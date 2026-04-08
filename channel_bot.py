import os
import sys
import logging
import requests
from datetime import datetime
from config import get_sent_links, save_link
from parsers import get_all_news, parse_court_cases, parse_sales
from formatters import format_news
from filters import filter_news
from db import init_db, get_pending_news, add_to_queue_batch, mark_published, get_all_pending_count
from llm import enhance_post_with_llm, USE_LLM
from scheduler import is_morning_time, is_evening_time, get_morning_summary, get_evening_digest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("MAX_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

MAX_POSTS_PER_RUN = 1

logger.info(f"USE_LLM = {USE_LLM}")
logger.info(f"GH_TOKEN configured = {bool(os.getenv('GH_TOKEN'))}")

from llm import GITHUB_TOKEN
logger.info(f"LLM will use token: {bool(GITHUB_TOKEN)}")

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

def is_silent_hours():
    """Проверяет, сейчас тихий час (00:00-06:00 МСК)"""
    msk = datetime.now()
    return msk.hour < 6

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
    
    init_db()
    logger.info("Database initialized")
    
    if is_morning_time():
        logger.info("🌅 Утренняя сводка (06:00)")
        summary = get_morning_summary()
        if summary:
            send_message(token, channel_id, summary)
            logger.info("Morning summary sent")
        return
    
    if is_evening_time():
        logger.info("🌙 Вечерний дайджест (23:00)")
        digest = get_evening_digest()
        if digest:
            send_message(token, channel_id, digest)
            logger.info("Evening digest sent")
        return
    
    import config
    news_items = get_all_news(config, hours=24)
    logger.info(f"Total RSS news fetched: {len(news_items)}")
    
    court_items = parse_court_cases()
    logger.info(f"Court cases fetched: {len(court_items)}")
    news_items.extend(court_items)
    
    sale_items = parse_sales()
    logger.info(f"Sales fetched: {len(sale_items)}")
    news_items.extend(sale_items)
    
    logger.info(f"Total news after all sources: {len(news_items)}")
    
    filtered_news = []
    for item in news_items:
        title = item.get('title', '')
        description = item.get('description', '')
        link = item.get('link', '')
        
        if filter_news(title, description, link):
            filtered_news.append(item)
    
    logger.info(f"After filtering: {len(filtered_news)} important news")
    
    added = add_to_queue_batch(filtered_news)
    logger.info(f"Added {added} new items to queue")
    
    pending_count = get_all_pending_count()
    logger.info(f"Queue: {pending_count} pending")
    
    pending = get_pending_news(MAX_POSTS_PER_RUN)
    logger.info(f"Sending {len(pending)} posts this run")
    
    if not pending:
        logger.info("No new posts to send this run")
        return
    
    new_posts = 0
    
    for item in pending:
        link = item.get('link', '')
        
        raw_text = item.get('raw_text', '') or item.get('description', '') or ''
        has_raw_text = bool(raw_text)
        logger.info(f"Processing item: id={item.get('id')}, has_raw_text={has_raw_text}, title={item.get('title', '')[:30]}...")
        
        if USE_LLM and has_raw_text:
            logger.info(f"Calling LLM for item {item.get('id')}")
            item['raw_text'] = raw_text
            enhanced = enhance_post_with_llm(item)
            if enhanced:
                logger.info(f"LLM returned enhanced text for item {item.get('id')}")
                formatted_message = enhanced
            else:
                logger.info(f"LLM returned None, using fallback for item {item.get('id')}")
                formatted_message = format_news(item)
        else:
            formatted_message = format_news(item)
        
        success = send_message(token, channel_id, formatted_message)
        
        if success:
            save_link(link)
            mark_published(item['id'])
            new_posts += 1
            logger.info(f"✓ Posted: {item['title'][:50]}...")
        else:
            logger.error(f"✗ Failed: {item['title'][:50]}...")
    
    final_pending = get_all_pending_count()
    logger.info(f"=== Bot finished. Sent: {new_posts}, Remaining in queue: {final_pending} ===")

if __name__ == "__main__":
    main()
