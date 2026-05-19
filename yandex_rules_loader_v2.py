import hashlib
import re
import time
from datetime import datetime
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from db import init_db, _execute, _fetch_all

YANDEX_SOURCES = [
    {
        "document_name": "Яндекс Маркет — как устроен договор с Маркетом",
        "section": "Договор",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/contract",
    },
    {
        "document_name": "Яндекс Маркет — взаиморасчёты и стоимость услуг",
        "section": "Взаиморасчёты и тарифы",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/rates/",
    },
    {
        "document_name": "Яндекс Маркет — услуги по работе с товарами и заказами",
        "section": "Модели работы",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/rates/models/",
    },
    {
        "document_name": "Яндекс Маркет — тарифы FBY",
        "section": "FBY",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/rates/models/fby",
    },
    {
        "document_name": "Яндекс Маркет — тарифы FBS",
        "section": "FBS",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/rates/models/fbs",
    },
    {
        "document_name": "Яндекс Маркет — тарифы DBS",
        "section": "DBS",
        "url": "https://yandex.ru/support/marketplace/ru/introduction/rates/models/dbs",
    },
    {
        "document_name": "Яндекс Маркет — legal terms marketplace crossboard",
        "section": "Legal",
        "url": "https://yandex.ru/legal/marketplace_crossboard_terms/ru/",
    },
    {
        "document_name": "Яндекс Маркет — legal CPA service agreement",
        "section": "Legal",
        "url": "https://yandex.ru/legal/cpa_service_agreement/ru/",
    },
]


def ensure_table():
    _execute("""
    CREATE TABLE IF NOT EXISTS rules_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        marketplace TEXT NOT NULL,
        document_name TEXT,
        section TEXT,
        topic TEXT,
        rule_text TEXT NOT NULL,
        effective_date TEXT,
        source_url TEXT,
        content_hash TEXT UNIQUE,
        loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)


def fetch_html(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 newsbot-rules-loader/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=40) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="ignore")


def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "img", "footer", "header"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if line.lower() in {"да", "нет"}:
            continue
        lines.append(line)

    return "\n".join(lines)


def split_chunks(text, max_chars=1800):
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_chars:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            current = p

    if current:
        chunks.append(current)

    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            start = 0
            while start < len(chunk):
                final.append(chunk[start:start + max_chars].strip())
                start += max_chars

    return [c for c in final if len(c) >= 80]


def make_hash(marketplace, document_name, section, topic, rule_text, source_url):
    base = "|".join([
        marketplace.strip().lower(),
        document_name.strip().lower(),
        section.strip().lower(),
        topic.strip().lower(),
        rule_text.strip().lower(),
        source_url.strip().lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def topic_from_chunk(chunk):
    first_line = chunk.splitlines()[0].strip()
    if len(first_line) > 160:
        return first_line[:160].rstrip() + "..."
    return first_line


def insert_chunk(document_name, section, url, chunk, idx):
    marketplace = "yandex_market"
    topic = topic_from_chunk(chunk)
    source_url = url
    effective_date = ""

    content_hash = make_hash(
        marketplace,
        document_name,
        f"{section} / chunk {idx}",
        topic,
        chunk,
        source_url,
    )

    _execute("""
        INSERT OR IGNORE INTO rules_documents
        (marketplace, document_name, section, topic, rule_text, effective_date, source_url, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        marketplace,
        document_name,
        f"{section} / chunk {idx}",
        topic,
        chunk,
        effective_date,
        source_url,
        content_hash,
    ))


def main():
    init_db()
    ensure_table()

    total_chunks = 0
    failed = 0

    for item in YANDEX_SOURCES:
        url = item["url"]
        document_name = item["document_name"]
        section = item["section"]

        try:
            print("FETCH:", document_name)
            html = fetch_html(url)
            text = clean_text(html)
            chunks = split_chunks(text)

            for idx, chunk in enumerate(chunks, start=1):
                insert_chunk(document_name, section, url, chunk, idx)

            print("OK:", document_name, "chunks:", len(chunks))
            total_chunks += len(chunks)
            time.sleep(1)

        except Exception as e:
            failed += 1
            print("FAILED:", document_name, repr(e))

    rows = _fetch_all("""
        SELECT marketplace, COUNT(*)
        FROM rules_documents
        GROUP BY marketplace
        ORDER BY COUNT(*) DESC
    """)

    print()
    print("Yandex loader finished")
    print("new chunks attempted:", total_chunks)
    print("failed pages:", failed)

    print()
    print("=== DOCUMENTS BY MARKETPLACE ===")
    for r in rows:
        print(r)

    print()
    print("=== LAST YANDEX DOCS ===")
    rows = _fetch_all("""
        SELECT id, document_name, section, topic
        FROM rules_documents
        WHERE marketplace = 'yandex_market'
        ORDER BY id DESC
        LIMIT 20
    """)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
