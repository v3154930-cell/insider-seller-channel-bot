import feedparser
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import urljoin
from filters import is_court_case, is_seller_story
from config import DEFAULT_IMAGE_URL

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC")
]

def extract_image_from_entry(entry, link):
    """Извлекает URL изображения из entry или со страницы новости"""
    
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('type', '').startswith('image/'):
                url = media.get('url')
                if url:
                    logger.info(f"   🖼️ Картинка из media_content: {url[:50]}...")
                    return url
    
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                url = enc.get('url')
                if url:
                    logger.info(f"   🖼️ Картинка из enclosure: {url[:50]}...")
                    return url
    
    try:
        response = requests.get(link, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image.get('content')
                if img_url:
                    logger.info(f"   🖼️ Картинка из og:image: {img_url[:50]}...")
                    return img_url
            
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                img_url = twitter_image.get('content')
                if img_url:
                    logger.info(f"   🖼️ Картинка из twitter:image: {img_url[:50]}...")
                    return img_url
            
            first_img = soup.find('img')
            if first_img and first_img.get('src'):
                img_src = first_img.get('src')
                if img_src:
                    if img_src.startswith('http'):
                        abs_url = img_src
                    elif img_src.startswith('/'):
                        abs_url = urljoin(link, img_src)
                    else:
                        abs_url = urljoin(link, '/' + img_src)
                    logger.info(f"   🖼️ Картинка из первого img: {abs_url[:50]}...")
                    return abs_url
    
    except Exception as e:
        logger.warning(f"   ⚠️ Ошибка извлечения изображения: {e}")
    
    logger.info(f"   🖼️ Картинка не найдена, используется заглушка")
    return DEFAULT_IMAGE_URL

def shorten_text(text, limit=200):
    if not text:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    if len(clean_text) <= limit:
        return clean_text
    shortened = clean_text[:limit]
    last_space = shortened.rfind(' ')
    if last_space > 0:
        shortened = shortened[:last_space]
    return shortened + "..."

class RSSParser:
    def __init__(self, feed_url, name, category):
        self.url = feed_url
        self.name = name
        self.category = category
    
    def fetch(self, hours=24):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            
            news_items = []
            
            for entry in feed.entries[:30]:
                try:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    description = self._clean_html(entry.get("description", ""))
                    
                    if not title or not link:
                        continue
                    
                    published_date = self._parse_date(entry)
                    image_url = extract_image_from_entry(entry, link)
                    short_text = shorten_text(description)
                    
                    news_items.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "description": description.strip()[:500],
                        "short_text": short_text,
                        "image_url": image_url,
                        "pub_date": published_date,
                        "source": self.name,
                        "category": self.category,
                        "type": self._determine_type(title, description)
                    })
                        
                except Exception as e:
                    logger.warning(f"Error parsing entry: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching RSS {self.name}: {e}")
            return []
    
    def _clean_html(self, text):
        if not text:
            return ""
        soup = BeautifulSoup(text, "lxml")
        return soup.get_text()
    
    def _parse_date(self, entry):
        try:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            
            if published:
                published_date = datetime(*published[:6])
                
                if published_date.tzinfo is None:
                    published_date = published_date.replace(tzinfo=timezone.utc)
            else:
                published_date = datetime.now(timezone.utc)
                
            return published_date
        except Exception as e:
            return datetime.now(timezone.utc)
    
    def _determine_type(self, title, description):
        text = f"{title} {description}".lower()
        
        if is_court_case(title, description):
            return "court"
        elif is_seller_story(title, description):
            return "seller_story"
        elif "озон" in text or "ozon" in text:
            return "ozon"
        elif "wildberries" in text or "wb" in text or "вилдберриз" in text:
            return "wildberries"
        elif "яндекс" in text or "market" in text:
            return "yandex"
        else:
            return "general"


class HTMLParser:
    def __init__(self, url, name, category):
        self.url = url
        self.name = name
        self.category = category
    
    def fetch(self, hours=24):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            news_items = []
            
            articles = soup.find_all("a", href=True)
            
            for article in articles[:30]:
                try:
                    href = article.get("href", "")
                    title = article.get_text(strip=True)
                    
                    if not title or len(title) < 20:
                        continue
                    
                    if not href.startswith("http"):
                        href = self.url.rstrip("/") + href
                    
                    news_items.append({
                        "title": title,
                        "link": href,
                        "description": "",
                        "short_text": "",
                        "i
