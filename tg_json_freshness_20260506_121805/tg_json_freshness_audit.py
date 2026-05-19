#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from urllib.parse import urlparse

DB = "/opt/newsbot_v2/news_queue.db"

def parse_dt(value):
    if not value:
        return None
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None

def load_existing_links():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT link FROM news
        WHERE link IS NOT NULL AND link != ''
    """).fetchall()
    conn.close()
    return {r[0] for r in rows}

urls = [x.strip() for x in os.getenv("TG_JSON_URLS", "").split(",") if x.strip()]
existing_links = load_existing_links()

now = datetime.now(timezone.utc)

print("now_utc:", now.isoformat())
print("TG_JSON_URLS:", len(urls))
print("existing_links:", len(existing_links))
print()

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
    print("declared_count:", data.get("count"))

    items = data.get("items") or []
    print("items_total:", len(items))
    print()

    by_channel = defaultdict(list)

    for item in items:
        channel = item.get("channel") or item.get("source") or "unknown"
        dt = parse_dt(item.get("published_at"))
        link = item.get("link") or item.get("url") or ""
        by_channel[channel].append((dt, link, item))

    print("--- CHANNEL FRESHNESS ---")
    for channel, rows in sorted(by_channel.items()):
        dates = [dt for dt, link, item in rows if dt]
        newest = max(dates).isoformat() if dates else ""
        oldest = min(dates).isoformat() if dates else ""

        fresh_24 = sum(1 for dt, link, item in rows if dt and dt >= now - timedelta(hours=24))
        fresh_48 = sum(1 for dt, link, item in rows if dt and dt >= now - timedelta(hours=48))
        fresh_72 = sum(1 for dt, link, item in rows if dt and dt >= now - timedelta(hours=72))
        already = sum(1 for dt, link, item in rows if link in existing_links)

        print(
            f"{channel:20} total={len(rows):>3} "
            f"fresh24={fresh_24:>2} fresh48={fresh_48:>2} fresh72={fresh_72:>2} "
            f"already_in_news={already:>2} "
            f"oldest={oldest} newest={newest}"
        )

    print()
    print("--- ITEMS NOT YET IN NEWS ---")
    fresh_new = []
    for item in items:
        dt = parse_dt(item.get("published_at"))
        link = item.get("link") or item.get("url") or ""
        if link not in existing_links:
            fresh_new.append((dt, item))

    fresh_new.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    for dt, item in fresh_new[:30]:
        title = item.get("title") or item.get("text") or item.get("description") or ""
        print(
            f"{item.get('source')} | {item.get('published_at')} | "
            f"{str(title).replace(chr(10), ' ')[:160]} | {item.get('link')}"
        )

    print()
    print("--- ITEMS WITH EMPTY published_at ---")
    for item in items:
        if not item.get("published_at"):
            title = item.get("title") or item.get("text") or item.get("description") or ""
            print(
                f"{item.get('source')} | channel={item.get('channel')} | "
                f"{str(title).replace(chr(10), ' ')[:160]} | {item.get('link')}"
            )
