#!/usr/bin/env python3
"""
Preview script for EXA shadow/merge pipeline.
Demonstrates how EXA candidates would merge with RSS candidates.
No DB writes, no MAX API calls, no publishing.
"""

import os
import sys
import logging
from exa_queries import ALL_QUERIES, QUERY_GROUPS
from exa_collector import search_exa_multi
from merge_candidates import merge_and_dedup, filter_exa_items

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("EXA Shadow Merge Preview")
    print("=" * 60)
    
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        print("\nWARNING: EXA_API_KEY not set - EXA search will be skipped")
        exa_items = []
    else:
        print(f"\nUsing queries from exa_queries.py")
        print(f"Total queries available: {len(ALL_QUERIES)}")
        
        sample_queries = [
            "Ozon sellers news Russia 2024",
            "Wildberries комиссия тарифы",
            "маркетплейсы штрафы регулирование",
            "Ozon логистика доставка",
            "маркетплейс налогообложение селлеры",
        ]
        
        print(f"\nRunning EXA search with {len(sample_queries)} sample queries...")
        exa_items = search_exa_multi(sample_queries)
    
    print(f"\nEXA items found: {len(exa_items)}")
    
    rss_items = []
    print(f"\nRSS items: {len(rss_items)} (read-only mode - existing collector not touched)")
    print("Note: In full integration, RSS items would come from existing collector")
    
    print("\n--- Running merge + dedup ---")
    merged = merge_and_dedup(rss_items, exa_items)
    
    print(f"\nAfter dedup: {len(merged)} items")
    
    limited = filter_exa_items(merged, max_exa=2)
    print(f"After EXA limit (max 2): {len(limited)} items")
    
    print("\n" + "=" * 60)
    print("TOP CANDIDATES")
    print("=" * 60)
    
    for i, item in enumerate(limited[:10], 1):
        source = item.get('source_type', 'unknown')
        title = item.get('title', 'No title')[:70]
        link = item.get('link', 'No link')[:50]
        published = item.get('published_at', 'N/A')
        query = item.get('query', '')[:30]
        
        print(f"\n{i}. [{source.upper()}] {title}")
        print(f"   Link: {link}")
        print(f"   Published: {published}")
        if query:
            print(f"   Query: {query}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"EXA items found: {len(exa_items)}")
    print(f"After merge+dedup: {len(merged)}")
    print(f"Final (EXA limited to 2): {len(limited)}")
    print("\nThis is SHADOW mode - no publishing, no DB writes, no MAX API calls")


if __name__ == "__main__":
    main()
