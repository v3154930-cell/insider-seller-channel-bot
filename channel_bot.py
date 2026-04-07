import os
import sys
import json
import logging
import requests
from datetime import datetime
from config import get_sent_links, save_link
from parsers import get_all_news
from formatters import format_news
from filters import filter_news

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("MAX_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

NEWS_CACHE_FILE = "news_cache.json"
MAX_POSTS_PER_RUN = 2

def send_message(token, chat_id, text):
    """Отправляет сообщение в канал через MAX API"""
    url = f"https://platform-api.max.ru/messages?chat_id={chat_id}"
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    
    payload = {"text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def load_news_cache():
    """Загружает кэш новостей"""
    try:
        with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"pending": [], "sent": []}

def save_news_cache(cache):
    """Сохраняет кэш новостей"""
    with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def add_news_to_cache(news_items):
    """Добавляет новости в кэш"""
    cache = load_news_cache()
    
    existing_links = {item['link'] for item in cache.get('pending', [])}
    existing_links.update(item['link'] for item in cache.get('sent', []))
    
    new_pending = []
    for item in news_items:
        if item['link'] not in existing_links:
            new_pending.append(item)
    
    cache['pending'] = cache.get('pending', []) + new_pending
    
    save_news_cache(cache)
    logger.info(f"Added {len(new_pending)} new items to cache. Total pending: {len(cache['pending'])}")
    return len(new_pending)

def get_pending_news(count):
    """Получает новости для отправки и помечает как обработанные"""
    cache = load_news_cache()
    
    pending = cache.get('pending', [])
    to_send = pending[:count]
    remaining = pending[count:]
    
    sent = cache.get('sent', [])
    for item in to_send:
        sent.append(item)
    
    cache['pending'] = remaining
    cache['sent'] = sent
    
    save_news_cache(cache)
    return to_send

def get_cached_stats():
    """Возвращает статистику кэша"""
    cache = load_news_cache()
    return {
        'pending': len(cache.get('pending', [])),
        'sent': len(cache.get('sent', []))
    }

def main():
    """Основная функция бота"""
    logger.info("=== Starting Insider Seller Bot ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id:
        if channel_id.startswith('@'):
            channel_id = "-73160979033512"
        elif channel_id.isdigit():
            channel_id = f"-{channel_id}"
    
    if not token:
        logger.error("MAX_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    if not channel_id:
        logger.error("CHANNEL_ID not set in environment")
        sys.exit(1)
    
    logger.info(f"Token: {'*' * 10}...{token[-5:]}")
    logger.info(f"Channel ID: {channel_id}")
    
    stats = get_cached_stats()
    logger.info(f"Cache stats: {stats['pending']} pending, {stats['sent']} sent")
    
    import config
    news_items = get_all_news(config, hours=24)
    
    logger.info(f"Total RSS news fetched: {len(news_items)}")
    
    filtered_news = []
    for item in news_items:
        title = item.get('title', '')
        description = item.get('description', '')
        link = item.get('link', '')
        
        if filter_news(title, description, link):
            filtered_news.append(item)
    
    logger.info(f"After filtering: {len(filtered_news)} important news")
    
    added = add_news_to_cache(filtered_news)
    logger.info(f"Added {added} new items to cache")
    
    stats = get_cached_stats()
    logger.info(f"Cache: {stats['pending']} pending, {stats['sent']} total sent")
    
    to_send = get_pending_news(MAX_POSTS_PER_RUN)
    logger.info(f"Sending {len(to_send)} posts this run")
    
    if not to_send:
        logger.info("No new posts to send this run")
        return
    
    new_posts = 0
    
    for item in to_send:
        link = item.get('link', '')
        
        formatted_message = format_news(item)
        
        success = send_message(token, channel_id, formatted_message)
        
        if success:
            save_link(link)
            new_posts += 1
            logger.info(f"✓ Posted: {item['title'][:50]}...")
        else:
            logger.error(f"✗ Failed: {item['title'][:50]}...")
    
    final_stats = get_cached_stats()
    logger.info(f"=== Bot finished. Sent: {new_posts}, Remaining in queue: {final_stats['pending']} ===")

if __name__ == "__main__":
    main()
