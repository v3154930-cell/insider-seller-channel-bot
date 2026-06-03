#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _ensure_app_importable() -> None:
    this_file = Path(__file__).resolve()
    runtime_root = this_file.parent.parent
    if str(runtime_root) not in sys.path:
        sys.path.insert(0, str(runtime_root))


_ensure_app_importable()

from app.scoring.llm_router import LLMRouter  # noqa: E402


def clean(value) -> str:
    return str(value or "").strip()


def build_input(title: str, raw_text: str) -> str:
    title = clean(title)
    raw_text = clean(raw_text)
    if title and raw_text and not raw_text.startswith(title):
        return title + "\n\n" + raw_text
    return raw_text or title


def format_processed(result: dict) -> str:
    summary = clean(result.get("summary"))
    conclusion = clean(result.get("seller_conclusion"))

    parts = []
    if summary:
        parts.append("Кратко: " + summary)
    if conclusion:
        parts.append("Вывод для селлера: " + conclusion)

    err = clean(result.get("llm_error"))
    if err:
        parts.append("LLM error: " + err[:500])

    return "\n\n".join(parts).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="/opt/newsbot_v2/news_queue.db")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--only-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    where = [
        "IFNULL(is_published,0)=0",
        "seller_decision='publish'",
    ]
    params = []

    if not args.overwrite:
        where.append("(processed_text IS NULL OR TRIM(processed_text)='')")

    if args.only_id is not None:
        where.append("id=?")
        params.append(args.only_id)

    sql = """
        SELECT id, title, raw_text, seller_relevance_score, actionability_score
        FROM news
        WHERE {}
        ORDER BY id DESC
        LIMIT ?
    """.format(" AND ".join(where))
    params.append(args.limit)

    router = LLMRouter(env=dict(os.environ))

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(sql, params).fetchall()

    print("selected={} dry_run={}".format(len(rows), str(args.dry_run).lower()))

    updated = 0

    for row in rows:
        news_id = int(row["id"])
        title = clean(row["title"])
        raw_text = clean(row["raw_text"])
        text = build_input(title, raw_text)

        scoring = {
            "seller_relevance_score": int(row["seller_relevance_score"] or 0),
            "actionability_score": int(row["actionability_score"] or 0),
            "is_low_value": False,
        }

        result = router.run(text, prompt_type="seller_summary", scoring=scoring)
        processed = format_processed(result)

        print("---")
        print("id={}".format(news_id))
        print("llm_status={}".format(result.get("llm_status")))
        print("llm_provider_used={}".format(result.get("llm_provider_used")))
        print("llm_attempt={}".format(result.get("llm_attempt")))
        print("title_before={}".format(title[:160]))
        print("processed_preview={}".format(processed[:700].replace("\n", " | ")))

        if not args.dry_run:
            con.execute(
                "UPDATE news SET processed_text=? WHERE id=?",
                (processed, news_id),
            )
            updated += 1

    if not args.dry_run:
        con.commit()

    con.close()
    print("updated={}".format(updated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
