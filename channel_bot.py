import os
import sys
import logging
import requests
from datetime import datetime
from config import get_sent_links, save_link
from parsers import get_all_news
from formatters import format_news

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_API_URL = "https://platform-api.max.ru"

TOKEN = os.getenv("MAX_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

def send_message(token, chat_id, text):
    """Отправляет сообщение в канал через MAX API"""
    url = f"https://api.max.ru/bot{token}/sendMessage"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "format": "markdown"
    }
    
    logger.info(f"🔍 Отправка POST на {url}")
    logger.info(f"🔍 chat_id: {chat_id}")
    logger.info(f"🔍 текст: {text[:100]}...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.info(f"✅ Статус ответа: {response.status_code}")
        logger.info(f"📦 Тело ответа: {response.text}")
        
        if response.status_code == 200:
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def main():
    """Основная функция бота"""
    logger.info("=== Starting Insider Seller Bot ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id and channel_id.startswith('@'):
        channel_id = "-100" + channel_id.replace('@id', '').replace('_biz', '')
    
    if not token:
        logger.error("MAX_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    if not channel_id:
        logger.error("CHANNEL_ID not set in environment")
        sys.exit(1)
    
    logger.info(f"Token: {'*' * 10}...{token[-5:]}")
    logger.info(f"Channel ID: {channel_id}")
    
    test_result = send_message(token, channel_id, "✅ Тест: бот запущен и работает")
    logger.info(f"Тестовое сообщение отправлено: {test_result}")
    
    import config
    news_items = get_all_news(config, hours=24)
    
    logger.info(f"Total news items fetched: {len(news_items)}")
    
    if not news_items:
        test_msg = "⚠️ ТЕСТ: новости не найдены, но бот работает"
        send_message(token, channel_id, test_msg)
        logger.info("No news found, sent test message")
        return
    
    sent_links = get_sent_links()
    new_posts = 0
    
    for item in news_items:
        link = item.get('link', '')
        
        if link in sent_links:
            logger.info(f"Skipping already posted: {link[:50]}...")
            continue
        
        formatted_message = format_news(item)
        
        success = send_message(token, channel_id, formatted_message)
        
        if success:
            save_link(link)
            sent_links.add(link)
            new_posts += 1
            logger.info(f"Posted: {item['title'][:50]}...")
        else:
            logger.warning(f"Failed to post: {item['title'][:50]}...")
    
    logger.info(f"=== Bot finished. New posts: {new_posts} ===")

if __name__ == "__main__":
    main()