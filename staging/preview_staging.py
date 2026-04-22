"""
Staging Preview Module

This module provides preview functionality for staging environment.
Instead of posting to MAX, it saves the final payload to a local file.

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
STAGING_OUTPUT_DIR = os.getenv("STAGING_OUTPUT_DIR", "/opt/newsbot-staging/outputs")
STAGING_LINKS_FILE = os.getenv("STAGING_LINKS_FILE", "/opt/newsbot-staging/posted_links_staging.txt")

from db import init_db, get_pending_news, get_all_pending_count
from formatters import format_news, get_source_link, detect_link_type, filter_non_forum_links
from llm import enhance_post_with_llm, USE_LLM, select_best_items_for_publishing


def get_item_url_local(item):
    """Get news URL with fallback - local helper (legacy)"""
    return item.get("url") or item.get("link") or ""


DOMAIN_BLACKLIST = [
    "vc.ru", "rbc.ru", "habr.com", "3dnews.ru", "ixbt.com", "kopeechka.store",
    "telega.in", "teletype.in", "prmedia.io",
    "news.google.com", "news.yahoo.com"
]

CONTEXT_KEYWORDS = [
    "озон", "ozon", "wildberries", "wb", "яндекс маркет", "yandex market",
    "seller", "селлер", "продавец"
]

IMPACT_KEYWORDS = [
    "оферт", "услови", "договор", "правила", "комиссия", "тариф",
    "логистика", "хранение", "приемка", "возврат", "штраф",
    "реклама", "продвижение", "кабинет", "api", "fbo", "fbs", "dbs",
    "поставка", "склад"
]

STOP_SIGNALS = [
    "поздравля", "праздник", "день рождения", "конкурс", "премия",
    "рейтинг", "интервью", "подборк", "вдохновен", "lifestyle",
    "мероприят", "event", "спорт", "культур", "выставк", "форум"
]


def extract_domain(url: str) -> str:
    """Extract domain from URL for blacklist checking"""
    if not url:
        return ""
    url = url.lower()
    if "://" in url:
        domain = url.split("://")[1].split("/")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    return ""


def evaluate_item_relevance(item: dict) -> dict:
    """
    Hard relevance gate - evaluates if item passes BEFORE LLM processing.
    Returns dict with:
      - passed: bool - did it pass the gate?
      - score: int - relevance score (0-100)
      - reasons: [...]- list of pass/fail reasons
      - domain: str - extracted domain
      - title: str - item title
    """
    url = get_item_url_local(item)
    domain = extract_domain(url)
    title = item.get("title", "")
    
    reasons = []
    score = 0
    
    raw_text = item.get("raw_text", "") or ""
    description = item.get("description", "") or ""
    combined_text = f"{title} {description} {raw_text}".lower()
    
    if domain in DOMAIN_BLACKLIST:
        reasons.append(f"STOP: домен в черном списке ({domain})")
        return {"passed": False, "score": 0, "reasons": reasons, "domain": domain, "title": title[:50]}
    if domain:
        reasons.append(f"domain: {domain}")
    
    if not url or len(url) < 5:
        reasons.append("STOP: нет ссылки")
        return {"passed": False, "score": 0, "reasons": reasons, "domain": domain, "title": title[:50]}
    
    normalized = f"{title} {description} {raw_text}".strip()
    has_interview = "интервью" in combined_text
    if len(normalized) < 140:
        if has_interview:
            reasons.append("STOP: слишком короткий текст ({len(normalized)} < 140) для интервью")
            return {"passed": False, "score": 0, "reasons": reasons, "domain": domain, "title": title[:50]}
        reasons.append(f"STOP: слишком короткий текст ({len(normalized)} < 140)")
        return {"passed": False, "score": 0, "reasons": reasons, "domain": domain, "title": title[:50]}
    
    reasons.append(f"text_len: {len(normalized)}")
    
    context_found = False
    for kw in CONTEXT_KEYWORDS:
        if kw.lower() in combined_text:
            context_found = True
            reasons.append(f"context: {kw}")
            score += 25
            break
    
    if not context_found:
        reasons.append("STOP: нет связи с маркетплейсом/селлером (маркетплейс)")
        return {"passed": False, "score": 25, "reasons": reasons, "domain": domain, "title": title[:50]}
    
    impact_found = False
    for kw in IMPACT_KEYWORDS:
        if kw.lower() in combined_text:
            impact_found = True
            reasons.append(f"impact: {kw}")
            score += 35
            break
    
    if not impact_found:
        reasons.append("STOP: нет признаков практического влияния (влияние)")
        return {"passed": False, "score": 50, "reasons": reasons, "domain": domain, "title": title[:50]}
    
    reasons.append("passed")
    score = min(100, score)
    
    for stop in STOP_SIGNALS:
        if stop.lower() in combined_text:
            reasons.append(f"STOP: стоп-сигнал '{stop}' (стоп-рейтинг)")
            score -= 50
    
    passed = score >= 60
    
    return {"passed": passed, "score": score, "reasons": reasons, "domain": domain, "title": title[:50]}


def ensure_staging_output_dir():
    os.makedirs(STAGING_OUTPUT_DIR, exist_ok=True)


def append_source_line(message: str, link: str) -> str:
    message = (message or "").rstrip()
    if not link:
        return message + "\n\n⚠️ Источник: ссылка недоступна"
    return message + f"\n\nИсточник:\n{link}"


def save_preview_payload(items: list, output_file: str, eval_results: list = None):
    ensure_staging_output_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"STAGING PREVIEW - Generated at {timestamp}\n")
        f.write("=" * 60 + "\n\n")
        
        if eval_results:
            f.write("=== RELEVANCE GATE DEBUG ===\n\n")
            
            accepted_items = set(id(item) for item, result in eval_results if result["passed"])
            
            for item, result in eval_results:
                item_id = id(item)
                is_accepted = item_id in accepted_items
                
                status = "PASSED" if is_accepted else "REJECTED"
                f.write(f"[{status}] Domain: {result['domain']}\n")
                f.write(f"Title: {result['title']}\n")
                f.write(f"Score: {result['score']}/100\n")
                f.write(f"Reasons:\n")
                for reason in result["reasons"]:
                    f.write(f"  - {reason}\n")
                if is_accepted:
                    f.write(f"  >>> WOULD PUBLISH\n")
                f.write("\n" + "-" * 40 + "\n\n")
        
        f.write("=== READY FOR PUBLISH ===\n\n")
        
        for i, item in enumerate(items, 1):
            final_link, link_type = get_source_link(item)
            raw_text = item.get("raw_text", "")
            
            if USE_LLM and raw_text:
                enhanced = enhance_post_with_llm(item)
                formatted_message = enhanced if enhanced else format_news(item)
            else:
                formatted_message = format_news(item)
            
            formatted_message = append_source_line(formatted_message, final_link)
            
            f.write(f"\n--- POST #{i} ---\n")
            f.write(f"ID: {item.get('id')}\n")
            f.write(f"Title: {item.get('title', '')[:100]}\n")
            f.write(f"Final Link: {final_link}\n")
            f.write(f"Link Type: {link_type}\n")
            f.write(f"Source: {item.get('source', 'N/A')}\n")
            f.write(f"Category: {item.get('category', 'general')}\n")
            f.write(f"Importance: {item.get('importance', 'normal')}\n")
            f.write(f"\n--- CONTENT PREVIEW (first 500 chars) ---\n")
            f.write(formatted_message[:500])
            if len(formatted_message) > 500:
                f.write("\n... [truncated]")
            f.write("\n")
            
            with open(STAGING_LINKS_FILE, "a", encoding="utf-8") as lf:
                lf.write(final_link + "\n")
        
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"Total posts in this run: {len(items)}\n")
        f.write("=" * 60 + "\n")
    
    logger.info(f"Preview payload saved to: {output_file}")
    return output_file


def run_regular_preview():
    if not STAGING_MODE:
        logger.warning("STAGING_MODE not enabled - this should only run in staging!")
    
    logger.info("=== Staging Regular Preview Mode ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    ensure_staging_output_dir()
    init_db()
    
    pending_count = get_all_pending_count()
    logger.info(f"Queue size: {pending_count} pending items")
    
    pending = get_pending_news(min(25, pending_count))
    
    if not pending:
        logger.info("No pending posts to preview")
        return
    
    logger.info(f"Loaded candidate items: {len(pending)}")
    
    eval_results = []
    for item in pending:
        result = evaluate_item_relevance(item)
        eval_results.append((item, result))
    
    passed_items = []
    rejected_items = []
    
    for item, result in eval_results:
        if result["passed"]:
            passed_items.append(item)
        else:
            rejected_items.append((item, result))
    
    logger.info(f"Hard gate passed: {len(passed_items)}, rejected: {len(rejected_items)}")
    
    if not passed_items:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(STAGING_OUTPUT_DIR, f"preview_regular_{timestamp}.txt")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(f"RELEVANCE GATE REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            f.write("=== REJECTED CANDIDATES ===\n\n")
            for item, result in rejected_items:
                f.write(f"Domain: {result['domain']}\n")
                f.write(f"Title: {result['title']}\n")
                f.write(f"Score: {result['score']}\n")
                f.write(f"Reasons:\n")
                for reason in result["reasons"]:
                    f.write(f"  - {reason}\n")
                f.write("\n" + "-" * 40 + "\n\n")
            
            f.write("RESULT: NO PASSED CANDIDATES\n")
            f.write("Better to skip slot than publish garbage.\n")
        
        logger.warning(f"No items passed hard relevance gate - slot skipped")
        logger.info(f"Preview (debug only) saved to: {output_file}")
        return
    
    MAX_POSTS_PER_RUN = 2
    
    candidate_pool_size = MAX_POSTS_PER_RUN * 4
    candidates = select_best_items_for_publishing(passed_items, candidate_pool_size)
    
    if not candidates:
        logger.warning("No items selected for publishing after LLM filtering")
        return
    
    filtered_candidates = filter_non_forum_links(candidates)
    logger.info(f"Candidates after forum dedupe: {len(filtered_candidates)} (was {len(candidates)})")
    
    selected = filtered_candidates[:MAX_POSTS_PER_RUN]
    logger.info(f"Selected items for preview: {len(selected)}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(STAGING_OUTPUT_DIR, f"preview_regular_{timestamp}.txt")
    
    save_preview_payload(selected, output_file, eval_results)
    logger.info(f"=== Staging Preview finished. Output: {output_file} ===")


if __name__ == "__main__":
    run_regular_preview()