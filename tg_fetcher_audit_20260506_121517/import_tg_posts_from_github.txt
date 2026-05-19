import json
import os
import re
import sys
import urllib.request
from datetime import datetime

from db import init_db, add_to_queue_batch, _fetch_all

RAW_URL = os.getenv(
    "TG_POSTS_JSON_URL",
    "https://raw.githubusercontent.com/v3154930-cell/newsbot-tg-fetcher/main/tg_posts.json"
)

LOCAL_JSON = "/opt/newsbot_v2/data/tg_posts.json"


def norm_text(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_source(channel):
    channel = norm_text(channel)
    if not channel:
        return "TG:unknown"

    channel = channel.replace("https://t.me/", "")
    channel = channel.replace("http://t.me/", "")
    channel = channel.replace("t.me/", "")
    channel = channel.strip("/ ")

    if channel.startswith("@"):
        channel = channel[1:]

    if channel.startswith("TG:"):
        return channel

    return "TG:" + channel


def first_existing(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return ""


def make_title(text):
    text = re.sub(r"\s+", " ", norm_text(text))
    if not text:
        return ""
    return text[:240]


def make_description(text):
    text = re.sub(r"\s+", " ", norm_text(text))
    return text[:1200]


def build_link(post, source):
    link = norm_text(first_existing(post, ["link", "url", "post_url", "message_url", "tg_url"]))
    if link:
        return link

    channel = source.replace("TG:", "")
    msg_id = norm_text(first_existing(post, ["id", "message_id", "post_id"]))
    if channel and msg_id:
        return f"https://t.me/{channel}/{msg_id}"

    text = make_description(first_existing(post, ["text", "message", "content", "title"]))
    return "tg://local/" + source + "/" + str(abs(hash(text)))


def load_json_from_github():
    print("=== DOWNLOAD TG JSON ===")
    print("URL:", RAW_URL)

    os.makedirs(os.path.dirname(LOCAL_JSON), exist_ok=True)

    req = urllib.request.Request(
        RAW_URL,
        headers={"User-Agent": "newsbot-v2-tg-importer"}
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    with open(LOCAL_JSON, "wb") as f:
        f.write(raw)

    print("Downloaded bytes:", len(raw))

    return json.loads(raw.decode("utf-8"))


def extract_posts(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ["posts", "items", "messages", "data", "results"]:
            if isinstance(payload.get(key), list):
                return payload[key]

    return []


def main():
    init_db()

    payload = load_json_from_github()
    posts = extract_posts(payload)

    print("Posts in JSON:", len(posts))

    items = []
    seller_decisions = {}

    for post in posts:
        if not isinstance(post, dict):
            continue

        text = first_existing(post, ["text", "message", "content", "title", "description"])
        title = make_title(first_existing(post, ["title"]))
        if not title:
            title = make_title(text)

        description = make_description(text)

        if not title and not description:
            continue

        channel = first_existing(post, ["channel", "channel_username", "source", "username", "chat", "chat_title"])
        source = normalize_source(channel)

        link = build_link(post, source)

        item = {
            "title": title,
            "description": description or title,
            "link": link,
            "source": source,
            "importance": "normal",
            "category": "telegram",
            "score": 5,
            "priority_bucket": "medium",
            "reason_tags": "telegram_github_import"
        }

        items.append(item)

        seller_decisions[link] = {
            "decision": "publish",
            "seller_relevance_score": 5,
            "actionability_score": 5,
            "reason": "telegram_github_import"
        }

    print("Prepared items:", len(items))

    if not items:
        print("NO ITEMS TO IMPORT")
        return

    before = _fetch_all("""
        SELECT COUNT(*) AS total_news, MAX(id) AS max_id, MAX(created_at) AS newest_created_at
        FROM news
    """)
    print("Before:", before)

    add_to_queue_batch(items, seller_decisions=seller_decisions)

    after = _fetch_all("""
        SELECT COUNT(*) AS total_news, MAX(id) AS max_id, MAX(created_at) AS newest_created_at
        FROM news
    """)
    print("After:", after)

    pending = _fetch_all("""
        SELECT id, source, seller_decision, is_published, seller_relevance_score, title
        FROM news
        WHERE is_published = 0
          AND seller_decision = 'publish'
        ORDER BY id DESC
        LIMIT 10
    """)

    print("Pending publish candidates:")
    for row in pending:
        print(row)


if __name__ == "__main__":
    main()
