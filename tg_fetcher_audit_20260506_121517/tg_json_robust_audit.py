#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
from collections import Counter
from urllib.parse import urlparse

urls = [x.strip() for x in os.getenv("TG_JSON_URLS", "").split(",") if x.strip()]

print("TG_JSON_URLS count:", len(urls))

for idx, url in enumerate(urls, 1):
    parsed = urlparse(url)
    safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    print()
    print("=" * 120)
    print(f"{idx}. {safe_url}")
    print("=" * 120)

    try:
        r = requests.get(url, timeout=30)
        print("HTTP:", r.status_code)
        print("content-type:", r.headers.get("content-type"))
        print("bytes:", len(r.content))

        r.raise_for_status()
        data = r.json()

        print("json_type:", type(data).__name__)

        if isinstance(data, dict):
            items = data.get("items") or data.get("posts") or []
            print("dict_keys:", list(data.keys()))
        elif isinstance(data, list):
            items = data
        else:
            items = []

        print("items_total:", len(items))

        by_source = Counter()
        by_channel = Counter()

        for x in items:
            if not isinstance(x, dict):
                continue
            by_source[x.get("source") or "unknown"] += 1
            by_channel[x.get("channel") or "unknown"] += 1

        print()
        print("--- by source ---")
        for src, cnt in by_source.most_common(50):
            print(f"{cnt:>5} | {src}")

        print()
        print("--- by channel ---")
        for ch, cnt in by_channel.most_common(50):
            print(f"{cnt:>5} | {ch}")

        print()
        print("--- first 20 items ---")
        for i, x in enumerate(items[:20], 1):
            if not isinstance(x, dict):
                print(i, type(x).__name__, str(x)[:120])
                continue

            title = x.get("title") or x.get("text") or x.get("description") or ""
            print(f"{i:02d}. source={x.get('source')} channel={x.get('channel')} published={x.get('published_at')}")
            print("    title:", str(title).replace("\n", " ")[:180])
            print("    link:", x.get("link") or x.get("url"))

        print()
        print("--- last 20 items ---")
        for i, x in enumerate(items[-20:], 1):
            if not isinstance(x, dict):
                print(i, type(x).__name__, str(x)[:120])
                continue

            title = x.get("title") or x.get("text") or x.get("description") or ""
            print(f"{i:02d}. source={x.get('source')} channel={x.get('channel')} published={x.get('published_at')}")
            print("    title:", str(title).replace("\n", " ")[:180])
            print("    link:", x.get("link") or x.get("url"))

    except Exception as e:
        print("ERROR:", repr(e))
