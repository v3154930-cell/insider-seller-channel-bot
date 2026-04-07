import feedparser
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import hashlib
from datetime import datetime, timezone
from filters import is_court_case, is_seller_story
from config import DEFAULT_IMAGE_URL

RSS_FEEDS = [
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC")
]

def fetch_rss_feed(url):
    try:
        feed = feedparser.parse(url)
        if feed.bozo and feed.bozo_exception:
            print(f"⚠️ Ошибка парсинга RSS: {feed.bozo_exception}")
        return feed
    except Exception as e:
        print(f"❌ Ошибка загрузки RSS {url}: {e}")
        return None

def extract_image_from_entry(entry, link, default_image=None):
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('type', '').startswith('image/'):
                url = media.get('url')
                if url:
                    return url
    
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                url = enc.get('url')
                if url:
                    return url
    
    try:
        response = requests.get(link, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image.get('content')
            
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                return twitter_image.get('content')
            
            first_img = soup.find('img')
            if first_img and first_img.get('src'):
                img_src = first_img.get('src')
                if img_src.startswith('http'):
                    return img_src
                elif img_src.startswith('/'):
                    return urljoin(link, img_src)
    except Exception as e:
        print(f"⚠️ Ошибка извлечения изображения: {e}")
    
    return default_image

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
            feed = fetch_rss_feed(self.url)
            if not feed:
                return []
            
            news_items = []
            
            for entry in feed.entries[:30]:
                try:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    description = self._clean_html(entry.get("description", ""))
                    
                    if not title or not link:
                        continue
                    
                    image_url = extract_image_from_entry(entry, link, DEFAULT_IMAGE_URL)
                    short_text = shorten_text(description)
                    
                    news_items.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "description": description.strip()[:500],
                        "short_text": short_text,
                        "image_url": image_url,
                        "source": self.name,
                        "category": self.category,
                        "type": self._determine_type(title, description)
                    })
                        
                except Exception as e:
                    print(f"Error parsing entry: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            print(f"Error fetching RSS {self.name}: {e}")
            return []
    
    def _clean_html(self, text):
        if not text:
            return ""
        soup = BeautifulSoup(text, "lxml")
        return soup.get_text()
    
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

def get_all_news(config, hours=24):
    all_news = []
    
    for feed_url, feed_name in RSS_FEEDS:
        parser = RSSParser(feed_url, feed_name, "general")
        news = parser.fetch(hours)
        all_news.extend(news)
        print(f"Fetched {len(news)} items from {feed_name}")
    
    return all_news
