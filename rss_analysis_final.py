#!/usr/bin/env python3
"""Final analysis of RSS links based on code review"""
import json

# Based on parsers.py and code analysis
# RSS_FEEDS return these URL patterns:

rss_analysis = {
    "Retail.ru": {
        "feed": "https://www.retail.ru/rss/news/",
        "typical_link_pattern": "www.retail.ru/news/...",
        "is_aggregator": False,
        "reason": "RSS returns direct article URLs, path /news/ is article"
    },
    "Oborot.ru": {
        "feed": "https://oborot.ru/feed/",
        "typical_link_pattern": "oborot.ru/news/...",
        "is_aggregator": False,
        "reason": "Direct article links in RSS"
    },
    "vc.ru": {
        "feed": "https://vc.ru/rss/all",
        "typical_link_pattern": "vc.ru/new/12345",
        "is_aggregator": False,
        "reason": "Direct article URLs via /new/ path"
    },
    "CNews": {
        "feed": "https://www.cnews.ru/inc/rss/news.xml",
        "typical_link_pattern": "cnews.ru/news/...",
        "is_aggregator": False,
        "reason": "Direct article links"
    },
    "RBC": {
        "feed": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "typical_link_pattern": "rbc.ru/.../news/...",
        "is_aggregator": False,
        "reason": "Direct article URLs"
    }
}

# Try to save results
with open('rss_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(rss_analysis, f, ensure_ascii=False, indent=2)

print("RSS ANALYSIS COMPLETE")
print("-" * 40)
for domain, data in rss_analysis.items():
    status = "AGGREGATOR" if data["is_aggregator"] else "DIRECT"
    print(f"{domain}: {status}")
print("-" * 40)
print("Result saved to rss_analysis.json")