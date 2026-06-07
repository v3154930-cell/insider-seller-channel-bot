#!/usr/bin/env python3
"""Idempotently create analytics contour v1 tables in rag_store.db."""

import argparse
import sqlite3
from pathlib import Path


def base_dir():
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db():
    return base_dir() / "data" / "rag_store.db"


def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS analytics_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_key TEXT UNIQUE NOT NULL,
        report_type TEXT NOT NULL,
        marketplace TEXT DEFAULT 'multiple',
        period_start TEXT,
        period_end TEXT,
        topic TEXT,
        title TEXT,
        summary TEXT,
        key_findings TEXT,
        seller_risks TEXT,
        seller_actions TEXT,
        source_doc_ids TEXT,
        source_news_ids TEXT,
        rag_document_id INTEGER,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analytics_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        request_type TEXT,
        marketplace TEXT,
        period_start TEXT,
        period_end TEXT,
        query TEXT,
        status TEXT DEFAULT 'created',
        is_free INTEGER DEFAULT 1,
        result_report_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analytics_user_limits (
        user_id TEXT NOT NULL,
        week_start TEXT NOT NULL,
        free_requests_limit INTEGER DEFAULT 2,
        free_requests_used INTEGER DEFAULT 0,
        paid_requests_used INTEGER DEFAULT 0,
        plan TEXT DEFAULT 'free',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, week_start)
    );
    CREATE INDEX IF NOT EXISTS idx_analytics_reports_period
        ON analytics_reports(marketplace, period_start, period_end, report_type);
    CREATE INDEX IF NOT EXISTS idx_analytics_requests_user_created
        ON analytics_requests(user_id, created_at);
    """)
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db()))
    args = ap.parse_args()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    init_schema(conn)
    for name in ("analytics_reports", "analytics_requests", "analytics_user_limits"):
        print("%s=ready rows=%s" % (name, conn.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]))
    conn.close()
    print("analytics_schema_db=%s" % db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
