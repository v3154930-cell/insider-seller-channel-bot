"""
Exa Collector - Search news via Exa API with daily rate limit.
Supports multi-query search and unified news item format.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

try:
    from exa_py import Exa
except ImportError:
    Exa = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

USAGE_FILE = "exa_usage.json"
MAX_DAILY_REQUESTS = 10

EXA_MAX_ITEMS_PER_QUERY = int(os.getenv("EXA_MAX_ITEMS_PER_QUERY", "5"))
EXA_MAX_TOTAL_ITEMS = int(os.getenv("EXA_MAX_TOTAL_ITEMS", "30"))


def _get_moscow_date() -> str:
    """Get today's date in Moscow timezone as YYYY-MM-DD string."""
    moscow_offset = timedelta(hours=3)
    return datetime.now(timezone(moscow_offset)).strftime("%Y-%m-%d")


def _get_usage() -> Dict[str, int]:
    """Load usage counter from file."""
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_usage(usage: Dict[str, int]) -> None:
    """Save usage counter to file."""
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False)


def _check_limit() -> bool:
    """Check if daily limit is reached. Returns True if can make request."""
    usage = _get_usage()
    today = _get_moscow_date()
    count = usage.get(today, 0)
    if count >= MAX_DAILY_REQUESTS:
        logger.info("EXA skipped: daily limit reached")
        return False
    return True


def _increment_usage() -> None:
    """Increment today's usage counter."""
    usage = _get_usage()
    today = _get_moscow_date()
    usage[today] = usage.get(today, 0) + 1
    _save_usage(usage)


def search_exa(query: str, num_results: int = 10) -> List[Dict]:
    """
    Search news via Exa API with rate limiting.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)
    
    Returns:
        List of news items with keys: title, raw_text, link, source, published_at
        Returns empty list if limit reached or API unavailable.
    """
    api_key = os.getenv("EXA_API_KEY") or os.getenv("EXA_API_TOKEN")
    if not api_key:
        logger.info("EXA skipped: missing EXA_API_KEY (also checked EXA_API_TOKEN)")
        return []
    
    if not _check_limit():
        return []
    
    if Exa is None:
        logger.warning("EXA skipped: exa-py SDK not installed")
        return []
    
    try:
        exa = Exa(api_key)
        results = exa.search(
            query,
            num_results=num_results,
            include_domains=["news", "blog"],
            contents={"highlights": {"num_highlights": 3}}
        )
        
        _increment_usage()
        
        news_items = []
        for item in results.results:
            raw_text = ""
            if hasattr(item, 'highlights') and item.highlights:
                raw_text = "\n\n".join(item.highlights)
            elif hasattr(item, 'text') and item.text:
                raw_text = item.text
            
            snippet = ""
            if hasattr(item, 'highlights') and item.highlights:
                snippet = item.highlights[0] if item.highlights else ""
            
            url = getattr(item, 'url', None) or ""
            link = url
            
            news_items.append({
                "source_type": "exa",
                "source_name": "exa",
                "title": getattr(item, 'title', None) or "",
                "link": link,
                "url": url,
                "raw_text": raw_text,
                "snippet": snippet,
                "published_at": getattr(item, 'published_date', None),
                "query": query,
                "score": getattr(item, 'score', None)
            })
        
        logger.info(f"EXA search ok: {len(news_items)} results")
        return news_items
        
    except Exception as e:
        logger.warning(f"EXA search failed: {e}")
        return []


def search_exa_multi(queries: List[str], max_per_query: Optional[int] = None, max_total: Optional[int] = None) -> List[Dict]:
    """
    Search news via Exa API with multiple queries.
    
    Args:
        queries: List of search query strings
        max_per_query: Maximum results per query (default: from env EXA_MAX_ITEMS_PER_QUERY)
        max_total: Maximum total results (default: from env EXA_MAX_TOTAL_ITEMS)
    
    Returns:
        List of unified news items with all required fields.
    """
    if max_per_query is None:
        max_per_query = EXA_MAX_ITEMS_PER_QUERY
    if max_total is None:
        max_total = EXA_MAX_TOTAL_ITEMS
    
    if not queries:
        logger.info("EXA multi-query: no queries provided")
        return []
    
    all_items = []
    
    for query in queries:
        items = search_exa(query, num_results=max_per_query)
        all_items.extend(items)
        
        if len(all_items) >= max_total:
            all_items = all_items[:max_total]
            break
    
    logger.info(f"EXA multi-query: {len(all_items)} total items (limit: {max_total})")
    return all_items


# Predefined queries for marketplace/e-commerce news
MARKETPLACE_QUERIES = [
    "Ozon sellers news Russia",
    "Wildberries sellers news Russia",
    "marketplace regulation Russia e-commerce",
    "маркетплейсы Россия селлеры новости",
    "Wildberries Ozon комиссия тариф 2024"
]


def get_marketplace_news(query: str = None) -> List[Dict]:
    """
    Search for marketplace/e-commerce news.
    
    Args:
        query: Optional custom query. If None, uses first predefined query.
    
    Returns:
        List of news items from Exa search.
    """
    if query is None:
        query = MARKETPLACE_QUERIES[0]
    return search_exa(query, num_results=10)


if __name__ == "__main__":
    print("EXA Collector - Test Mode")
    print("=" * 40)
    
    for q in MARKETPLACE_QUERIES[:2]:
        print(f"\nQuery: {q}")
        results = search_exa(q, num_results=5)
        print(f"Found: {len(results)} items")
        for r in results:
            print(f"  - {r.get('title', 'No title')[:60]}...")