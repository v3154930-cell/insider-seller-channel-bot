"""
Staging Publisher - Fixed version with canonical final_link.

Key fixes:
1. Always use get_source_link() to get canonical URL
2. Don't trust link block from LLM enhance
3. Always append one canonical source line before sending
"""

import os
import sys
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

STAGING_MODE = os.getenv("STAGING_MODE", "true").lower() == "true"

from db import init_db, get_pending_news, mark_published, mark_dropped, get_all_pending_count, get_all_queued_count
from formatters import format_news, get_source_link, detect_link_type
from llm import enhance_post_with_llm, USE_LLM, select_best_items_for_publishing


def extract_existing_source_link(text: str) -> str:
    """Extract existing source/link line from text to remove it."""
    if not text:
        return ""
    
    patterns = [
        r'(?:Источник|Source)[\s\n]*[:\-]?\s*[\n]?(https?://[^\s]+)',
        r'🔗\s*<a\s+href="([^"]+)">[^<]+</a>',
        r'Ссылка[\s\n]*[:\-]?\s*[\n]?(https?://[^\s]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    
    return ""


def append_canonical_source_line(text: str, final_link: str, link_type: str) -> str:
    """Append one canonical source line - replaces any existing source link."""
    text = (text or "").rstrip()
    
    if not final_link:
        return text
    
    source_line = f"\n\n🔗 <a href=\"{final_link}\">Источник</a>"
    
    return text + source_line


def publish_item_staging(item: dict, channel_id: str, token: str) -> bool:
    """
    Publish one item in staging - with canonical final_link fix.
    """
    item_id = item.get('id')
    
    final_link, link_type = get_source_link(item)
    logger.info(f"Item {item_id}: final_link={final_link[:60] if final_link else 'EMPTY'}, link_type={link_type}")
    
    raw_text = item.get('raw_text', '')
    has_raw_text = bool(raw_text)
    enhance_success = False
    
    if USE_LLM and has_raw_text:
        logger.info(f"Final enhance started for {item_id}")
        enhanced = enhance_post_with_llm(item)
        
        if enhanced:
            formatted_message = enhanced
            enhance_success = True
            logger.info(f"Final enhance ok: id={item_id}")
            
            existing = extract_existing_source_link(enhanced)
            if existing and existing != final_link:
                logger.warning(f"Enhanced contains different source link: {existing[:50]} != {final_link[:50]}")
        else:
            formatted_message = format_news(item)
            logger.warning(f"Final enhance failed: id={item_id}, using fallback")
    else:
        formatted_message = format_news(item)
    
    formatted_message = append_canonical_source_line(formatted_message, final_link, link_type)
    
    logger.info(f"Final message length: {len(formatted_message)}")
    
    return True


def run_staging_publisher(run_manual: bool = False):
    """
    Run staging publisher - preview only, doesn't actually post to MAX.
    """
    logger.info("=== Staging Publisher (Preview Only) ===")
    logger.info(f"STAGING_MODE: {STAGING_MODE}")
    
    if not run_manual and not STAGING_MODE:
        logger.warning("STAGING_MODE not enabled - this should only run in staging!")
    
    init_db()
    
    pending = get_all_queued_count()
    logger.info(f"Queue size: {pending}")
    
    if pending == 0:
        logger.info("No pending posts")
        return
    
    items = get_pending_news(min(50, pending))
    logger.info(f"Loaded: {len(items)} items")
    
    eval_results = []
    for item in items:
        from staging.preview_staging import evaluate_item_relevance
        result = evaluate_item_relevance(item)
        eval_results.append((item, result))
    
    passed_items = [item for item, result in eval_results if result["passed"]]
    logger.info(f"Relevance gate passed: {len(passed_items)}")
    
    if not passed_items:
        logger.info("No items passed relevance gate - skipping")
        return
    
    MAX_POSTS_PER_RUN = 2
    candidate_pool_size = MAX_POSTS_PER_RUN * 4
    candidates = select_best_items_for_publishing(passed_items, candidate_pool_size)
    
    if not candidates:
        logger.warning("No items selected after LLM filtering")
        return
    
    selected = candidates[:MAX_POSTS_PER_RUN]
    logger.info(f"Selected: {len(selected)}")
    
    for item in selected:
        publish_item_staging(item, "", "")


if __name__ == "__main__":
    run_staging_publisher(run_manual=True)