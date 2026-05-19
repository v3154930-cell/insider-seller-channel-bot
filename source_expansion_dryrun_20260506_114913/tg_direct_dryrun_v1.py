#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import sqlite3
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/opt/newsbot_v2")

from telegram_sources_v2 import fetch_tg_channel_public
from seller_filter import evaluate_item as evaluate_seller_filter_item

NEWS_DB = Path("/opt/newsbot_v2/news_queue.db")

# Кандидаты НЕ пишутся в базу. Это только проверка доступности и качества.
# Часть может не существовать или не открываться через t.me/s — это нормально.
CANDIDATE_CHANNELS = [
    # Уже известные / контрольные
    "marketplace_biz",
    "mpgo_ru",
    "oborotru",
    "crmmarketplace",
    "Apetecom",

    # Кандидаты для расширения обычной новостной ленты
    "sellerden",
    "SellerDen",
    "marketplaceguru",
    "marketplace_guru",
    "mpstats",
    "mpstats_io",
    "moneyplace",
    "new_retail",
    "retailru",
    "e_pepper",
    "epepper",
    "akit_ru",
    "datainsight",
    "data_insight",
    "moysklad",
    "kontur_market",
    "selsup",
    "modulbank_business",
]

def norm(s):
    return (s or "").strip()

def clean_text(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def get_existing_sources():
    if not NEWS_DB.exists():
        return set(), set()

    conn = sqlite3.connect(str(NEWS_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sources = set()
    links = set()

    try:
        for r in cur.execute("SELECT DISTINCT source FROM news WHERE source IS NOT NULL"):
            sources.add(r["source"])
    except Exception:
        pass

    try:
        for r in cur.execute("SELECT link FROM news WHERE link IS NOT NULL AND link != ''"):
            links.add(r["link"])
    except Exception:
        pass

    conn.close()
    return sources, links

def simple_keyword_score(item):
    text = " ".join([
        str(item.get("title") or ""),
        str(item.get("description") or ""),
        str(item.get("raw_text") or ""),
        str(item.get("source") or ""),
    ]).lower().replace("ё", "е")

    good = [
        "ozon", "озон",
        "wildberries", "вайлдберриз", "wb",
        "яндекс маркет", "маркет",
        "маркетплейс", "селлер", "продавец",
        "комиссия", "тариф", "оферта", "штраф",
        "возврат", "логистика", "фулфилмент", "склад",
        "fbo", "fbs", "dbs", "пвз",
        "выплаты", "налог", "ндс",
        "маркировка", "честный знак", "фас",
        "e-commerce", "ecommerce", "онлайн-торговля",
    ]
    bad = [
        "porsche", "bugatti", "футбол", "хоккей", "теннис",
        "илон маск", "openai", "политика",
    ]

    if any(x in text for x in bad):
        return -100

    return sum(1 for x in good if x in text)

def main():
    existing_sources, existing_links = get_existing_sources()

    print("TG DIRECT DRY RUN")
    print("DB:", NEWS_DB)
    print("existing sources in news:", ", ".join(sorted(existing_sources)) or "none")
    print()

    summary = []

    for channel in CANDIDATE_CHANNELS:
        print("=" * 120)
        print("CHANNEL:", channel)
        print("-" * 120)

        try:
            posts = fetch_tg_channel_public(channel, limit=8)
        except Exception as e:
            print("FETCH_ERROR:", repr(e))
            summary.append((channel, "error", 0, 0, 0, str(e)[:120]))
            continue

        print("posts fetched:", len(posts))

        if not posts:
            summary.append((channel, "empty", 0, 0, 0, "no posts"))
            continue

        publish_like = 0
        digest_like = 0
        drop_like = 0
        duplicate_links = 0

        for i, item in enumerate(posts[:8], 1):
            item = dict(item)
            item["source"] = f"TG:{channel}"

            link = item.get("link") or ""
            if link in existing_links:
                duplicate_links += 1

            kw_score = simple_keyword_score(item)

            try:
                sf = evaluate_seller_filter_item(item)
                decision = sf.get("decision")
                rel = sf.get("seller_relevance_score")
                act = sf.get("actionability_score")
                reason = sf.get("reason")
            except Exception as e:
                decision = "filter_error"
                rel = ""
                act = ""
                reason = repr(e)

            if kw_score >= 3:
                publish_like += 1
            elif kw_score >= 1:
                digest_like += 1
            else:
                drop_like += 1

            title = clean_text(item.get("title") or item.get("description") or item.get("raw_text") or "")[:220]

            print(f"{i:02d}. kw_score={kw_score} seller_filter={decision} rel={rel} act={act}")
            print("    title:", title)
            print("    link:", link)
            print("    reason:", clean_text(str(reason))[:220])

        status = "candidate"
        if publish_like + digest_like == 0:
            status = "weak"
        if duplicate_links >= max(2, len(posts) // 2):
            status = "duplicate_or_already_covered"

        summary.append((channel, status, len(posts), publish_like, digest_like, f"duplicates={duplicate_links}"))

    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print("channel | status | fetched | publish_like | digest_like | notes")
    for row in summary:
        print(" | ".join(map(str, row)))

if __name__ == "__main__":
    main()
