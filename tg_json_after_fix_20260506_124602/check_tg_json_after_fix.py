#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

urls = [x.strip() for x in os.getenv("TG_JSON_URLS", "").split(",") if x.strip()]
now = datetime.now(timezone.utc)

print("now_utc:", now.isoformat())
print("TG_JSON_URLS:", len(urls))

for url in urls:
    parsed = urlparse(url)
    safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    print("=" * 120)
    print("URL:", safe_url)

    r = requests.get(url, timeout=30)
    print("HTTP:", r.status_code)
    print("bytes:", len(r.content))
    r.raise_for_status()

    data = r.json()

    print("generated_at:", data.get("generated_at"))
    print("count:", data.get("count"))
    print("channels:", data.get("channels"))
    print("per_channel_limit:", data.get("per_channel_limit"))
    print("total_limit:", data.get("total_limit"))

    items = data.get("items") or []
    print("items_total:", len(items))

    by_source = Counter(x.get("source") or "unknown" for x in items)
    by_channel = Counter(x.get("channel") or "unknown" for x in items)

    print()
    print("--- by source ---")
    for k, v in by_source.most_common():
        print(f"{v:>4} | {k}")

    print()
    print("--- freshness by channel ---")
    rows = defaultdict(list)
    for item in items:
        rows[item.get("channel") or "unknown"].append(item)

    for ch, ch_items in sorted(rows.items()):
        dts = [parse_dt(x.get("published_at")) for x in ch_items]
        dts = [x for x in dts if x]

        fresh24 = sum(1 for x in dts if x >= now - timedelta(hours=24))
        fresh48 = sum(1 for x in dts if x >= now - timedelta(hours=48))
        fresh72 = sum(1 for x in dts if x >= now - timedelta(hours=72))

        newest = max(dts).isoformat() if dts else ""
        oldest = min(dts).isoformat() if dts else ""

        print(f"{ch:20} total={len(ch_items):>3} fresh24={fresh24:>2} fresh48={fresh48:>2} fresh72={fresh72:>2} oldest={oldest} newest={newest}")

    print()
    print("--- first 30 items ---")
    for i, item in enumerate(items[:30], 1):
        title = item.get("title") or item.get("description") or ""
        print(f"{i:02d}. {item.get('source')} | {item.get('published_at')} | {str(title)[:160]} | {item.get('link')}")

