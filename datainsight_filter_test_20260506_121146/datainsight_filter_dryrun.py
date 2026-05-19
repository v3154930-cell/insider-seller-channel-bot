#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import feedparser
import requests

sys.path.insert(0, "/opt/newsbot_v2")

from seller_filter import evaluate_item as evaluate_seller_filter_item
from scoring import score_items
from collector_v2 import seller_score

URL = "https://datainsight.ru/rss.xml"
SOURCE = "Data Insight"

headers = {
    "User-Agent": "Mozilla/5.0 InsiderSellerBot/1.0"
}

resp = requests.get(URL, headers=headers, timeout=15)
resp.raise_for_status()

feed = feedparser.parse(resp.content)

items = []
for e in feed.entries:
    title = getattr(e, "title", "") or ""
    summary = getattr(e, "summary", "") or ""
    link = getattr(e, "link", "") or ""
    published = getattr(e, "published", "") or ""

    items.append({
        "title": title,
        "description": summary,
        "summary": summary,
        "raw_text": summary,
        "link": link,
        "url": link,
        "source": SOURCE,
        "published_at": published,
        "category": "marketplace",
        "importance": "normal",
    })

try:
    items = score_items(items)
except Exception as e:
    print("scoring failed:", repr(e))

print("Data Insight items:", len(items))
print()

for i, item in enumerate(items, 1):
    kw_score = seller_score(item)

    try:
        sf = evaluate_seller_filter_item(item)
    except Exception as e:
        sf = {
            "decision": "filter_error",
            "seller_relevance_score": "",
            "actionability_score": "",
            "reason": repr(e),
        }

    title = str(item.get("title") or "")[:220]
    link = item.get("link") or ""
    score = item.get("score", "")

    print("=" * 120)
    print(f"{i}. kw_score={kw_score} scoring_score={score}")
    print("seller_filter_decision:", sf.get("decision"))
    print("seller_relevance_score:", sf.get("seller_relevance_score"))
    print("actionability_score:", sf.get("actionability_score"))
    print("reason:", sf.get("reason"))
    print("title:", title)
    print("link:", link)
