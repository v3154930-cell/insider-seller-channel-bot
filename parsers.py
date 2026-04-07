import feedparser
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timezone, timedelta
import re
from filters import is_court_case, is_seller_story

logger = logging.getLogger(__name__)

# FIXED: Swapped order to (url, name) instead of (name, url)
RSS_FEEDS = [
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC")
]

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
                    
                    news_items.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "description": description.strip()[:500],
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
                        "pub_date": datetime.now(timezone.utc),
                        "source": self.name,
                        "category": self.category,
                        "type": self._determine_type(title)
                    })
                        
                except Exception as e:
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching HTML {self.name}: {e}")
            return []
    
    def _determine_type(self, title):
        text = title.lower()
        
        if is_court_case(title, ""):
            return "court"
        elif is_seller_story(title, ""):
            return "seller_story"
        
        return "general"


def get_all_news(config, hours=24):
    all_news = []
    
    for feed_url, feed_name in RSS_FEEDS:
        parser = RSSParser(feed_url, feed_name, "general")
        news = parser.fetch(hours)
        all_news.extend(news)
        logger.info(f"Fetched {len(news)} items from {feed_name}")
    
    return all_news
