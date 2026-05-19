#!/usr/bin/env python3
import logging
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("official_sources_v2")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsBotV2/1.0)"
}

SOURCES = [
    {
        "name": "Яндекс Маркет для продавцов",
        "url": "https://partner.market.yandex.ru/chtojournal/category/novosti-marketa/",
        "base": "https://partner.market.yandex.ru",
    },
    {
        "name": "WB Partners справка",
        "url": "https://seller.wildberries.ru/instructions/ru/ru/material/portal-news",
        "base": "https://seller.wildberries.ru",
    },
]


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    # Некоторые страницы отдают HTML без корректной кодировки в headers.
    # Принудительно читаем как UTF-8, иначе получаем кракозябры вида ÐÐµÐ...
    r.encoding = "utf-8"
    return r.text or ""


def extract_links_from_page(source: Dict, limit: int = 20) -> List[Dict]:
    url = source["url"]
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a"):
        title = clean_text(a.get_text(" ", strip=True))
        href = a.get("href") or ""

        if not title or len(title) < 20:
            continue

        full_url = urljoin(source["base"], href)

        # грубая отсечка мусора
        low = title.lower()
        href_low = href.lower()
        full_low = full_url.lower()

        if any(x in low for x in ["войти", "регистрация", "cookie", "поддержка", "личный кабинет"]):
            continue

        # Яндекс: убираем разделы, теги, welcome-страницы и футер.
        # Нам нужны именно материалы журнала, а не навигация.
        if source["name"].startswith("Яндекс"):
            if "/chtojournal/" not in full_low:
                continue
            if "/category/" in full_low or "/tag/" in full_low:
                continue
            if "/welcome/" in full_low:
                continue

        # WB: пока берём только справочные материалы, не навигацию.
        if source["name"].startswith("WB"):
            if "/instructions/" not in full_low or "/material/" not in full_low:
                continue

        if full_url in seen:
            continue

        seen.add(full_url)

        items.append({
            "title": title[:250],
            "description": title,
            "summary": title,
            "raw_text": title,
            "link": full_url,
            "source": source["name"],
            "category": "official_marketplace_news",
            "importance": "normal",
            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        if len(items) >= limit:
            break

    return items


def get_official_news(limit_per_source: int = 20) -> List[Dict]:
    all_items = []

    for source in SOURCES:
        try:
            items = extract_links_from_page(source, limit=limit_per_source)
            logger.info("Official source [%s]: %s items", source["name"], len(items))
            all_items.extend(items)
        except Exception as e:
            logger.warning("Official source [%s] failed: %s", source["name"], e)

    return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    items = get_official_news()
    print("TOTAL:", len(items))
    for item in items[:30]:
        print("-", item["source"], "|", item["title"], "|", item["link"])
