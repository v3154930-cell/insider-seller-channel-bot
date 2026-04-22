#!/usr/bin/env python3
"""Preview script for URL fix - shows before/after link selection."""
import sys

def get_item_url(item):
    """Safely get news URL with fallback chain."""
    return item.get('url') or item.get('link', '')

test_items = [
    {"title": "Ozon снизил комиссию", "link": "https://retail.ru/news", "url": "https://retail.ru/news/ozon-commission", "source": "rss"},
    {"title": "WB новый тариф", "link": "https://oborot.ru/tariffs", "url": "", "source": "rss"},
    {"title": "EXA article", "link": "", "url": "https://example.com/article/123", "source": "exa"},
    {"title": "Legacy item", "link": "https://old-source.com/item", "source": "rss"},
]

output = []
output.append("=" * 60)
output.append("URL FIX PREVIEW")
output.append("=" * 60)
output.append("")

for i, item in enumerate(test_items, 1):
    old_link = item.get('link', '')
    new_link = get_item_url(item)
    
    output.append(f"{i}. {item['title'][:40]}")
    output.append(f"   OLD (item.get link):  {old_link}")
    output.append(f"   NEW (get_item_url):  {new_link}")
    output.append(f"   Source: {item.get('source', 'N/A')}")
    output.append("")

output.append("=" * 60)
output.append("Summary:")
output.append("- If 'url' field exists -> use it (better for EXA)")
output.append("- Otherwise fallback to 'link' (RSS fallback)")
output.append("- If both empty -> empty string")
output.append("=" * 60)
output.append("")
output.append("This is PREVIEW only - no changes made, no DB writes")

with open('preview_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))