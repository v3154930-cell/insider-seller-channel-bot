#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, "/opt/newsbot_v2")

from telegram_json_sources_v2 import fetch_telegram_json

urls = [x.strip() for x in os.getenv("TG_JSON_URLS", "").split(",") if x.strip()]

print("TG_JSON_URLS count:", len(urls))

for idx, url in enumerate(urls, 1):
    parsed = urlparse(url)
    safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    print()
    print("=" * 100)
    print(idx, safe_url)

    try:
        items = fetch_telegram_json(url, limit=20)
        print("items:", len(items))

        sources = {}
        for item in items:
            src = item.get("source") or "unknown"
            sources[src] = sources.get(src, 0) + 1

        print("sources:", sources)

        for item in items[:5]:
            print("-", item.get("source"), "|", str(item.get("title") or "")[:160])
    except Exception as e:
        print("ERROR:", repr(e))
