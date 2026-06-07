#!/usr/bin/env python3
"""Build a deterministic no-LLM analytics draft from news_queue.db."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALIASES = {
    "wildberries": ("wildberries", "wildberry", "wb", "вб", "вайлдберриз"),
    "ozon": ("ozon", "озон"),
    "yandex_market": ("yandex market", "yandex_market", "яндекс маркет", "яндекс"),
}


def base_dir():
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def q(name):
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn, table):
    return {r[1] for r in conn.execute("PRAGMA table_info(%s)" % q(table))}


def ensure_reports(conn):
    conn.execute("""
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
    )
    """)
    conn.commit()


def row_text(row):
    keys = {"title", "raw_text", "processed_text", "source", "category", "reason_tags", "topic_tags"}
    return " ".join(str(row[k] or "") for k in row.keys() if k in keys).lower()


def matches_marketplace(row, marketplace):
    return marketplace == "all" or any(a in row_text(row) for a in ALIASES[marketplace])


def split_tags(value):
    return [p.strip() for p in re.split(r"[,;|\n]+", value or "") if p.strip()]


def fetch_news(db, days, marketplace, topic):
    if not db.exists():
        raise FileNotFoundError("news_queue.db not found: %s" % db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if not table_exists(conn, "news"):
        conn.close()
        raise RuntimeError("news table is missing in news_queue.db")
    cols = columns(conn, "news")
    wanted = ["id", "title", "raw_text", "processed_text", "link", "source", "category", "reason_tags", "topic_tags", "seller_decision", "seller_relevance_score", "actionability_score", "score", "created_at"]
    selected = [c for c in wanted if c in cols]
    if "id" not in selected:
        raise RuntimeError("news.id column is required")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    where, params = [], []
    if "seller_decision" in cols:
        where.append("seller_decision IN ('publish', 'digest')")
    if "created_at" in cols:
        where.append("created_at >= ?")
        params.append(start.strftime("%Y-%m-%d %H:%M:%S"))
    sql = "SELECT %s FROM news" % ", ".join(q(c) for c in selected)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + ("created_at DESC, id DESC" if "created_at" in cols else "id DESC")
    rows = list(conn.execute(sql, params))
    conn.close()
    rows = [r for r in rows if matches_marketplace(r, marketplace)]
    if topic:
        rows = [r for r in rows if topic.lower() in row_text(r)]
    return rows, start, now


def score(row):
    keys = row.keys()
    rel = int(row["seller_relevance_score"] or 0) if "seller_relevance_score" in keys else 0
    act = int(row["actionability_score"] or 0) if "actionability_score" in keys else 0
    base = int(row["score"] or 0) if "score" in keys else 0
    return rel * 2 + act * 2 + base


def format_counter(counter, limit=8):
    return ", ".join("%s (%s)" % item for item in counter.most_common(limit)) or "none"


def build_report(rows, days, marketplace, topic, start, end):
    label = "all marketplaces" if marketplace == "all" else marketplace
    title = "Analytics draft: %s, last %s days" % (label, days)
    if topic:
        title += " — " + topic
    sources = Counter(str(r["source"] or "unknown") for r in rows if "source" in r.keys())
    decisions = Counter(str(r["seller_decision"] or "unknown") for r in rows if "seller_decision" in r.keys())
    categories = Counter(str(r["category"] or "unknown") for r in rows if "category" in r.keys())
    tags = Counter()
    for r in rows:
        if "reason_tags" in r.keys():
            tags.update(split_tags(r["reason_tags"]))
        if "topic_tags" in r.keys():
            tags.update(split_tags(r["topic_tags"]))
    top = sorted(rows, key=score, reverse=True)[:10]
    top_lines = ["- #%s | %s | source=%s | score=%s" % (r["id"], r["title"], r["source"] if "source" in r.keys() else "unknown", score(r)) for r in top]
    summary = "Period: %s — %s. Filtered seller-relevant news: %s. Marketplace: %s. Topic: %s. No LLM was used." % (start.date(), end.date(), len(rows), label, topic or "all topics")
    findings = ["Total seller-relevant items: %s" % len(rows), "Top sources: " + format_counter(sources), "Seller decisions: " + format_counter(decisions), "Top categories: " + format_counter(categories), "Top tags: " + format_counter(tags, 12), "Top news by relevance/actionability:"] + (top_lines or ["- none"])
    risks = "Potential seller risks to review manually:\n- tariff mentions must be checked against unified_tariffs.db;\n- legal/offer changes require official/legal RAG validation;\n- TG/media signals are context, not calculation inputs."
    actions = "Suggested seller actions:\n- review top-scored items and confirm official sources;\n- compare tariff signals with unified_tariffs.db before pricing changes;\n- prepare manual follow-up for high-actionability changes."
    return {"title": title, "summary": summary, "key_findings": "\n".join(findings), "seller_risks": risks, "seller_actions": actions, "source_news_ids": json.dumps([r["id"] for r in top], ensure_ascii=False)}


def save_report(db, report, days, marketplace, topic, start, end):
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    ensure_reports(conn)
    key = "periodic:%s:%s:%s:%s:%s" % (marketplace, days, start.date(), end.date(), (topic or "all").replace(" ", "_"))
    conn.execute("""
    INSERT INTO analytics_reports (report_key, report_type, marketplace, period_start, period_end, topic, title, summary, key_findings, seller_risks, seller_actions, source_news_ids, status, updated_at)
    VALUES (?, 'periodic_news_draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', CURRENT_TIMESTAMP)
    ON CONFLICT(report_key) DO UPDATE SET title=excluded.title, summary=excluded.summary, key_findings=excluded.key_findings, seller_risks=excluded.seller_risks, seller_actions=excluded.seller_actions, source_news_ids=excluded.source_news_ids, status='draft', updated_at=CURRENT_TIMESTAMP
    """, (key, "multiple" if marketplace == "all" else marketplace, str(start.date()), str(end.date()), topic, report["title"], report["summary"], report["key_findings"], report["seller_risks"], report["seller_actions"], report["source_news_ids"]))
    report_id = conn.execute("SELECT id FROM analytics_reports WHERE report_key=?", (key,)).fetchone()[0]
    conn.commit()
    conn.close()
    return report_id


def main():
    ap = argparse.ArgumentParser(description="Build analytics periodic draft v1 without LLM")
    ap.add_argument("--days", type=int, choices=(7, 30), required=True)
    ap.add_argument("--marketplace", choices=("all", "wildberries", "ozon", "yandex_market"), required=True)
    ap.add_argument("--topic")
    ap.add_argument("--news-db", default=str(base_dir() / "news_queue.db"))
    ap.add_argument("--rag-db", default=str(base_dir() / "data" / "rag_store.db"))
    args = ap.parse_args()
    try:
        rows, start, end = fetch_news(Path(args.news_db), args.days, args.marketplace, args.topic)
        report = build_report(rows, args.days, args.marketplace, args.topic, start, end)
        report_id = save_report(Path(args.rag_db), report, args.days, args.marketplace, args.topic, start, end)
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as exc:
        print("ERROR: %s" % exc)
        return 2
    print("analytics_report_id=%s" % report_id)
    print("news_rows_used=%s" % len(rows))
    print("title=%s" % report["title"])
    for name in ("summary", "key_findings", "seller_risks", "seller_actions"):
        print("\n== %s ==" % name)
        print(report[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
