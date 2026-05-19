import os
import json
import logging
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)


def fetch_telegram_json(url: str, limit: int = 150) -> List[Dict]:
    url = (url or "").strip()
    if not url:
        return []

    resp = requests.get(url, timeout=20)
    if resp.status_code >= 400:
        logger.warning("TG JSON failed HTTP %s: %s", resp.status_code, url)
        return []

    data = resp.json()

    if isinstance(data, dict):
        items = data.get("items") or data.get("posts") or []
    elif isinstance(data, list):
        items = data
    else:
        return []

    result = []
    for x in items[:limit]:
        text = x.get("description") or x.get("text") or x.get("title") or ""
        link = x.get("link") or x.get("url") or ""

        if not text:
            continue

        title = x.get("title") or text[:140]

        result.append({
            "title": title.strip(),
            "description": text.strip(),
            "link": link,
            "url": link,
            "source": x.get("source") or x.get("channel") or "TG",
            "published_at": x.get("published_at") or "",
            "category": "telegram",
            "importance": "normal",
        })

    return result


def fetch_telegram_json_sources() -> List[Dict]:
    urls = [
        x.strip()
        for x in os.getenv("TG_JSON_URLS", "").split(",")
        if x.strip()
    ]

    try:
        limit = int(os.getenv("TG_JSON_LIMIT", "150"))
    except Exception:
        limit = 150

    all_items = []
    for url in urls:
        try:
            items = fetch_telegram_json(url, limit=limit)
            logger.info("TG JSON [%s]: %s items limit=%s", url, len(items), limit)
            all_items.extend(items)
        except Exception as e:
            logger.warning("TG JSON failed [%s]: %s", url, e)

    return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    items = fetch_telegram_json_sources()
    print("FOUND:", len(items))
    for i, item in enumerate(items[:10], 1):
        print("=" * 80)
        print(i, item.get("source"))
        print(item.get("title"))
        print(item.get("link"))
