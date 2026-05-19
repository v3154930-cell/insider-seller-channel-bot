#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path("/opt/newsbot_v2")
DBS = [
    ROOT / "news_queue.db",
    ROOT / "data" / "rag_store.db",
    ROOT / "data" / "unified_tariffs.db",
]

SCAN_FILES = [
    "collector_v2.py",
    "seller_filter.py",
    "official_sources_v2.py",
    "telegram_sources_v2.py",
    "telegram_json_sources_v2.py",
    "rss_sources.py",
    "sources.py",
    "signal_monitor.py",
    "signal_digest.py",
    "publisher_v2.py",
]

URL_RE = re.compile(r'(https?://[^\s\'"<>]+|t\.me/[A-Za-z0-9_/\-?=&.]+|@[A-Za-z0-9_]+)', re.I)

def print_header(title):
    print()
    print("=" * 120)
    print(title)
    print("=" * 120)

def inspect_db(path: Path):
    print_header(f"DB: {path}")
    if not path.exists():
        print("NOT FOUND")
        return

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        tables = [r["name"] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]

        print("TABLES:", ", ".join(tables) if tables else "none")

        for table in tables:
            try:
                count = cur.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            except Exception as e:
                count = f"ERR {e}"

            print()
            print(f"--- {table} | rows={count} ---")

            try:
                cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
                col_names = [c["name"] for c in cols]
                print("columns:", ", ".join(col_names))
            except Exception as e:
                print("columns error:", e)
                continue

            # Показываем источники, если таблица похожа на source/news/rag.
            lowered = [c.lower() for c in col_names]
            useful_cols = [
                c for c in col_names
                if c.lower() in (
                    "source", "source_name", "source_url", "url", "channel", "channel_name",
                    "source_type", "marketplace", "rag_layer", "trust_level",
                    "enabled", "title", "seller_decision", "score", "created_at",
                    "published_at", "is_published", "in_digest"
                )
            ]

            if useful_cols:
                select_cols = ", ".join(useful_cols[:10])
                try:
                    rows = cur.execute(
                        f"SELECT {select_cols} FROM {table} ORDER BY rowid DESC LIMIT 20"
                    ).fetchall()
                    for r in rows:
                        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
                except Exception as e:
                    print("sample error:", e)

        conn.close()
    except Exception as e:
        print("DB INSPECT ERROR:", repr(e))

def scan_file(path: Path):
    print_header(f"FILE SCAN: {path}")
    if not path.exists():
        print("NOT FOUND")
        return

    text = path.read_text(encoding="utf-8", errors="ignore")
    urls = []
    for m in URL_RE.finditer(text):
        u = m.group(0).strip()
        if u not in urls:
            urls.append(u)

    if not urls:
        print("No URLs/channels found")
    else:
        for u in urls[:200]:
            print(u)

    print()
    print("--- lines with source/channel keywords ---")
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(k in low for k in ["source", "rss", "telegram", "t.me", "channel", "источник", "канал"]):
            if len(line.strip()) > 0:
                print(f"{i}: {line[:220]}")

def inspect_recent_news():
    path = ROOT / "news_queue.db"
    print_header("RECENT NEWS BY SOURCE / DECISION")
    if not path.exists():
        print("news_queue.db not found")
        return

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Ищем таблицу news и её поля.
    tables = [r["name"] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    if "news" not in tables:
        print("table news not found")
        conn.close()
        return

    cols = [r["name"] for r in cur.execute("PRAGMA table_info(news)").fetchall()]
    print("news columns:", ", ".join(cols))

    source_col = "source" if "source" in cols else None
    decision_col = "seller_decision" if "seller_decision" in cols else None

    if source_col and decision_col:
        print()
        print("--- counts by source and seller_decision ---")
        try:
            rows = cur.execute("""
                SELECT source, seller_decision, COUNT(*) AS c
                FROM news
                GROUP BY source, seller_decision
                ORDER BY c DESC
                LIMIT 80
            """).fetchall()
            for r in rows:
                print(f"{r['c']:>5} | {r['seller_decision'] or '' :<8} | {r['source']}")
        except Exception as e:
            print("counts error:", e)

    print()
    print("--- last 40 news ---")
    wanted = [c for c in ["id", "source", "title", "seller_decision", "score", "is_published", "in_digest", "created_at", "published_at"] if c in cols]
    if wanted:
        try:
            rows = cur.execute(
                f"SELECT {', '.join(wanted)} FROM news ORDER BY id DESC LIMIT 40"
            ).fetchall()
            for r in rows:
                print(" | ".join(f"{k}={r[k]}" for k in r.keys()))
        except Exception as e:
            print("last news error:", e)

    conn.close()

def main():
    print("SOURCE INVENTORY")
    print("time:", datetime.now().isoformat(timespec="seconds"))
    print("root:", ROOT)

    for db in DBS:
        inspect_db(db)

    inspect_recent_news()

    print_header("PYTHON FILES WITH SOURCES")
    for name in SCAN_FILES:
        scan_file(ROOT / name)

    print_header("FIND SOURCE-LIKE FILES")
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in [".py", ".json", ".yaml", ".yml", ".txt", ".md"]:
            continue
        name = p.name.lower()
        if any(k in name for k in ["source", "telegram", "rss", "channel", "collector"]):
            print(p)

if __name__ == "__main__":
    main()
