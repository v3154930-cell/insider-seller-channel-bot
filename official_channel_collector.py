import hashlib
import json
import os
import html
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

NEWS_DB = Path("/opt/newsbot_v2/news_queue.db")
RAG_DB = Path("/opt/newsbot_v2/data/rag_store.db")
ENV_PATH = Path("/opt/newsbot_v2/.env")


def load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


SOURCES = [
    {
        "source_name": "OFFICIAL: Ozon Marketplace TG",
        "username": "ozonmarketplace",
        "marketplace": "ozon",
        "url": "https://t.me/s/ozonmarketplace",
        "notes": "Official Telegram channel for Ozon sellers. Used as official_signal/high only, not tariff source of truth.",
    },
    {
        "source_name": "OFFICIAL: WB Partners TG",
        "username": "wbsellerofficial",
        "marketplace": "wildberries",
        "url": "https://t.me/s/wbsellerofficial",
        "notes": "Official Telegram channel for Wildberries entrepreneurs. Used as official_signal/high only.",
    },
    {
        "source_name": "OFFICIAL: WB API Notifications TG",
        "username": "wb_api_notifications",
        "marketplace": "wildberries",
        "url": "https://t.me/s/wb_api_notifications",
        "notes": "Official Wildberries developer/API notification channel. Used as official_signal/high only.",
    },
    {
        "source_name": "OFFICIAL: Yandex Market Sellers TG",
        "username": "market_marketplace",
        "marketplace": "yandex_market",
        "url": "https://t.me/s/market_marketplace",
        "notes": "Official Yandex Market seller news channel. Used as official_signal/high only.",
    },
    {
        "source_name": "OFFICIAL: Yandex Market API TG",
        "username": "yandex_market_api",
        "marketplace": "yandex_market",
        "url": "https://t.me/s/yandex_market_api",
        "notes": "Yandex Market API news channel. Used as official_signal/high only.",
    },
]


def clean_html(value: str) -> str:
    value = value or ""
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def title_from_text(text: str) -> str:
    text = " ".join((text or "").split())
    return text[:180] if text else ""


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 InsiderSellerBot/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_posts(page_html: str, username: str):
    # Telegram public channel page: blocks with data-post="channel/123"
    pattern = re.compile(
        r'<div class="tgme_widget_message[^"]*"[^>]*data-post="' + re.escape(username) + r'/(\d+)"[\s\S]*?(?=<div class="tgme_widget_message[^"]*"[^>]*data-post="|\Z)',
        re.S,
    )

    posts = []

    for match in pattern.finditer(page_html):
        post_id = match.group(1)
        block = match.group(0)

        text_match = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)</div>',
            block,
            re.S,
        )

        if not text_match:
            continue

        text = clean_html(text_match.group(1))
        if not text:
            continue

        time_match = re.search(r'<time datetime="([^"]+)"', block)
        published_at = time_match.group(1) if time_match else ""

        posts.append({
            "post_id": post_id,
            "text": text,
            "title": title_from_text(text),
            "published_at": published_at,
            "link": f"https://t.me/{username}/{post_id}",
        })

    return posts


def ensure_news_tables(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS official_channel_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        username TEXT NOT NULL,
        marketplace TEXT,
        source_type TEXT DEFAULT 'official_channel',
        rag_layer TEXT DEFAULT 'official_signal',
        trust_level TEXT DEFAULT 'high',
        post_id TEXT NOT NULL,
        title TEXT,
        raw_text TEXT,
        link TEXT,
        published_at TEXT,
        collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        content_hash TEXT,
        status TEXT DEFAULT 'new',
        UNIQUE(username, post_id)
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_official_channel_posts_marketplace
    ON official_channel_posts(marketplace)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_official_channel_posts_collected_at
    ON official_channel_posts(collected_at)
    """)


def register_rag_sources():
    if not RAG_DB.exists():
        print("RAG DB not found, skip rag_sources registration:", RAG_DB)
        return

    conn = sqlite3.connect(RAG_DB)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rag_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        marketplace TEXT,
        rag_layer TEXT NOT NULL,
        trust_level TEXT NOT NULL DEFAULT 'medium',
        url TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    for src in SOURCES:
        row = cur.execute(
            "SELECT id FROM rag_sources WHERE name = ?",
            (src["source_name"],),
        ).fetchone()

        if row:
            cur.execute("""
                UPDATE rag_sources
                SET source_type = 'official_channel',
                    marketplace = ?,
                    rag_layer = 'official_signal',
                    trust_level = 'high',
                    url = ?,
                    enabled = 1,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (src["marketplace"], src["url"], src["notes"], row[0]))
        else:
            cur.execute("""
                INSERT INTO rag_sources (
                    name, source_type, marketplace, rag_layer, trust_level, url, enabled, notes
                )
                VALUES (?, 'official_channel', ?, 'official_signal', 'high', ?, 1, ?)
            """, (src["source_name"], src["marketplace"], src["url"], src["notes"]))

    conn.commit()

    print("registered official_channel sources in rag_sources:")
    for row in cur.execute("""
        SELECT id, source_type, marketplace, rag_layer, trust_level, enabled, name, url
        FROM rag_sources
        WHERE source_type = 'official_channel'
        ORDER BY marketplace, name
    """):
        print(row)

    conn.close()



def normalize_marketplace(value: str) -> str:
    value = (value or "").strip().lower()
    if value in ("ozon", "озон"):
        return "ozon"
    if value in ("wb", "wildberries", "вб", "вайлдберриз"):
        return "wildberries"
    if value in ("yandex", "yandex_market", "яндекс", "яндекс маркет", "market"):
        return "yandex_market"
    return value or "unknown"


def guess_marketplace(source_name: str, text: str, url: str) -> str:
    hay = f"{source_name} {text} {url}".lower()
    if "ozon" in hay or "озон" in hay:
        return "ozon"
    if "wildberries" in hay or "wbseller" in hay or "wb_api" in hay or " wb " in f" {hay} ":
        return "wildberries"
    if "yandex" in hay or "яндекс" in hay or "market_marketplace" in hay or "yandex_market" in hay:
        return "yandex_market"
    return "unknown"


def official_json_username(source_name: str, source_url: str, link: str) -> str:
    value = str(source_name or source_url or link or "github_json").lower()
    value = re.sub(r"^official:\s*", "", value)
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9_а-яё]+", "_", value, flags=re.I)
    value = value.strip("_")
    return ("json_" + value[:80]) if value else "json_github"


def extract_json_posts(data):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("posts", "items", "updates", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    raise ValueError("Unsupported official JSON format: expected list or dict with posts/items/updates/data")


def fetch_official_json_posts(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 InsiderSellerOfficialJSON/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return extract_json_posts(json.loads(raw))


def collect_official_json_sources(cur):
    urls_raw = (
        os.getenv("OFFICIAL_JSON_URLS")
        or os.getenv("OFFICIAL_JSON_URL")
        or ""
    ).strip()

    if not urls_raw:
        print("official JSON sources: not configured")
        return 0, 0

    urls = [u.strip() for u in urls_raw.replace("\n", ",").split(",") if u.strip()]

    total_seen = 0
    total_inserted = 0

    for url in urls:
        print()
        print("SOURCE JSON:", url)

        try:
            posts = fetch_official_json_posts(url)
        except Exception as e:
            print("FAILED JSON:", repr(e))
            continue

        print("json posts parsed:", len(posts))
        total_seen += len(posts)

        for post in posts:
            text = str(
                post.get("text")
                or post.get("raw_text")
                or post.get("body")
                or post.get("content")
                or post.get("message")
                or ""
            ).strip()

            title = str(post.get("title") or post.get("headline") or "").strip()
            if not title:
                title = title_from_text(text)

            link = str(
                post.get("link")
                or post.get("raw_url")
                or post.get("post_url")
                or post.get("url")
                or post.get("source_url")
                or ""
            ).strip()

            source_url = str(post.get("source_url") or url).strip()
            source_name = str(post.get("source_name") or post.get("source") or "").strip()
            if not source_name:
                source_name = "OFFICIAL: GitHub JSON"

            marketplace = normalize_marketplace(str(post.get("marketplace") or ""))
            if marketplace == "unknown":
                marketplace = guess_marketplace(source_name, f"{title} {text}", f"{source_url} {link}")

            username = str(post.get("username") or "").strip()
            if not username:
                username = official_json_username(source_name, source_url, link)

            content_hash = str(post.get("content_hash") or post.get("hash") or "").strip()
            if not content_hash:
                content_hash = hashlib.sha256(
                    (source_name + "|" + link + "|" + title + "|" + text).encode("utf-8", errors="ignore")
                ).hexdigest()

            post_id = str(post.get("post_id") or post.get("id") or "").strip()
            if not post_id:
                post_id = content_hash[:24]

            published_at = str(
                post.get("published_at")
                or post.get("posted_at")
                or post.get("date")
                or post.get("created_at")
                or ""
            ).strip()

            if not text and not title:
                continue

            cur.execute("""
                INSERT OR IGNORE INTO official_channel_posts (
                    source_name,
                    username,
                    marketplace,
                    source_type,
                    rag_layer,
                    trust_level,
                    post_id,
                    title,
                    raw_text,
                    link,
                    published_at,
                    collected_at,
                    content_hash,
                    status
                )
                VALUES (?, ?, ?, 'official_channel', 'official_signal', 'high', ?, ?, ?, ?, ?, ?, ?, 'new')
            """, (
                source_name,
                username,
                marketplace,
                post_id,
                title,
                text,
                link,
                published_at,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                content_hash,
            ))

            if cur.rowcount:
                total_inserted += 1

    return total_seen, total_inserted

def main():
    load_env()
    conn = sqlite3.connect(NEWS_DB)
    cur = conn.cursor()

    ensure_news_tables(cur)

    total_inserted = 0
    total_seen = 0
    json_seen, json_inserted = collect_official_json_sources(cur)
    total_seen += json_seen
    total_inserted += json_inserted


    # If GitHub official JSON is available, it is the primary source.
    # Direct Telegram web parsing is only a fallback, because the VPS often gets
    # No route to host for t.me/s pages.
    tg_fallback_mode = os.getenv("OFFICIAL_TG_FALLBACK", "auto").strip().lower()
    skip_direct_tg = (
        tg_fallback_mode in ("0", "false", "no", "off")
        or (tg_fallback_mode == "auto" and json_seen > 0)
    )

    if skip_direct_tg:
        print("direct official TG fallback skipped; GitHub JSON is available")
    else:

        for src in SOURCES:
            print()
            print("SOURCE:", src["source_name"], src["url"])

            try:
                page = fetch_html(src["url"])
                posts = parse_posts(page, src["username"])
            except Exception as e:
                print("FAILED:", repr(e))
                continue

            print("posts parsed:", len(posts))
            total_seen += len(posts)

            for post in posts:
                content_hash = hashlib.sha256(
                    (src["source_name"] + post["post_id"] + post["text"]).encode("utf-8")
                ).hexdigest()

                cur.execute("""
                    INSERT OR IGNORE INTO official_channel_posts (
                        source_name,
                        username,
                        marketplace,
                        source_type,
                        rag_layer,
                        trust_level,
                        post_id,
                        title,
                        raw_text,
                        link,
                        published_at,
                        collected_at,
                        content_hash,
                        status
                    )
                    VALUES (?, ?, ?, 'official_channel', 'official_signal', 'high', ?, ?, ?, ?, ?, ?, ?, 'new')
                """, (
                    src["source_name"],
                    src["username"],
                    src["marketplace"],
                    post["post_id"],
                    post["title"],
                    post["text"],
                    post["link"],
                    post["published_at"],
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    content_hash,
                ))

                if cur.rowcount:
                    total_inserted += 1

        conn.commit()
        conn.close()
    register_rag_sources()

    print()
    print("official_channel_collector done")
    print("posts seen:", total_seen)
    print("posts inserted:", total_inserted)


if __name__ == "__main__":
    main()
