import os
import json
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

from db import init_db, _execute, _fetch_all

WB_API_KEY = os.getenv("WB_API_KEY")
SOURCE_URL = "wildberries_api:common-api/api/v1/tariffs/commission"
API_URL = "https://common-api.wildberries.ru/api/v1/tariffs/commission"
CACHE_PATH = Path("rules_docs/api_cache/wb_commissions.json")
CACHE_TTL_HOURS = 12


def make_hash(row):
    base = "|".join([
        "wildberries",
        "WB API — комиссии по категориям",
        str(row.get("parentID", "")),
        str(row.get("parentName", "")),
        str(row.get("subjectID", "")),
        str(row.get("subjectName", "")),
        str(row.get("kgvpBooking", "")),
        str(row.get("kgvpMarketplace", "")),
        str(row.get("kgvpPickup", "")),
        str(row.get("kgvpSupplier", "")),
        str(row.get("kgvpSupplierExpress", "")),
        str(row.get("paidStorageKgvp", "")),
    ]).lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


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


def load_from_cache():
    if not CACHE_PATH.exists():
        return None

    mtime = datetime.fromtimestamp(CACHE_PATH.stat().st_mtime)
    age = datetime.now() - mtime

    if age > timedelta(hours=CACHE_TTL_HOURS):
        return None

    raw = CACHE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    report = data.get("report") or []

    print(f"WB API cache used: {CACHE_PATH}, age={age}")
    return report


def fetch_commissions():
    cached = load_from_cache()
    if cached is not None:
        return cached

    if not WB_API_KEY:
        raise RuntimeError("WB_API_KEY is missing")

    req = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": WB_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "newsbot-v2/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(raw, encoding="utf-8")

    except urllib.error.HTTPError as e:
        if e.code == 429 and CACHE_PATH.exists():
            print("WB API 429 Too Many Requests. Falling back to existing cache.")
            raw = CACHE_PATH.read_text(encoding="utf-8")
        else:
            raise

    data = json.loads(raw)
    report = data.get("report") or []

    if not isinstance(report, list):
        raise RuntimeError("Unexpected WB API response: report is not list")

    return report


def rule_text_from_row(row):
    return (
        f"WB комиссия по категории. "
        f"Родительская категория: {row.get('parentName')} (parentID={row.get('parentID')}). "
        f"Предмет: {row.get('subjectName')} (subjectID={row.get('subjectID')}). "
        f"kgvpBooking: {row.get('kgvpBooking')}%. "
        f"kgvpMarketplace: {row.get('kgvpMarketplace')}%. "
        f"kgvpPickup: {row.get('kgvpPickup')}%. "
        f"kgvpSupplier: {row.get('kgvpSupplier')}%. "
        f"kgvpSupplierExpress: {row.get('kgvpSupplierExpress')}%. "
        f"paidStorageKgvp: {row.get('paidStorageKgvp')}%."
    )


def main():
    init_db()
    ensure_table()

    report = fetch_commissions()
    print("WB commission rows fetched:", len(report))

    inserted_or_ignored = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for row in report:
        parent_name = str(row.get("parentName") or "").strip()
        subject_name = str(row.get("subjectName") or "").strip()

        topic = f"{parent_name} / {subject_name}".strip(" /")
        section = f"commission / parentID={row.get('parentID')} / subjectID={row.get('subjectID')}"
        rule_text = rule_text_from_row(row)
        content_hash = make_hash(row)

        _execute("""
            INSERT OR IGNORE INTO rules_documents
            (marketplace, document_name, section, topic, rule_text, effective_date, source_url, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "wildberries",
            "WB API — комиссии по категориям",
            section,
            topic,
            rule_text,
            today,
            SOURCE_URL,
            content_hash,
        ))

        inserted_or_ignored += 1

    print("WB commissions inserted_or_ignored:", inserted_or_ignored)

    rows = _fetch_all("""
        SELECT COUNT(*)
        FROM rules_documents
        WHERE marketplace='wildberries'
          AND document_name='WB API — комиссии по категориям'
    """)
    print("WB API commission docs total:", rows[0][0])

    print("\n=== SAMPLE ===")
    rows = _fetch_all("""
        SELECT topic, rule_text
        FROM rules_documents
        WHERE marketplace='wildberries'
          AND document_name='WB API — комиссии по категориям'
        ORDER BY id DESC
        LIMIT 5
    """)
    for r in rows:
        print(r)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR:", e.code)
        print(e.read().decode("utf-8", errors="ignore")[:2000])
        raise
