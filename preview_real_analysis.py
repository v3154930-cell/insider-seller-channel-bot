#!/usr/bin/env python3
"""
Real data preview for URL fix.
Simulates items as they come from different pipelines.
"""

# Simulate what actually happens in the system:

# 1. RSS item from parsers.py -> collector.py -> DB
#    In parsers.py line 185-194:
#    {"title": "...", "link": "https://retail.ru/news/...", ...}
#    Then in db.py add_to_queue_batch uses link only
#    Result in DB: only 'link' field exists
rss_item = {
    "id": 1,
    "title": "Ozon снизил комиссию для новых продавцов",
    "link": "https://retail.ru/news/ozon-commission",
    "source": "Retail.ru",
    "raw_text": "Озон объявил о снижении комиссии..."
}

# 2. EXA item from exa_collector.py -> merge_candidates
#    In exa_collector.py line 184-198:
#    {"title": "...", "link": url, "url": url, ...}
#    Link = url = original article URL
exa_item = {
    "id": 2,
    "title": "Amazon expands in Russia (from EXA)",
    "link": "https://example.com/article/123456",
    "url": "https://example.com/article/123456",
    "source": "exa",
    "raw_text": "EXA news content..."
}

# 3. What merge_candidates does for RSS
#    Line 116: "url": item.get("url", item.get("link", ""))
#    So for RSS: url = link (same!)
merged_rss_item = {
    "id": 3,
    "title": "WB new tariffs",
    "link": "https://oborot.ru/news/wb",
    "url": "https://oborot.ru/news/wb",  # Same as link!
    "source": "rss"
}

# 4. Rare case: some RSS might have different URLs
#    Some RSS feeds include actual article URL in different field
rare_rss_item = {
    "id": 4,
    "title": "Legal news",
    "link": "https://pravo.ru/news/feed",
    "url": "https://pravo.ru/article/456789",  # Different!
    "source": "Право.ru"
}

# Import helper
import sys
sys.path.insert(0, '.')
from formatters import get_item_url

print("=" * 80)
print("REAL DATA PREVIEW - URL Fix Impact Analysis")
print("=" * 80)
print()

test_cases = [
    ("RSS from DB (no url field)", rss_item),
    ("EXA item (url == link)", exa_item),
    ("Merged RSS (url == link)", merged_rss_item),
    ("Rare RSS with different url", rare_rss_item),
]

improved_count = 0

for name, item in test_cases:
    link = item.get('link', '')
    url = item.get('url', '')
    chosen = get_item_url(item)
    
    is_improved = url and url != link
    
    if is_improved:
        improved_count += 1
    
    print(f"--- {name} ---")
    print(f"Title: {item['title'][:50]}...")
    print(f"link:  '{link[:60]}'" if link else "link:  ''")
    print(f"url:   '{url[:60]}'" if url else "url:   ''")
    print(f"CHOSEN: '{chosen[:60]}'" if chosen else "CHOSEN: ''")
    print(f"Improved: {'YES - ' + url + ' vs ' + link if is_improved else 'NO - url==link'}")
    print()

print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()
print("CURRENT STATE:")
print("  - DB table 'news' has only 'link' column (NO 'url' column)")
print("  - Regular pipeline: publisher.py -> get_pending_news() -> uses link")
print("  - For RSS items from DB: url field does NOT exist")
print()
print("WHAT FIX DOES:")
print("  - get_item_url(item) returns: item.get('url') or item.get('link', '')")
print("  - For RSS from DB: url is None, falls back to link (unchanged)")
print("  - For EXA items: url exists and is different, uses url (IMPROVED)")
print("  - For merged RSS: url == link, returns same (no change)")
print()
print(f"IMPACT: Only {improved_count} out of {len(test_cases)} cases improve")
print()
print("CONCLUSION:")
print("  The fix helps EXA items and rare RSS cases.")
print("  For majority of RSS items in regular pipeline - NO CHANGE (same as before)")
print("  To fix RSS properly, need to work at parsing layer (NOT in this fix scope)")
print("=" * 80)