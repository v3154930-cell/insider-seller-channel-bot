import csv
import hashlib
import sys
from pathlib import Path
from db import init_db, _execute, _fetch_all

DEFAULT_PATH = "rules_docs/marketplace_rules_template.csv"

REQUIRED_COLUMNS = [
    "marketplace",
    "document_name",
    "section",
    "topic",
    "rule_text",
    "effective_date",
    "source_url",
]

def make_hash(row):
    base = "|".join([
        (row.get("marketplace") or "").strip().lower(),
        (row.get("document_name") or "").strip().lower(),
        (row.get("section") or "").strip().lower(),
        (row.get("topic") or "").strip().lower(),
        (row.get("rule_text") or "").strip().lower(),
        (row.get("effective_date") or "").strip().lower(),
        (row.get("source_url") or "").strip().lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]

def main():
    init_db()

    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)

    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    inserted = 0
    skipped = 0

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            print("Missing columns:", missing)
            print("Expected:", REQUIRED_COLUMNS)
            sys.exit(1)

        for row in reader:
            marketplace = (row.get("marketplace") or "").strip()
            document_name = (row.get("document_name") or "").strip()
            section = (row.get("section") or "").strip()
            topic = (row.get("topic") or "").strip()
            rule_text = (row.get("rule_text") or "").strip()
            effective_date = (row.get("effective_date") or "").strip()
            source_url = (row.get("source_url") or "").strip()

            if not marketplace or not rule_text:
                skipped += 1
                continue

            content_hash = make_hash(row)

            _execute("""
                INSERT OR IGNORE INTO rules_documents
                (marketplace, document_name, section, topic, rule_text, effective_date, source_url, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                marketplace,
                document_name,
                section,
                topic,
                rule_text,
                effective_date,
                source_url,
                content_hash,
            ))

            inserted += 1

    rows = _fetch_all("SELECT COUNT(*) FROM rules_documents")
    total = rows[0][0]

    print("Import finished")
    print("file:", path)
    print("processed:", inserted + skipped)
    print("inserted_or_ignored:", inserted)
    print("skipped_empty:", skipped)
    print("rules_documents total:", total)

    print("\n=== LAST DOCUMENTS ===")
    rows = _fetch_all("""
        SELECT id, marketplace, document_name, section, topic, effective_date
        FROM rules_documents
        ORDER BY id DESC
        LIMIT 10
    """)
    for r in rows:
        print(r)

if __name__ == "__main__":
    main()
