import hashlib
import re
import sqlite3
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/rag_store.db")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def get_text(self):
        text = " ".join(self.parts)
        text = re.sub(r"\s+", " ", text).strip()
        return text


def fetch_url(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 compatible; InsiderSellerBot/1.0"
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def guess_topic(rag_layer: str) -> str:
    if rag_layer == "tariff_official":
        return "tariff"
    if rag_layer == "legal_official":
        return "offer"
    return "general"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    sources = cur.execute("""
        SELECT id, name, source_type, marketplace, rag_layer, trust_level, url
        FROM rag_sources
        WHERE enabled = 1
          AND source_type = 'official'
          AND url IS NOT NULL
        ORDER BY id
    """).fetchall()

    print("official sources:", len(sources))

    inserted = 0
    skipped = 0
    failed = 0

    for source_id, name, source_type, marketplace, rag_layer, trust_level, url in sources:
        print()
        print("SOURCE:", name)
        print("URL:", url)

        try:
            html = fetch_url(url)
            text = html_to_text(html)

            if len(text) < 500:
                print("SKIP: too little text", len(text))
                skipped += 1
                continue

            title = name
            content_hash = hashlib.sha256((url + "\n" + text).encode("utf-8")).hexdigest()

            exists = cur.execute("""
                SELECT id FROM rag_documents
                WHERE content_hash = ?
            """, (content_hash,)).fetchone()

            if exists:
                print("SKIP: already exists id=", exists[0])
                skipped += 1
                continue

            topic = guess_topic(rag_layer)
            now = datetime.utcnow().isoformat(timespec="seconds")

            cur.execute("""
                INSERT INTO rag_documents (
                    source_news_id,
                    title,
                    clean_text,
                    markdown_text,
                    source,
                    source_type,
                    marketplace,
                    document_type,
                    topic,
                    impact_level,
                    published_at,
                    effective_date,
                    link,
                    content_hash,
                    rag_eligible,
                    eligibility_reason,
                    rag_layer,
                    trust_level,
                    source_url
                )
                VALUES (
                    NULL,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    ?,
                    ?,
                    1,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (
                title,
                text,
                text,
                name,
                source_type,
                marketplace,
                rag_layer,
                topic,
                "high",
                now,
                url,
                content_hash,
                "official source imported from rag_sources",
                rag_layer,
                trust_level,
                url,
            ))

            conn.commit()
            print("INSERTED:", name, "chars=", len(text))
            inserted += 1

        except Exception as e:
            print("FAILED:", repr(e))
            failed += 1

    print()
    print("DONE")
    print("inserted:", inserted)
    print("skipped:", skipped)
    print("failed:", failed)

    conn.close()


if __name__ == "__main__":
    main()
