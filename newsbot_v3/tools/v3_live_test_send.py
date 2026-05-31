#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.models import NewsItem
from app.publisher.publisher import limited_live_publish_one


def sample_candidate(scenario: str) -> dict:
    if scenario == "sample_short":
        item = NewsItem("v3-short-1", "Тест короткой новости", "Короткий тестовый текст", "https://example.com/short", "test")
    else:
        item = NewsItem("v3-long-1", "Тест длинной новости", "Длинный текст " * 220, "https://example.com/long", "test")
    return {"id": f"candidate-{item.news_id}", "item": item}


def from_v2_unpublished(v2_db: str) -> dict:
    con = sqlite3.connect(f"file:{v2_db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT id, title, COALESCE(content,''), link FROM news ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        con.close()
    if not row:
        return sample_candidate("sample_short")
    item = NewsItem(str(row[0]), row[1] or "v2 item", row[2] or "", row[3], "v2")
    return {"id": f"candidate-v2-{row[0]}", "item": item}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    p.add_argument("--scenario", default="sample_long", choices=["sample_long", "sample_short", "from_v2_unpublished"])
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--v2-db", default="/opt/newsbot_v2/news_queue.db")
    args = p.parse_args()

    if args.limit != 1:
        print("V3_LIVE_TEST_STATUS=FAIL")
        print("recommended_next_steps=use --limit 1 only")
        return 1

    if not args.execute:
        print("V3_LIVE_TEST_STATUS=DRY_RUN")
        print("real_send=false")
        print("production_mutation=false")
        return 0

    candidate = from_v2_unpublished(args.v2_db) if args.scenario == "from_v2_unpublished" and Path(args.v2_db).exists() else sample_candidate(args.scenario)
    target_channel = __import__('os').getenv("NEWSBOT_V3_TEST_CHANNEL_ID", "")
    result = limited_live_publish_one(candidate, target_channel=target_channel)

    status = "OK" if result.get("send_status") == "sent" else "FAIL"
    print(f"V3_LIVE_TEST_STATUS={status}")
    print("real_send=true")
    for k in ["max_mode", "target_channel", "test_channel_guard", "v3_db_write", "selected_candidate_id", "post_built", "read_more_needed", "source_link_present", "max_message_id", "send_attempt_recorded", "published_message_recorded", "helper_cta_status"]:
        val = result.get(k if k != "selected_candidate_id" else "id", candidate.get("id"))
        print(f"{k}={val}")
    print(f"v3_db={__import__('os').getenv('V3_DB','/opt/newsbot_v3/runtime/newsbot_v3.db')}")
    print("v2_db_mutation=false")
    print("production_mutation=false")
    print("recommended_next_steps=keep v2 as production; rollback by setting NEWSBOT_V3_REAL_SEND=false")
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
