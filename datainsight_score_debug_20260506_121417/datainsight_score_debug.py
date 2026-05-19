#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import copy
sys.path.insert(0, "/opt/newsbot_v2")

from parsers import fetch_rss_feed
from scoring import score_items
from collector_v2 import seller_score
from seller_filter import evaluate_item as evaluate_seller_filter_item

URL = "https://datainsight.ru/rss.xml"
SOURCE = "Data Insight"

feed = fetch_rss_feed(URL, SOURCE)

print("feed entries:", len(feed.entries))
print()

items = []

for idx, e in enumerate(feed.entries, 1):
    title = getattr(e, "title", "") or ""
    summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
    link = getattr(e, "link", "") or ""
    published = getattr(e, "published", "") or getattr(e, "updated", "") or ""

    item = {
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
    }
    items.append(item)

    print("=" * 120)
    print("RAW ITEM", idx)
    print("title:", title)
    print("link:", link)
    print("published:", published)
    print("summary_len:", len(summary))
    print("collector_seller_score:", seller_score(item))

    try:
        sf = evaluate_seller_filter_item(item)
        print("seller_filter:", sf)
    except Exception as ex:
        print("seller_filter_error:", repr(ex))

print()
print("=" * 120)
print("BEFORE score_items:", len(items))

try:
    scored = score_items(copy.deepcopy(items))
    print("AFTER score_items:", len(scored))
    for i, item in enumerate(scored, 1):
        print("-" * 120)
        print("SCORED", i)
        print("title:", item.get("title"))
        print("score:", item.get("score"))
        print("source:", item.get("source"))
        print("published_at:", item.get("published_at"))
except Exception as e:
    print("score_items ERROR:", repr(e))

print()
print("=" * 120)
print("DIRECT ROUTING WITHOUT score_items, FOR UNDERSTANDING ONLY")
for i, item in enumerate(items, 1):
    kw = seller_score(item)
    if kw >= 3:
        route = "publish"
    elif kw >= 1:
        route = "digest"
    else:
        route = "drop"
    print(f"{i}. kw={kw} route={route} | {item.get('title')}")
