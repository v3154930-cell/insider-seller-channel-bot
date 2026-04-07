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
    url = f"{MAX_API_URL}/messages"
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {chat_id}")
            return True
        else:
            logger.error(f"Failed to send message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def main():
    """Основная функция бота"""
    logger.info("=== Starting Insider Seller Bot ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if not token:
        logger.error("MAX_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    if not channel_id:
        logger.error("CHANNEL_ID not set in environment")
        sys.exit(1)
    
    logger.info(f"Token: {'*' * 10}...{token[-5:]}")
    logger.info(f"Channel ID: {channel_id}")
    
    import config
    news_items = get_all_news(config, hours=24)
    
    logger.info(f"Total news items fetched: {len(news_items)}")
    
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