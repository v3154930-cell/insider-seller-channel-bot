import feedparser
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
from filters import filter_news, is_court_case, is_seller_story

logger = logging.getLogger(__name__)

class RSSParser:
    """Парсер RSS-лент"""
    
    def __init__(self, feed_url, name, category):
        self.url = feed_url
        self.name = name
        self.category = category
    
    def fetch(self, hours=24):
        """Получает новости из RSS-ленты за последние hours часов"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            
            news_items = []
            time_limit = datetime.now() - timedelta(hours=hours)
            
            for entry in feed.entries[:50]:
                try:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    description = self._clean_html(entry.get('description', ''))
                    pub_date = self._parse_date(entry.get('published', ''))
                    
                    if not title or not link:
                        continue
                    
                    if pub_date and pub_date < time_limit:
                        continue
                    
                    if filter_news(title, description, link):
                        news_items.append({
                            'title': title.strip(),
                            'link': link.strip(),
                            'description': description.strip()[:500],
                            'pub_date': pub_date,
                            'source': self.name,
                            'category': self.category,
                            'type': self._determine_type(title, description)
                        })
                        
                except Exception as e:
                    logger.warning(f"Error parsing entry: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching RSS {self.name}: {e}")
            return []
    
    def _clean_html(self, text):
        """Очищает HTML от тегов"""
        if not text:
            return ""
        soup = BeautifulSoup(text, 'lxml')
        return soup.get_text()
    
    def _parse_date(self, date_str):
        """Парсит дату из строки"""
        if not date_str:
            return None
        
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            pass
        
        try:
            formats = [
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d.%m.%Y %H:%M',
                '%d.%m.%Y',
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue
        except:
            pass
        
        return None
    
    def _determine_type(self, title, description):
        """Определяет тип новости"""
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
    """Парсер HTML-страниц"""
    
    def __init__(self, url, name, category):
        self.url = url
        self.name = name
        self.category = category
    
    def fetch(self, hours=24):
        """Получает новости со страницы"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            news_items = []
            
            articles = soup.find_all('a', href=True)
            
            for article in articles[:30]:
                try:
                    href = article.get('href', '')
                    title = article.get_text(strip=True)
                    
                    if not title or len(title) < 20:
                        continue
                    
                    if not href.startswith('http'):
                        href = self.url.rstrip('/') + href
                    
                    if filter_news(title, "", href):
                        news_items.append({
                            'title': title,
                            'link': href,
                            'description': '',
                            'pub_date': None,
                            'source': self.name,
                            'category': self.category,
                            'type': self._determine_type(title)
                        })
                        
                except Exception as e:
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching HTML {self.name}: {e}")
            return []
    
    def _determine_type(self, title):
        """Определяет тип новости"""
        text = title.lower()
        
        if is_court_case(title, ""):
            return "court"
        elif is_seller_story(title, ""):
            return "seller_story"
        
        return "general"


def get_all_news(config, hours=24):
    """Получает все новости из всех источников"""
    all_news = []
    
    for feed_config in config.RSS_FEEDS:
        parser = RSSParser(
            feed_config['url'],
            feed_config['name'],
            feed_config.get('category', 'general')
        )
        news = parser.fetch(hours)
        all_news.extend(news)
        logger.info(f"Fetched {len(news)} items from {feed_config['name']}")
    
    return all_news