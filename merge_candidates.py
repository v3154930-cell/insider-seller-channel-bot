"""
Merge candidates from RSS and EXA sources with deduplication.
Provides unified candidate list for digest/publishing pipeline.
"""

import logging
import re
from typing import List, Dict, Set, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, remove punctuation, extra spaces."""
    if not title:
        return ""
    
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def normalize_url(url: str) -> str:
    """Normalize URL: remove trailing slashes, www, query params."""
    if not url:
        return ""
    
    url = url.strip().lower()
    
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            netloc = parsed.netloc
            netloc = netloc.replace('www.', '')
            path = parsed.path.rstrip('/')
            return f"{parsed.scheme}://{netloc}{path}"
    except Exception:
        pass
    
    return url


def dedup_by_link(items: List[Dict]) -> List[Dict]:
    """Deduplicate by normalized URL/link."""
    seen: Set[str] = set()
    result = []
    
    for item in items:
        link = item.get('link', '') or item.get('url', '') or ''
        if not link:
            result.append(item)
            continue
        
        norm_link = normalize_url(link)
        if norm_link not in seen:
            seen.add(norm_link)
            result.append(item)
    
    return result


def dedup_by_title(items: List[Dict]) -> List[Dict]:
    """Deduplicate by normalized title."""
    seen: Set[str] = set()
    result = []
    
    for item in items:
        title = item.get('title', '') or ''
        if not title:
            result.append(item)
            continue
        
        norm_title = normalize_title(title)
        if norm_title and norm_title not in seen:
            seen.add(norm_title)
            result.append(item)
    
    return result


def filter_empty_items(items: List[Dict]) -> List[Dict]:
    """Filter out items that have neither title nor link nor raw_text."""
    result = []
    for item in items:
        title = item.get('title', '') or ''
        link = item.get('link', '') or item.get('url', '') or ''
        raw_text = item.get('raw_text', '') or ''
        
        if title or link or raw_text:
            result.append(item)
    
    return result


def merge_and_dedup(rss_items: List[Dict], exa_items: List[Dict]) -> List[Dict]:
    """
    Merge RSS and EXA candidates with deduplication.
    
    Args:
        rss_items: List of RSS news items
        exa_items: List of EXA news items
    
    Returns:
        Unified list of candidates with deduplication applied.
    """
    all_items = []
    
    for item in rss_items:
        normalized_item = {
            "source_type": item.get("source_type", "rss"),
            "source_name": item.get("source_name", item.get("source", "rss")),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "url": item.get("url", item.get("link", "")),
            "raw_text": item.get("raw_text", item.get("description", "")),
            "snippet": item.get("snippet", item.get("description", "")),
            "published_at": item.get("published_at", item.get("pubDate", "")),
            "query": item.get("query", ""),
            "score": item.get("score"),
            "importance": item.get("importance", "normal"),
        }
        all_items.append(normalized_item)
    
    for item in exa_items:
        normalized_item = {
            "source_type": item.get("source_type", "exa"),
            "source_name": item.get("source_name", "exa"),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "url": item.get("url", ""),
            "raw_text": item.get("raw_text", ""),
            "snippet": item.get("snippet", ""),
            "published_at": item.get("published_at", ""),
            "query": item.get("query", ""),
            "score": item.get("score"),
            "importance": "normal",
        }
        all_items.append(normalized_item)
    
    logger.info(f"Merge: {len(rss_items)} RSS + {len(exa_items)} EXA = {len(all_items)} total")
    
    filtered = filter_empty_items(all_items)
    logger.info(f"After empty filter: {len(filtered)} items")
    
    deduped_link = dedup_by_link(filtered)
    logger.info(f"After link dedup: {len(deduped_link)} items")
    
    deduped_title = dedup_by_title(deduped_link)
    logger.info(f"After title dedup: {len(deduped_title)} items")
    
    return deduped_title


def filter_exa_items(items: List[Dict], max_exa: int = 2) -> List[Dict]:
    """
    Limit number of EXA items in the final list.
    
    Args:
        items: List of merged candidates
        max_exa: Maximum number of EXA items to keep
    
    Returns:
        List with EXA items limited to max_exa count.
    """
    exa_items = [i for i in items if i.get("source_type") == "exa"]
    rss_items = [i for i in items if i.get("source_type") != "exa"]
    
    limited_exa = exa_items[:max_exa]
    
    result = rss_items + limited_exa
    
    logger.info(f"EXA items limited: {len(exa_items)} -> {len(limited_exa)} (max: {max_exa})")
    
    return result
