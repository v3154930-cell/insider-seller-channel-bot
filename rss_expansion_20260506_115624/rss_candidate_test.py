#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import feedparser
import requests
from bs4 import BeautifulSoup

CANDIDATES = [
    # Уже есть — контрольные
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC"),

    # Новые кандидаты
    ("https://rb.ru/feeds/all/", "RB.RU all"),
    ("http://rusbase.com/feeds/all/", "Rusbase old all"),
    ("https://new-retail.ru/rss/", "New Retail"),
    ("https://new-retail.ru/news/rss/", "New Retail news"),
    ("https://e-pepper.ru/news/rss.xml", "E-Pepper"),
    ("https://www.sostav.ru/rss/news.xml", "Sostav"),
    ("https://www.kommersant.ru/RSS/news.xml", "Коммерсантъ news"),
    ("https://www.kommersant.ru/RSS/section-business.xml", "Коммерсантъ business"),
    ("https://www.vedomosti.ru/rss/news", "Ведомости news"),
    ("https://www.vedomosti.ru/rss/rubric/business", "Ведомости business"),
    ("https://www.akit.ru/feed/", "АКИТ"),
    ("https://datainsight.ru/news/feed", "Data Insight feed"),
    ("https://datainsight.ru/rss.xml", "Data Insight rss.xml"),
]

SELLER_WORDS = [
    "маркетплейс", "маркетплейсы", "ozon", "озон",
    "wildberries", "вайлдберриз", "wb",
    "яндекс маркет", "селлер", "продавец", "продавцы",
    "комиссия", "тариф", "оферта", "логистика", "возврат",
    "пвз", "fbo", "fbs", "dbs", "маркировка", "честный знак",
    "e-commerce", "ecommerce", "интернет-торговля", "онлайн-торговля",
]

def fetch(url):
    headers = {"User-Agent": "Mozilla/5.0 InsiderSellerBot/1.0"}
    r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    return r

def score_text(text):
    t = (text or "").lower().replace("ё", "е")
    return sum(1 for w in SELLER_WORDS if w in t)

def main():
    print("RSS CANDIDATE TEST")
    print()

    summary = []

    for url, name in CANDIDATES:
        print("=" * 120)
        print(name)
        print(url)
        print("-" * 120)

        try:
            r = fetch(url)
            print("HTTP:", r.status_code, "final_url:", r.url, "content_type:", r.headers.get("content-type"))

            if r.status_code >= 400:
                summary.append((name, "bad_http", r.status_code, 0, 0, url))
                continue

            feed = feedparser.parse(r.content)

            bozo = bool(getattr(feed, "bozo", False))
            entries = list(getattr(feed, "entries", []) or [])

            print("bozo:", bozo)
            if bozo:
                print("bozo_exception:", str(getattr(feed, "bozo_exception", ""))[:180])

            print("entries:", len(entries))

            if not entries:
                # Попробуем понять, это HTML или не RSS.
                soup = BeautifulSoup(r.text[:20000], "html.parser")
                title = soup.find("title")
                print("html_title:", title.get_text(" ", strip=True)[:180] if title else "")
                summary.append((name, "empty_or_not_rss", r.status_code, 0, 0, url))
                continue

            seller_like = 0

            for i, e in enumerate(entries[:10], 1):
                title = getattr(e, "title", "") or ""
                summary_text = getattr(e, "summary", "") or ""
                link = getattr(e, "link", "") or ""
                s = score_text(title + " " + summary_text)
                if s > 0:
                    seller_like += 1

                print(f"{i:02d}. seller_score={s} | {title[:180]}")
                print("    link:", link)

            status = "good" if seller_like >= 2 else "weak"
            summary.append((name, status, r.status_code, len(entries), seller_like, url))

        except Exception as e:
            print("ERROR:", repr(e))
            summary.append((name, "error", "", 0, 0, f"{url} | {repr(e)[:120]}"))

    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print("name | status | http | entries | seller_like_first10 | url")
    for row in summary:
        print(" | ".join(map(str, row)))

if __name__ == "__main__":
    main()
