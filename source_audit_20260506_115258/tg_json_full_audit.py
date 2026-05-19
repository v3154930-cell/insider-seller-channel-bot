#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, "/opt/newsbot_v2")

from telegram_json_sources_v2 import fetch_telegram_json

urls = [x.strip() for x in os.getenv("TG_JSON_URLS", "").split(",") if x.strip()]

print("TG_JSON_URLS count:", len(urls))

for idx, url in enumerate(urls, 1):
    parsed = urlparse(url)
    safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    print()
    print("=" * 120)
    print(f"{idx}. {safe_url}")
    print("=" * 120)

    items = fetch_telegram_json(url, limit=10000)
    print("items_total:", len(items))

    by_source = Counter((x.get("source") or x.get("channel") or "unknown") for x in items)

    print()
    print("--- sources distribution ---")
    for src, cnt in by_source.most_common():
        print(f"{cnt:>5} | {src}")

    print()
    print("--- last/sample 5 by original order ---")
    for item in items[:5]:
        print("-", item.get("source"), "|", str(item.get("title") or "")[:180], "|", item.get("link"))

    print()
    print("--- tail/sample 5 ---")
    for item in items[-5:]:
        print("-", item.get("source"), "|", str(item.get("title") or "")[:180], "|", item.get("link"))
