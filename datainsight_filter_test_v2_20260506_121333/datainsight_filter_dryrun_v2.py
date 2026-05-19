#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.insert(0, "/opt/newsbot_v2")

from parsers import fetch_rss_feed
from seller_filter import evaluate_item as evaluate_seller_filter_item
from scoring import score_items
from collector_v2 import seller_score

URL = "https://datainsight.ru/rss.xml"
SOURCE = "Data Insight"

feed = fetch_rss_feed(URL, SOURCE)

print("feed entries:", len(feed.entries))
print("feed bozo:", getattr(feed, "bozo", None))
if getattr(feed, "bozo", False):
    print("bozo_exception:", getattr(feed, "bozo_exception", ""))

items = []

for e in feed.entries:
    title = getattr(e, "title", "") or ""
    summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
    link = getattr(e, "link", "") or ""
    published = getattr(e, "published", "") or getattr(e, "updated", "") or ""

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

print()
print("Data Insight normalized items:", len(items))
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

    print("=" * 120)
    print(f"{i}. kw_score={kw_score} scoring_score={item.get('score', '')}")
    print("seller_filter_decision:", sf.get("decision"))
    print("seller_relevance_score:", sf.get("seller_relevance_score"))
    print("actionability_score:", sf.get("actionability_score"))
    print("reason:", sf.get("reason"))
    print("title:", str(item.get("title") or "")[:220])
    print("link:", item.get("link") or "")
