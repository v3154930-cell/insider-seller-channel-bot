#!/usr/bin/env python3
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")


def norm_date(value: str | None) -> str:
    if value:
        return value.strip()
    return datetime.now().strftime("%Y-%m-%d")


def mp_label(mp: str) -> str:
    return {
        "ozon": "Ozon",
        "wildberries": "Wildberries",
        "yandex_market": "Яндекс Маркет",
        "unknown": "Не определено",
    }.get(mp or "unknown", mp or "Не определено")


def classify_doc(document_name: str, source_url: str) -> str:
    s = f"{document_name or ''} {source_url or ''}".lower()

    if "wb api" in s or "wildberries_api" in s:
        return "WB API / комиссии"
    if "тариф" in s or "rates" in s or "commission" in s or ".xlsx" in s:
        return "тарифы / ставки / таблицы"
    if "legal" in s or "agreement" in s or "terms" in s or "оферт" in s:
        return "оферта / legal-документ"
    return "официальный документ"


def rows_for_day(cur, day: str):
    return cur.execute(
        """
        SELECT
            id,
            marketplace,
            document_name,
            section,
            topic,
            source_url,
            content_hash,
            loaded_at
        FROM rules_documents
        WHERE substr(loaded_at, 1, 10) = ?
        ORDER BY marketplace, document_name, loaded_at, id
        """,
        (day,),
    ).fetchall()


def previous_hash(cur, marketplace, document_name, section, day: str):
    row = cur.execute(
        """
        SELECT content_hash, loaded_at, id
        FROM rules_documents
        WHERE marketplace = ?
          AND document_name = ?
          AND section = ?
          AND substr(loaded_at, 1, 10) < ?
        ORDER BY loaded_at DESC, id DESC
        LIMIT 1
        """,
        (marketplace, document_name, section, day),
    ).fetchone()

    if not row:
        return None

    return row["content_hash"]


def build_summary(day: str):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = rows_for_day(cur, day)

    grouped = {}

    for row in rows:
        key = (
            row["marketplace"],
            row["document_name"],
            row["source_url"],
        )

        if key not in grouped:
            grouped[key] = {
                "marketplace": row["marketplace"],
                "document_name": row["document_name"],
                "source_url": row["source_url"],
                "doc_kind": classify_doc(row["document_name"], row["source_url"]),
                "rows": 0,
                "new_sections": 0,
                "changed_sections": 0,
                "same_sections": 0,
                "sections": set(),
                "first_loaded": row["loaded_at"],
                "last_loaded": row["loaded_at"],
            }

        g = grouped[key]
        g["rows"] += 1
        g["sections"].add(row["section"])
        g["first_loaded"] = min(g["first_loaded"], row["loaded_at"])
        g["last_loaded"] = max(g["last_loaded"], row["loaded_at"])

        prev_hash = previous_hash(
            cur,
            row["marketplace"],
            row["document_name"],
            row["section"],
            day,
        )

        if prev_hash is None:
            g["new_sections"] += 1
        elif prev_hash != row["content_hash"]:
            g["changed_sections"] += 1
        else:
            g["same_sections"] += 1

    con.close()

    result = list(grouped.values())
    result.sort(key=lambda x: (-x["changed_sections"], -x["new_sections"], -x["rows"], x["marketplace"], x["document_name"]))
    return result


def print_table(day: str, summary):
    print("=" * 80)
    print("OFFICIAL RULES UPDATES SUMMARY")
    print(f"date: {day}")
    print("=" * 80)

    if not summary:
        print("No rules_documents rows loaded for this date.")
        return

    for item in summary:
        print()
        print(f"marketplace: {mp_label(item['marketplace'])}")
        print(f"document: {item['document_name']}")
        print(f"kind: {item['doc_kind']}")
        print(f"rows_loaded: {item['rows']}")
        print(f"sections: {len(item['sections'])}")
        print(f"new_sections: {item['new_sections']}")
        print(f"changed_sections_vs_previous_load: {item['changed_sections']}")
        print(f"same_sections_vs_previous_load: {item['same_sections']}")
        print(f"first_loaded: {item['first_loaded']}")
        print(f"last_loaded: {item['last_loaded']}")
        print(f"source_url: {item['source_url']}")


def print_digest_text(day: str, summary):
    print(f"📌 Официальный слой за {day}")

    if not summary:
        print("За день новых загрузок официальных документов и тарифных строк не обнаружено.")
        return

    print("Официальный слой обновлялся. Это ещё не означает автоматическое изменение условий для продавцов, но фразу «изменений нет» писать нельзя.")
    print()

    for item in summary[:8]:
        changed = item["changed_sections"]
        new = item["new_sections"]

        status_parts = []
        if changed:
            status_parts.append(f"изменённых секций: {changed}")
        if new:
            status_parts.append(f"новых секций: {new}")
        if not status_parts:
            status_parts.append("перезагрузка без отличий по секциям")

        status = ", ".join(status_parts)

        print(
            f"• {mp_label(item['marketplace'])}: {item['document_name']} — "
            f"{item['rows']} строк; {status}."
        )

    print()
    print("Автоматически подтверждённых изменений для публикации может не быть, но официальный слой обновлялся и требует проверки diff.")


def main():
    parser = argparse.ArgumentParser(description="Read-only summary of rules_documents updates.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD. Default: today.")
    parser.add_argument("--digest-text", action="store_true", help="Print digest-ready text.")
    args = parser.parse_args()

    day = norm_date(args.date)
    summary = build_summary(day)

    if args.digest_text:
        print_digest_text(day, summary)
    else:
        print_table(day, summary)


if __name__ == "__main__":
    main()
