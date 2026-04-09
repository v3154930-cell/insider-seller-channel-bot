import os
import sys
import logging
from datetime import datetime
from config import get_sent_links
from parsers import get_all_news, parse_court_cases, parse_sales, parse_legal_news, extract_sales_from_news
from filters import filter_news
from db import init_db, add_to_queue_batch, get_all_pending_count, clean_duplicates, get_duplicate_count
from scheduler import now_moscow
from scoring import score_items

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_collector():
    """Сбор новостей из всех источников и сохранение в SQLite"""
    logger.info("=== Collector mode ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    init_db()
    logger.info("Database initialized")
    logger.info(f"Current time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    news_items = get_all_news(hours=24)
    logger.info(f"RSS fetched: {len(news_items)}")
    
    legal_items = parse_legal_news(news_items)
    logger.info(f"Legal fallback feeds: {len(legal_items)}")
    news_items.extend(legal_items)
    
    court_items = parse_court_cases()
    logger.info(f"Court feeds: {len(court_items)}")
    news_items.extend(court_items)
    
    sale_items = parse_sales()
    logger.info(f"Sales dedicated feeds: {len(sale_items)}")
    
    sales_from_rss = extract_sales_from_news(news_items)
    logger.info(f"Sales from RSS: {len(sales_from_rss)}")
    
    all_sale_items = sale_items + sales_from_rss
    logger.info(f"Sales total: {len(all_sale_items)}")
    news_items.extend(all_sale_items)
    
    logger.info(f"Normalized items: {len(news_items)}")
    
    filtered_news = []
    for item in news_items:
        title = item.get('title', '')
        description = item.get('description', '')
        link = item.get('link', '')
        
        if filter_news(title, description, link):
            filtered_news.append(item)
    
    logger.info(f"After filtering: {len(filtered_news)} important news")
    
    scored_news = score_items(filtered_news)
    logger.info(f"After scoring: {len(scored_news)} scored news")
    
    total_before = get_all_pending_count()
    added = add_to_queue_batch(scored_news)
    duplicates_skipped = len(scored_news) - added if scored_news else 0
    
    dup_count = get_duplicate_count()
    if dup_count > 0:
        logger.info(f"Found {dup_count} duplicate groups in pending queue, cleaning...")
        removed = clean_duplicates()
        logger.info(f"Removed {removed} duplicate rows")
        added -= removed
    
    logger.info(f"Saved to DB: {added} new items")
    logger.info(f"Duplicates skipped: {duplicates_skipped}")
    
    pending_count = get_all_pending_count()
    logger.info(f"Queue size: {pending_count} pending")
    logger.info("=== Collector finished ===")

if __name__ == "__main__":
    run_collector()
