#!/usr/bin/env python3
"""Preview-only resolver - writes to file"""
import sys

# Use minimal test without network
test_items = [
    {"link": "https://www.retail.ru/news/ozon-test/", "expected": "likely_direct"},
    {"link": "https://www.retail.ru/rss/news/", "expected": "listing"},
    {"link": "https://oborot.ru/feed/", "expected": "listing"},
]

output = []
output.append("=" * 60)
output.append("RSS RESOLVER PREVIEW TEST")
output.append("=" * 60)
output.append("")

output.append("Testing items in memory (no network):")
output.append("")

for item in test_items:
    link = item['link']
    parsed = __import__('urllib.parse', fromlist=['urlparse']).urlparse(link)
    path = parsed.path.lower()
    
    # Simple heuristic check
    is_direct = '/news/' in path and '/rss' not in path
    result = "DIRECT" if is_direct else "NEEDS_RESOLUTION"
    
    output.append(f"Link: {link}")
    output.append(f"  Path: {path}")
    output.append(f"  Result: {result}")
    output.append("")

output.append("=" * 60)
output.append("Full extraction requires network - see preview_rss_resolver.py")
output.append("=" * 60)

with open('rss_resolver_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))