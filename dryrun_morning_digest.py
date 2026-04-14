#!/usr/bin/env python3
"""
Dry-run test for morning digest with/without EXA.
Demonstrates how EXA integrates into digest pipeline.
No DB writes, no MAX API calls, no publishing.
"""

import os
import sys
import logging
from exa_digest_adapter import get_digest_preview

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("MORNING DIGEST DRY-RUN TEST")
    print("=" * 60)
    
    rss_items = [
        {"title": "Ozon снизил комиссию для новых продавцов", "link": "https://example.com/1", "source": "rss"},
        {"title": "Wildberries запустил новую программу логистики", "link": "https://example.com/2", "source": "rss"},
        {"title": "Новые правила маркировки товаров в 2025", "link": "https://example.com/3", "source": "rss"},
        {"title": "Штрафы за нарушение правил маркетплейсов", "link": "https://example.com/4", "source": "rss"},
    ]
    
    print(f"\n--- RSS items (sample): {len(rss_items)} ---")
    for i, item in enumerate(rss_items, 1):
        print(f"  {i}. {item['title'][:50]}")
    
    print("\n--- Morning Digest WITHOUT EXA ---")
    preview = get_digest_preview(rss_items, with_exa=False)
    print(f"Total candidates: {preview['without_exa']['count']}")
    
    print("\n--- Morning Digest WITH EXA ---")
    print("(If ENABLE_EXA=true and ENABLE_EXA_IN_DIGEST=true)")
    preview_with = get_digest_preview(rss_items, with_exa=True)
    if preview_with["with_exa"]:
        print(f"Total candidates: {preview_with['with_exa']['count']}")
        print(f"Difference: {preview_with['difference']:+d}")
    else:
        print("EXA disabled or not configured")
    
    print("\n" + "=" * 60)
    print("DRY-RUN COMPLETE")
    print("=" * 60)
    print("This is test mode - no DB writes, no MAX API calls")


if __name__ == "__main__":
    main()
