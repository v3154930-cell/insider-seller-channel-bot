"""
EXA adapter for digest pipeline.
Provides EXA candidates for morning/final digest with soft rollout.
"""

import os
import logging
from typing import List, Dict, Optional

from config import (
    ENABLE_EXA,
    ENABLE_EXA_IN_DIGEST,
    EXA_MAX_ITEMS_PER_QUERY,
    EXA_MAX_TOTAL_ITEMS,
    EXA_MAX_ITEMS_FOR_DIGEST,
)
from exa_queries import ALL_QUERIES
from exa_collector import search_exa_multi
from merge_candidates import merge_and_dedup, filter_exa_items

logger = logging.getLogger(__name__)


def is_exa_enabled_for_digest() -> bool:
    """Check if EXA is enabled for digest integration."""
    if not ENABLE_EXA:
        logger.info("EXA disabled globally (ENABLE_EXA=false)")
        return False
    if not ENABLE_EXA_IN_DIGEST:
        logger.info("EXA disabled for digest (ENABLE_EXA_IN_DIGEST=false)")
        return False
    return True


def get_exa_candidates_for_digest(
    rss_items: List[Dict],
    max_exa_items: Optional[int] = None,
    queries: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Get EXA candidates merged with RSS items for digest.
    
    Args:
        rss_items: Existing RSS digest candidates
        max_exa_items: Max EXA items to include (default from config)
        queries: Optional custom queries list
    
    Returns:
        Merged and deduplicated candidate list with EXA items included.
    """
    if not is_exa_enabled_for_digest():
        logger.info("EXA not enabled for digest, returning RSS items only")
        return rss_items
    
    if max_exa_items is None:
        max_exa_items = EXA_MAX_ITEMS_FOR_DIGEST
    
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        logger.warning("EXA_API_KEY not set, falling back to RSS items only")
        return rss_items
    
    if queries is None:
        queries = _get_digest_queries()
    
    try:
        exa_items = search_exa_multi(
            queries=queries,
            max_per_query=EXA_MAX_ITEMS_PER_QUERY,
            max_total=EXA_MAX_TOTAL_ITEMS,
        )
        logger.info(f"EXA candidates retrieved: {len(exa_items)}")
    except Exception as e:
        logger.warning(f"EXA search failed: {e}, falling back to RSS items only")
        return rss_items
    
    if not exa_items:
        logger.info("EXA returned empty results, using RSS items only")
        return rss_items
    
    merged = merge_and_dedup(rss_items, exa_items)
    
    limited = filter_exa_items(merged, max_exa=max_exa_items)
    
    exa_count = sum(1 for i in limited if i.get("source_type") == "exa")
    rss_count = sum(1 for i in limited if i.get("source_type") != "exa")
    logger.info(f"Digest candidates: {rss_count} RSS + {exa_count} EXA = {len(limited)} total")
    
    return limited


def _get_digest_queries() -> List[str]:
    """Get queries optimized for digest content."""
    return [
        "Ozon sellers news Russia 2024",
        "Wildberries комиссия тарифы",
        "маркетплейсы штрафы изменение правил",
        "Ozon логистика доставка",
        "маркетплейс налогообложение селлеры",
    ]


def get_exa_candidates_only(
    queries: Optional[List[str]] = None,
    max_total: Optional[int] = None,
) -> List[Dict]:
    """
    Get only EXA candidates without merging with RSS.
    Useful for preview/testing.
    
    Args:
        queries: Optional custom queries list
        max_total: Optional max total items
    
    Returns:
        List of EXA news items in unified format.
    """
    if not ENABLE_EXA:
        logger.info("EXA disabled globally")
        return []
    
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        logger.warning("EXA_API_KEY not set")
        return []
    
    if queries is None:
        queries = _get_digest_queries()
    
    if max_total is None:
        max_total = EXA_MAX_TOTAL_ITEMS
    
    try:
        items = search_exa_multi(
            queries=queries,
            max_per_query=EXA_MAX_ITEMS_PER_QUERY,
            max_total=max_total,
        )
        logger.info(f"EXA candidates (standalone): {len(items)}")
        return items
    except Exception as e:
        logger.warning(f"EXA search failed: {e}")
        return []


def get_digest_preview(
    rss_items: List[Dict],
    with_exa: bool = True,
) -> Dict[str, object]:
    """
    Get digest preview showing difference between with/without EXA.
    
    Args:
        rss_items: Existing RSS digest candidates
        with_exa: Whether to include EXA candidates
    
    Returns:
        Dict with preview data including counts and top items.
    """
    result: Dict[str, object] = {
        "without_exa": {
            "count": len(rss_items),
            "items": rss_items[:10],
        },
        "with_exa": None,
        "difference": None,
    }
    
    if with_exa:
        merged = get_exa_candidates_for_digest(rss_items)
        result["with_exa"] = {
            "count": len(merged),
            "items": merged[:10],
        }
        result["difference"] = len(merged) - len(rss_items)
    
    return result
