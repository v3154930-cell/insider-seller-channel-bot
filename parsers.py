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

COURT_RSS_FEEDS = [
    ("https://mos-gorsud.ru/rss/index", "МосГорСуд"),
    ("https://www.mosobl.sudrf.ru/modules.php?name=press_dep&func=page&page=2&rss=1", "МособлСуд"),
    ("https://pravo.ru/news/partner/feed/", "Право.ru"),
]

SALE_RSS_FEEDS = [
    ("https://www.retail.ru/rss/tag/akcii/", "Retail.ru Акции"),
    ("https://e-pepper.ru/news/rss.xml", "E-Pepper"),
    ("https://www.retail.ru/rss/tag/skidki/", "Retail.ru Скидки"),
]

SALE_KEYWORDS = ["акция", "распродажа", "скидка", "бонус", "cashback", "чёрная пятница", "11.11", "сезонная скидка"]

def is_sale_news(title, description):
    """Определяет, является ли новость акцией маркетплейса"""
    text = f"{title} {description}".lower()
    return any(kw in text for kw in SALE_KEYWORDS)

def determine_importance(title, description):
    """Определяет важность новости"""
    text = f"{title} {description}".lower()
    
    critical_keywords = ["взыскание", "убытки", "компенсация", "миллион", "штраф", "блокировка", "крупный"]
    if any(kw in text for kw in critical_keywords):
        return "critical"
    
    important_keywords = ["подмена товара", "возврат", "нарушение прав", "неустойка", "повышение тарифа", "изменение"]
    if any(kw in text for kw in important_keywords):
        return "high"
    
    return "normal"

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

def get_all_news(config=None, hours=24):
    all_news = []
    
    for feed_url, feed_name in RSS_FEEDS:
        parser = RSSParser(feed_url, feed_name, "general")
        news = parser.fetch(hours)
        all_news.extend(news)
        print(f"Fetched {len(news)} items from {feed_name}")
    
    return all_news

def parse_court_cases():
    """Парсит судебные дела по маркетплейсам"""
    court_news = []
    keywords = ["маркетплейс", "озон", "wildberries", "яндекс маркет", "ozon", "wb"]
    
    for feed_url, feed_name in COURT_RSS_FEEDS:
        try:
            parser = RSSParser(feed_url, feed_name, "court")
            news = parser.fetch(hours=24)
            
            for item in news:
                title = item.get('title', '').lower()
                desc = item.get('description', '').lower()
                
                if any(kw in title or kw in desc for kw in keywords):
                    if is_court_case(item.get('title', ''), item.get('description', '')):
                        importance = determine_importance(item.get('title', ''), item.get('description', ''))
                        item['importance'] = importance
                        item['category'] = 'court'
                        court_news.append(item)
        except Exception as e:
            print(f"Error parsing court feed {feed_name}: {e}")
    
    return court_news

def parse_sales():
    """Парсит акции маркетплейсов"""
    sale_news = []
    
    for feed_url, feed_name in SALE_RSS_FEEDS:
        try:
            parser = RSSParser(feed_url, feed_name, "sale")
            news = parser.fetch(hours=24)
            
            for item in news:
                if is_sale_news(item.get('title', ''), item.get('description', '')):
                    item['importance'] = 'normal'
                    item['category'] = 'sale'
                    sale_news.append(item)
        except Exception as e:
            print(f"Error parsing sale feed {feed_name}: {e}")
    
    return sale_news
