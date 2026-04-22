"""
Staging Digest Preview Module

This module provides preview functionality for digest publishing in staging.
Instead of posting to MAX, it saves the final digest payload to a local file.

Does NOT call send_message() - only writes to outputs/.
"""

import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

STAGING_MODE = os.getenv("STAGING_MODE", "false").lower() == "true"
STAGING_OUTPUT_DIR = "/opt/newsbot-staging/outputs"


def get_item_url_local(item):
    """Get news URL with fallback - local helper"""
    return item.get("url") or item.get("link", "")


def ensure_staging_output_dir():
    os.makedirs(STAGING_OUTPUT_DIR, exist_ok=True)


def save_digest_preview(digest_type: str, news_items: list, output_file: str):
    ensure_staging_output_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"STAGING DIGEST PREVIEW - {digest_type.upper()}\n")
        f.write(f"Generated at {timestamp}\n")
        f.write("=" * 60 + "\n\n")
        
        from db import is_digest_sent_today
        f.write(f"Items count: {len(news_items)}\n")
        f.write(f"Already sent today: {is_digest_sent_today(digest_type)}\n\n")
        
        for i, item in enumerate(news_items, 1):
            link = get_item_url_local(item)
            f.write(f"\n--- ITEM #{i} ---\n")
            f.write(f"ID: {item.get('id')}\n")
            f.write(f"Title: {item.get('title', '')}\n")
            f.write(f"Link: {link}\n")
            f.write(f"Source: {item.get('source', 'N/A')}\n")
            f.write(f"Importance: {item.get('importance', 'normal')}\n")
            f.write(f"\nRaw text (first 300 chars):\n")
            raw = item.get("raw_text", "")
            f.write(raw[:300] if raw else "")
            if len(raw) > 300:
                f.write("...")
            f.write("\n")
        
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"Total items in digest preview: {len(news_items)}\n")
        f.write("NOTE: PREVIEW only - not sent to MAX channel\n")
    
    logger.info(f"Digest preview saved to: {output_file}")
    return output_file


def run_digest_preview():
    if not STAGING_MODE:
        logger.warning("STAGING_MODE not enabled!")
    
    logger.info("=== Staging Digest Preview Mode ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    ensure_staging_output_dir()
    
    from db import init_db, get_top_news_for_digest
    init_db()
    
    news_items = get_top_news_for_digest(limit=5)
    
    if not news_items:
        logger.info("No news available for digest preview")
        return
    
    logger.info(f"Selected items for digest: {len(news_items)}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(STAGING_OUTPUT_DIR, f"preview_digest_{timestamp}.txt")
    
    save_digest_preview("final_digest", news_items, output_file)
    logger.info(f"=== Staging Digest Preview finished. Output: {output_file} ===")


if __name__ == "__main__":
    run_digest_preview()