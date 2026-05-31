from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Dict, List

from app.models import SCHEMA_DRAFT_TABLES


def get_v3_db_path() -> Path:
    return Path(os.getenv("V3_DB", "/opt/newsbot_v3/runtime/newsbot_v3.db"))


def list_expected_tables() -> List[str]:
    return list(SCHEMA_DRAFT_TABLES)


def build_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS raw_news (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    link TEXT,
    published_at TEXT,
    content_hash TEXT,
    raw_payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS normalized_news (
    id INTEGER PRIMARY KEY,
    raw_news_id INTEGER,
    normalized_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    source TEXT,
    link TEXT,
    language TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scored_news (
    id INTEGER PRIMARY KEY,
    normalized_news_id INTEGER,
    score REAL,
    importance TEXT,
    reasons TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS publish_candidates (
    id INTEGER PRIMARY KEY,
    normalized_news_id INTEGER,
    candidate_id TEXT UNIQUE,
    short_post_text TEXT,
    source_link TEXT,
    is_digest_candidate INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS published_messages (
    id INTEGER PRIMARY KEY,
    candidate_id TEXT,
    message_id INTEGER,
    channel TEXT,
    published_at TEXT,
    status TEXT,
    max_message_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS full_articles (
    id INTEGER PRIMARY KEY,
    normalized_news_id INTEGER,
    full_text TEXT,
    source_link TEXT,
    fetched_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS digest_runs (
    id INTEGER PRIMARY KEY,
    digest_id TEXT UNIQUE,
    run_started_at TEXT,
    run_finished_at TEXT,
    selected_count INTEGER,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS callback_events (
    id INTEGER PRIMARY KEY,
    callback_id TEXT,
    callback_type TEXT,
    callback_payload TEXT,
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS source_registry (
    id INTEGER PRIMARY KEY,
    source_id TEXT UNIQUE,
    source_type TEXT,
    source_name TEXT,
    source_url TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS source_health (
    id INTEGER PRIMARY KEY,
    source_id TEXT,
    checked_at TEXT,
    status TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY,
    action_id TEXT,
    actor TEXT,
    action_type TEXT,
    payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY,
    event_id TEXT,
    event_type TEXT,
    severity TEXT,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS send_attempts (
    id INTEGER PRIMARY KEY,
    attempt_id TEXT,
    candidate_id TEXT,
    sent_at TEXT,
    status TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS llm_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    model TEXT,
    prompt_type TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS migration_mapping (
    id INTEGER PRIMARY KEY,
    v2_table TEXT NOT NULL,
    v2_id TEXT NOT NULL,
    v3_table TEXT NOT NULL,
    v3_id_or_external_id TEXT NOT NULL,
    migrated_at TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(v2_table, v2_id, v3_table)
);
CREATE TABLE IF NOT EXISTS rag_sources (
    id INTEGER PRIMARY KEY,
    source_name TEXT,
    source_url TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY,
    source_id INTEGER,
    external_id TEXT,
    title TEXT,
    body TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    content_hash TEXT,
    body TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS legal_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT,
    title TEXT,
    body TEXT,
    source_link TEXT,
    happened_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shadow_runs (
    id INTEGER PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    v2_news_id TEXT,
    selection_reason TEXT,
    importance TEXT,
    seller_relevance_score REAL,
    actionability_score REAL,
    read_more_needed INTEGER,
    read_more_payload TEXT,
    source_link_present INTEGER,
    post_text TEXT,
    helper_cta_planned INTEGER,
    status TEXT,
    diagnostics_json TEXT
);
CREATE TABLE IF NOT EXISTS shadow_rendered_posts (
    id INTEGER PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    shadow_run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    v2_news_id TEXT,
    post_text TEXT NOT NULL,
    read_more_needed INTEGER,
    read_more_payload TEXT,
    source_link_present INTEGER,
    helper_cta_planned INTEGER,
    status TEXT,
    diagnostics_json TEXT,
    FOREIGN KEY(shadow_run_id) REFERENCES shadow_runs(id)
);
""".strip()


def validate_schema_sql() -> bool:
    sql = build_schema_sql()
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(sql)
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return all(table in tables for table in list_expected_tables())
    finally:
        con.close()


def dry_run_create_plan(db_path: Path) -> Dict[str, object]:
    path = Path(db_path)
    return {
        "runtime_db_path": str(path),
        "would_create_db": (not path.exists()),
        "schema_table_count": len(list_expected_tables()),
        "schema_tables": list_expected_tables(),
        "schema_sql_valid": validate_schema_sql(),
        "production_mutation": False,
    }


def init_v3_runtime_db() -> Dict[str, object]:
    """Initialize minimal runtime tables for limited live test.

    NOTE: Backup runtime DB snapshot before first live test send.
    """
    db_path = get_v3_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript("""
CREATE TABLE IF NOT EXISTS published_messages (
    id INTEGER PRIMARY KEY,
    candidate_id TEXT,
    message_id TEXT,
    channel TEXT,
    published_at TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS send_attempts (
    id INTEGER PRIMARY KEY,
    attempt_id TEXT,
    candidate_id TEXT,
    sent_at TEXT,
    status TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY,
    event_id TEXT,
    event_type TEXT,
    severity TEXT,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS callback_events (
    id INTEGER PRIMARY KEY,
    callback_id TEXT,
    callback_type TEXT,
    callback_payload TEXT,
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shadow_runs (
    id INTEGER PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    v2_news_id TEXT,
    selection_reason TEXT,
    importance TEXT,
    seller_relevance_score REAL,
    actionability_score REAL,
    read_more_needed INTEGER,
    read_more_payload TEXT,
    source_link_present INTEGER,
    post_text TEXT,
    helper_cta_planned INTEGER,
    status TEXT,
    diagnostics_json TEXT
);
CREATE TABLE IF NOT EXISTS shadow_rendered_posts (
    id INTEGER PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    shadow_run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    v2_news_id TEXT,
    post_text TEXT NOT NULL,
    read_more_needed INTEGER,
    read_more_payload TEXT,
    source_link_present INTEGER,
    helper_cta_planned INTEGER,
    status TEXT,
    diagnostics_json TEXT,
    FOREIGN KEY(shadow_run_id) REFERENCES shadow_runs(id)
);
""")
        con.commit()
        return {"v3_db": str(db_path), "v3_db_write": True}
    finally:
        con.close()
