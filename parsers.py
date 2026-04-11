import feedparser
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict
from filters import is_court_case, is_seller_story
from config import DEFAULT_IMAGE_URL

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # === TIER 1: Marketplace Official - NO PUBLIC RSS AVAILABLE ===
    # All official marketplace docs use HTML/API, not RSS
    # Monitoring via: Telegram @OzonSellerAPI, @wb_api_news
    # === TIER 2: E-commerce / Retail Media (working RSS) ===
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC")
]

# HTML-only sources with actual working endpoints
HTML_ONLY_SOURCES = {
    "Ozon Seller News": {
        "url": "https://dev.ozon.ru/ru/news/",
        "type": "html",
        "tier": "tier1",
        "headers": {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        "selectors": {
            "item": "article, .news-item, .article",
            "title": "h1, h2, .news-item__title",
            "link": "a[href]",
            "date": "time, .news-item__date, .article__date"
        }
    },
    "Yandex Market Updates": {
        "url": "https://yandex.ru/dev/market/partner-api/doc/ru/changelog/all",
        "type": "html",
        "tier": "tier1",
        "headers": {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        "selectors": {
            "item": "h3[id]",
            "title": "h3",
            "link": "a[href]",
            "date": "h3"
        }
    }
}

LEGAL_NEWS_FEEDS = [
    ("https://pravo.ru/news/partner/feed/", "Право.ru"),
    ("https://www.legalreport.ru/rss/", "LegalReport"),
]

COURT_RSS_FEEDS = [
    ("https://mos-gorsud.ru/rss/index", "МосГорСуд"),
    ("https://www.mosobl.sudrf.ru/modules.php?name=press_dep&func=page&page=2&rss=1", "МособлСуд"),
]

SALE_RSS_FEEDS = [
    ("https://www.retail.ru/rss/tag/akcii/", "Retail.ru Акции"),
    ("https://e-pepper.ru/news/rss.xml", "E-Pepper"),
]

MARKETPLACE_KEYWORDS = ["маркетплейс", "озон", "wildberries", "яндекс маркет", "ozon", "wb", "ozon", "мегамаркет"]

SALE_KEYWORDS = ["акция", "распродажа", "скидк", "бонус", "cashback", "чёрная пятница", "11.11", "сезонная", "промокод", "купон", "спецпредложение", "特卖", "特價"]

LEGAL_KEYWORDS = ["суд", "арбитраж", "иск", "взыскание", "убытки", "компенсация", "штраф", "решение суда", "мосгорсуд", "мосobl", "кадатр"]

def is_legal_news(title, description):
    text = f"{title} {description}".lower()
    return any(kw in text for kw in LEGAL_KEYWORDS)

def is_sale_news(title, description):
    text = f"{title} {description}".lower()
    return any(kw in text for kw in SALE_KEYWORDS)

def determine_importance(title, description):
    text = f"{title} {description}".lower()
    
    critical_keywords = ["взыскание", "убытки", "компенсация", "миллион", "штраф", "блокировка", "крупный", "тяжба"]
    if any(kw in text for kw in critical_keywords):
        return "critical"
    
    important_keywords = ["подмена товара", "возврат", "нарушение прав", "неустойка", "повышение тарифа", "изменение", "иск"]
    if any(kw in text for kw in important_keywords):
        return "high"
    
    return "normal"

def fetch_rss_feed(url, source_name):
    try:
        feed = feedparser.parse(url)
        if feed.bozo and feed.bozo_exception:
            exc_str = str(feed.bozo_exception)[:100]
            logger.warning(f"RSS [{source_name}] bozo: {exc_str}")
        
        if not feed.entries:
            logger.warning(f"RSS [{source_name}] empty feed")
        
        return feed
    except Exception as e:
        logger.error(f"RSS [{source_name}] error: {e}")
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
    except:
        pass
    
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
        feed = fetch_rss_feed(self.url, self.name)
        if not feed:
            return []
        
        news_items = []
        success_count = 0
        
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
                success_count += 1
                    
            except Exception as e:
                logger.warning(f"RSS [{self.name}] entry error: {e}")
                continue
        
        logger.info(f"RSS [{self.name}]: {success_count} items")
        return news_items
    
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
    
    logger.info(f"RSS total: {len(all_news)} items from {len(RSS_FEEDS)} sources")
    return all_news

def extract_sales_from_news(news_items):
    """Извлекает sales-акции из общего потока новостей"""
    sales_items = []
    seen_links = set()
    
    for item in news_items:
        link = item.get('link', '')
        if not link or link in seen_links:
            continue
        if item.get('category') == 'sale':
            continue
            
        if is_sale_news(item.get('title', ''), item.get('description', '')):
            item['importance'] = 'normal'
            item['category'] = 'sale'
            sales_items.append(item)
            seen_links.add(link)
    
    logger.info(f"Sales from RSS: {len(sales_items)} items")
    return sales_items

def parse_sales():
    """Парсит акции маркетплейсов из специализированных RSS"""
    sale_news = []
    
    for feed_url, feed_name in SALE_RSS_FEEDS:
        try:
            parser = RSSParser(feed_url, feed_name, "sale")
            news = parser.fetch(hours=24)
            
            for item in news:
                item['importance'] = 'normal'
                item['category'] = 'sale'
                sale_news.append(item)
        except Exception as e:
            logger.error(f"Sales [{feed_name}] error: {e}")
    
    logger.info(f"Sales RSS: {len(sale_news)} items from dedicated feeds")
    return sale_news

def parse_legal_news(news_items=None):
    """Парсит legal-новости - из специализированных И из общего потока"""
    legal_news = []
    
    # 1. Specialized legal feeds
    for feed_url, feed_name in LEGAL_NEWS_FEEDS:
        try:
            parser = RSSParser(feed_url, feed_name, "legal")
            news = parser.fetch(hours=24)
            
            for item in news:
                title_lower = item.get('title', '').lower()
                desc_lower = item.get('description', '').lower()
                
                if any(kw in title_lower or kw in desc_lower for kw in MARKETPLACE_KEYWORDS):
                    item['importance'] = determine_importance(item.get('title', ''), item.get('description', ''))
                    item['category'] = 'legal'
                    legal_news.append(item)
        except Exception as e:
            logger.error(f"Legal [{feed_name}] error: {e}")
    
    # 2. Extract legal news from general RSS stream
    if news_items:
        for item in news_items:
            if is_legal_news(item.get('title', ''), item.get('description', '')):
                item['importance'] = determine_importance(item.get('title', ''), item.get('description', ''))
                item['category'] = 'legal'
                legal_news.append(item)
    
    logger.info(f"Legal news total: {len(legal_news)} items")
    return legal_news

def parse_court_cases():
    """Парсит судебные дела по маркетплейсам"""
    court_news = []
    
    for feed_url, feed_name in COURT_RSS_FEEDS:
        try:
            parser = RSSParser(feed_url, feed_name, "court")
            news = parser.fetch(hours=24)
            
            for item in news:
                title_lower = item.get('title', '').lower()
                desc_lower = item.get('description', '').lower()
                
                if any(kw in title_lower or kw in desc_lower for kw in MARKETPLACE_KEYWORDS):
                    if is_court_case(item.get('title', ''), item.get('description', '')):
                        item['importance'] = determine_importance(item.get('title', ''), item.get('description', ''))
                        item['category'] = 'court'
                        court_news.append(item)
        except Exception as e:
            logger.error(f"Court [{feed_name}] error: {e}")
    
    logger.info(f"Court RSS: {len(court_news)} items from court feeds")
    return court_news


def fetch_html_sources(hours: int = 24) -> List[Dict]:
    """Fetch news from HTML-only sources (no RSS available)"""
    html_news = []
    
    for source_name, config in HTML_ONLY_SOURCES.items():
        try:
            url = config.get('url')
            source_type = config.get('type', 'html')
            tier = config.get('tier', 'tier2')
            
            if source_type == 'json':
                # API endpoint
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    # Parse JSON structure (Ozon-style)
                    items = data.get('items', data.get('news', []))
                    for item in items:
                        html_news.append({
                            'title': item.get('title', ''),
                            'description': item.get('description', item.get('annotation', '')),
                            'link': item.get('link', item.get('url', '')),
                            'source': source_name,
                            'category': 'marketplace',
                            'importance': 'high',
                            'priority_bucket': 'high'
                        })
            else:
                # HTML parsing
                headers = config.get('headers', {})
                response = requests.get(url, timeout=15, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    selectors = config.get('selectors', {})
                    
                    items = soup.select(selectors.get('item', 'article, .news-item'))
                    for item in items:
                        title_elem = item.select_one(selectors.get('title', 'h2, h3, .title'))
                        link_elem = item.select_one(selectors.get('link', 'a[href]'))
                        date_elem = item.select_one(selectors.get('date', 'time, .date'))
                        
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            if not title_text or len(title_text) < 5:
                                continue
                            
                            item_text = item.get_text(strip=True)
                            if len(item_text) > 1000:
                                item_text = item_text[:1000]
                            
                            html_news.append({
                                'title': title_text,
                                'description': item_text,
                                'link': link_elem.get('href', '') if link_elem else '',
                                'source': source_name,
                                'category': 'marketplace',
                                'importance': 'high',
                                'priority_bucket': 'high'
                            })
            
            logger.info(f"HTML source [{source_name}]: {len(html_news)} items")
        except Exception as e:
            logger.warning(f"HTML source [{source_name}] error: {e}")
    
    return html_news
