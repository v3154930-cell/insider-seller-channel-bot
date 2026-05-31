#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.db import list_expected_tables


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-db", default="/opt/newsbot_v2/news_queue.db")
    parser.add_argument("--v2-root", default="/opt/newsbot_v2")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    v2_db = Path(args.v2_db)
    readable = v2_db.exists()
    v2_tables = []
    news_rows = 0
    published_rows = 0
    unpublished_rows = 0
    digest_candidates = 0
    has_full_text = False
    has_links = False
    has_max_message_id = False

    if readable:
        con = sqlite3.connect(f"file:{v2_db}?mode=ro", uri=True)
        try:
            v2_tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            if "news" in v2_tables:
                news_cols = [r[1] for r in con.execute("PRAGMA table_info(news)")]
                news_rows = int(con.execute("SELECT COUNT(*) FROM news").fetchone()[0])
                has_full_text = any(c in news_cols for c in ("full_text", "raw_text", "full_article"))
                has_links = any(c in news_cols for c in ("link", "url", "source_url"))
                if "is_published" in news_cols:
                    published_rows = int(con.execute("SELECT COUNT(*) FROM news WHERE is_published=1").fetchone()[0])
                    unpublished_rows = max(news_rows - published_rows, 0)
                elif "published" in news_cols:
                    published_rows = int(con.execute("SELECT COUNT(*) FROM news WHERE published=1").fetchone()[0])
                    unpublished_rows = max(news_rows - published_rows, 0)
                if "is_digest_candidate" in news_cols:
                    digest_candidates = int(con.execute("SELECT COUNT(*) FROM news WHERE is_digest_candidate=1").fetchone()[0])
                elif "for_digest" in news_cols:
                    digest_candidates = int(con.execute("SELECT COUNT(*) FROM news WHERE for_digest=1").fetchone()[0])
            has_max_message_id = ("published_messages" in v2_tables)
            if has_max_message_id:
                pm_cols = [r[1] for r in con.execute("PRAGMA table_info(published_messages)")]
                has_max_message_id = "max_message_id" in pm_cols
        finally:
            con.close()

    status = "OK" if readable else "FAIL"
    print(f"V3_MIGRATION_DRY_RUN_STATUS={status}")
    print(f"v2_db={v2_db}")
    print(f"v2_db_readable={'true' if readable else 'false'}")
    print(f"v2_tables={','.join(v2_tables)}")
    print(f"v2_news_rows={news_rows}")
    print(f"v2_published_rows={published_rows}")
    print(f"v2_unpublished_rows={unpublished_rows}")
    print(f"v2_digest_candidates={digest_candidates}")
    print(f"v2_has_full_text={'true' if has_full_text else 'false'}")
    print(f"v2_has_links={'true' if has_links else 'false'}")
    print(f"v2_has_max_message_id={'true' if has_max_message_id else 'false'}")
    print(f"v3_target_tables={','.join(list_expected_tables())}")
    print(f"would_migrate_raw_news={news_rows}")
    print(f"would_migrate_published_messages={published_rows}")
    print(f"would_migrate_full_articles={news_rows if has_full_text else 0}")
    print(f"would_migrate_digest_runs={digest_candidates}")
    print("would_create_migration_mapping=true")
    print("duplicate_prevention_strategy=stable_external_id_hash(source+link+title+published_at/content_hash); migration_mapping(v2_table,v2_id,v3_table,v3_id_or_external_id,migrated_at,status); preserve_published_status; do_not_repost_published; preserve_max_message_id_if_exists; preserve_source_link; preserve_full_text; preserve_digest_history")
    print("production_mutation=false")
    print("recommended_next_steps=backup before real migration; execute dry-run first; real migration only by explicit operator command; rollback to v2 using backup if validation fails")
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
