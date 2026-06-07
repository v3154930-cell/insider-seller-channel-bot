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

PROMO_PHRASES = (
    "мой бот",
    "у меня есть телеграм-бот",
    "подписывайтесь",
    "записаться",
    "успейте",
    "осталось 2 часа",
    "курс",
    "вебинар",
    "промокод",
    "скидка только",
    "личку",
    "закрываем кабинет",
    "есть квоты",
)
PROMO_REASON_TAGS = {"native_ad", "leadgen", "promo", "advertisement"}
PROMO_SOURCE_PATTERNS = (
    "promo",
    "advert",
    "реклама",
    "leadgen",
    "лидген",
    "курс",
    "вебинар",
)
TECHNICAL_TAG_FRAGMENTS = (
    "seller_filter_live",
    "queue_prepare_v3",
    "official_signal_bridge",
    "group_key=",
    "signal_ids=",
    "collector_routing",
    "semantic_duplicate",
    "weak_publish_to_digest",
    "seller_impact_to_publish",
)
TAG_NORMALIZATION = {
    "commission_tariff": "tariffs/commissions",
    "logistics_storage": "logistics/storage",
    "returns_disputes": "returns/disputes",
    "finance_payments": "finance/payments",
    "api": "platform tools/API",
    "offer": "offer/rules",
    "legal": "legal/regulation",
    "certification": "certification/marking",
    "marking": "certification/marking",
}
TOPIC_KEYWORDS = {
    "tariffs/commissions": ("tariff", "commission", "тариф", "комисс"),
    "logistics/storage": ("logistics", "storage", "логист", "хранен", "склад"),
    "returns/disputes": ("return", "dispute", "возврат", "спор", "претензи"),
    "finance/payments": ("finance", "payment", "финанс", "платеж", "выплат"),
    "platform tools/API": ("api", "апи", "кабинет", "бот", "инструмент"),
    "offer/rules": ("offer", "оферт", "правил"),
    "legal/regulation": ("legal", "law", "закон", "регулир", "штраф"),
    "certification/marking": ("certification", "marking", "сертифик", "маркиров"),
}
ACTIONABLE_KEYWORDS = (
    "с 1 ",
    "с 2 ",
    "с 3 ",
    "с 4 ",
    "с 5 ",
    "измен",
    "обяз",
    "требован",
    "повыш",
    "сниж",
    "запуск",
    "перейти",
    "отключ",
    "начнет",
    "начинает",
    "deadline",
    "must",
    "required",
    "тариф",
    "комисс",
    "оферт",
)


def base_dir():
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def q(name):
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn, table):
    return {r[1] for r in conn.execute("PRAGMA table_info(%s)" % q(table))}


def row_get(row, key, default=""):
    try:
        return row[key] if key in row.keys() else default
    except AttributeError:
        return row.get(key, default)
    except (KeyError, IndexError):
        return default


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
    keys = {"title", "raw_text", "processed_text", "source", "category", "reason_tags", "topic_tags", "source_type"}
    return " ".join(str(row_get(row, k, "") or "") for k in keys).lower()


def matches_marketplace(row, marketplace):
    return marketplace == "all" or any(a in row_text(row) for a in ALIASES[marketplace])


def detect_marketplace(row):
    text = row_text(row)
    matches = [name for name, aliases in ALIASES.items() if any(a in text for a in aliases)]
    return matches[0] if len(matches) == 1 else ("multiple" if matches else "unknown")


def split_tags(value):
    return [p.strip() for p in re.split(r"[,;|\n]+", value or "") if p.strip()]


def is_technical_tag(tag):
    value = (tag or "").lower()
    return any(fragment in value for fragment in TECHNICAL_TAG_FRAGMENTS)


def normalize_tag(tag):
    value = (tag or "").strip()
    lowered = value.lower()
    if not value or is_technical_tag(value):
        return None
    if lowered in TAG_NORMALIZATION:
        return TAG_NORMALIZATION[lowered]
    for key, normalized in TAG_NORMALIZATION.items():
        if key in lowered:
            return normalized
    if len(value) > 80 or "=" in value:
        return None
    return value.replace("_", " ")


def human_tags(row):
    tags = []
    for field in ("reason_tags", "topic_tags"):
        for tag in split_tags(str(row_get(row, field, "") or "")):
            normalized = normalize_tag(tag)
            if normalized:
                tags.append(normalized)
    return tags


def is_promotional_row(row):
    text = row_text(row)
    reason_tags = {tag.lower() for tag in split_tags(str(row_get(row, "reason_tags", "") or ""))}
    source_title = " ".join(str(row_get(row, key, "") or "") for key in ("source", "title")).lower()
    return (
        any(phrase in text for phrase in PROMO_PHRASES)
        or bool(PROMO_REASON_TAGS.intersection(reason_tags))
        or any(pattern in source_title for pattern in PROMO_SOURCE_PATTERNS)
    )


def is_official_row(row):
    source = str(row_get(row, "source", "") or "").strip().lower()
    source_type = str(row_get(row, "source_type", "") or "").strip().lower()
    return source.startswith("official:") or source_type == "official"


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    candidates = (
        (text[:19], "%Y-%m-%d %H:%M:%S"),
        (text[:19], "%Y-%m-%dT%H:%M:%S"),
        (text[:10], "%Y-%m-%d"),
    )
    for candidate, fmt in candidates:
        try:
            dt = datetime.strptime(candidate, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def detect_topic(row):
    tags = human_tags(row)
    for tag in tags:
        if tag in TOPIC_KEYWORDS:
            return tag
    text = row_text(row)
    for topic, needles in TOPIC_KEYWORDS.items():
        if any(needle in text for needle in needles):
            return topic
    return "other"


def fetch_news(db, days, marketplace, topic):
    if not db.exists():
        raise FileNotFoundError("news_queue.db not found: %s" % db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if not table_exists(conn, "news"):
        conn.close()
        raise RuntimeError("news table is missing in news_queue.db")
    cols = columns(conn, "news")
    wanted = ["id", "title", "raw_text", "processed_text", "link", "source", "source_type", "category", "reason_tags", "topic_tags", "seller_decision", "seller_relevance_score", "actionability_score", "score", "created_at"]
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
        topic_lower = topic.lower()
        rows = [r for r in rows if topic_lower in row_text(r) or topic_lower in " ".join(human_tags(r)).lower()]
    return rows, start, now


def score(row, start=None, end=None):
    rel = int(row_get(row, "seller_relevance_score", 0) or 0)
    act = int(row_get(row, "actionability_score", 0) or 0)
    base = int(row_get(row, "score", 0) or 0)
    value = rel * 2 + act * 3 + base
    text = row_text(row)
    if is_official_row(row):
        value += 35
    if any(needle in text for needle in ACTIONABLE_KEYWORDS):
        value += 12
    if detect_marketplace(row) == "unknown":
        value -= 5
    if is_promotional_row(row):
        value -= 1000
    created_at = parse_datetime(row_get(row, "created_at", ""))
    if created_at and start and end and end > start:
        age_ratio = max(0.0, min(1.0, (end - created_at).total_seconds() / (end - start).total_seconds()))
        value -= int(age_ratio * 10)
    return value


def format_counter(counter, limit=8):
    return ", ".join("%s (%s)" % item for item in counter.most_common(limit)) or "none"


def format_item(row, start=None, end=None):
    title = str(row_get(row, "title", "untitled") or "untitled").strip().replace("\n", " ")
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    source = str(row_get(row, "source", "unknown") or "unknown")
    market = detect_marketplace(row)
    official = "official" if is_official_row(row) else "context"
    return "- #%s | %s | %s | %s | source=%s | score=%s" % (row_get(row, "id", "?"), title, market, official, source, score(row, start, end))


def top_items(rows, limit, start, end):
    return sorted(rows, key=lambda row: score(row, start, end), reverse=True)[:limit]


def build_report(rows, days, marketplace, topic, start, end, limit_top=10, include_filtered_debug=False):
    label = "all marketplaces" if marketplace == "all" else marketplace
    title = "Analytics draft: %s, last %s days" % (label, days)
    if topic:
        title += " — " + topic

    filtered_rows = [r for r in rows if is_promotional_row(r)]
    clean_rows = [r for r in rows if not is_promotional_row(r)]
    official_rows = [r for r in clean_rows if is_official_row(r)]
    context_rows = [r for r in clean_rows if not is_official_row(r)]

    marketplaces = Counter(detect_marketplace(r) for r in clean_rows)
    topics = Counter(detect_topic(r) for r in clean_rows)
    tags = Counter()
    for r in clean_rows:
        tags.update(human_tags(r))

    official_top = top_items(official_rows, min(limit_top, 5), start, end)
    context_top = top_items(context_rows, min(limit_top, 5), start, end)
    top = top_items(clean_rows, limit_top, start, end)
    validation = top_items(context_rows, min(limit_top, 5), start, end)

    summary = "\n".join([
        "Period: %s — %s." % (start.date(), end.date()),
        "Marketplace: %s. Topic: %s." % (label, topic or "all topics"),
        "Total seller-relevant rows: %s." % len(rows),
        "Official signals: %s." % len(official_rows),
        "TG/media context rows: %s." % len(context_rows),
        "Filtered promo/native/leadgen rows from top ranking: %s." % len(filtered_rows),
        "No LLM was used.",
    ])

    findings = [
        "official_signals:",
        "- count: %s" % len(official_rows),
        *(format_item(r, start, end) for r in official_top),
        "marketplace_breakdown: " + format_counter(marketplaces),
        "topic_breakdown: " + format_counter(topics),
        "contextual_tg_media_signals:",
        *(format_item(r, start, end) for r in context_top),
        "clean_top_tags: " + format_counter(tags, 12),
        "top_news_by_score_after_promo_filtering:",
        *(format_item(r, start, end) for r in top),
        "needs_official_validation:",
        *(format_item(r, start, end) for r in validation),
        "filtered_out_summary:",
        "- promo/native/leadgen rows excluded from top ranking: %s" % len(filtered_rows),
    ]
    if include_filtered_debug:
        findings.append("filtered_out_debug_examples:")
        findings.extend(format_item(r, start, end) for r in top_items(filtered_rows, min(limit_top, 5), start, end))
    if not official_top:
        findings.insert(2, "- none")
    if not context_top:
        context_idx = findings.index("contextual_tg_media_signals:")
        findings.insert(context_idx + 1, "- none")
    if not top:
        top_idx = findings.index("top_news_by_score_after_promo_filtering:")
        findings.insert(top_idx + 1, "- none")
    if not validation:
        validation_idx = findings.index("needs_official_validation:")
        findings.insert(validation_idx + 1, "- none")

    risks = "\n".join([
        "seller_risks:",
        "- Tariff signals require unified_tariffs.db validation before seller-facing numeric conclusions.",
        "- TG/media context requires official marketplace confirmation.",
        "- Legal/offer signals require legal official RAG validation.",
        "needs_official_validation:",
        *(format_item(r, start, end) for r in validation),
    ])
    if not validation:
        risks += "\n- none"
    actions = "\n".join([
        "seller_actions:",
        "- Check official marketplace sources for the top changes above.",
        "- Update Seller Helper tariff inputs only after official validation against unified_tariffs.db.",
        "- Prepare follow-up for high-actionability marketplace changes.",
    ])
    return {
        "title": title,
        "summary": summary,
        "key_findings": "\n".join(findings),
        "seller_risks": risks,
        "seller_actions": actions,
        "source_news_ids": json.dumps([row_get(r, "id") for r in top], ensure_ascii=False),
    }


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
    ap.add_argument("--limit-top", type=int, default=10)
    ap.add_argument("--include-filtered-debug", action="store_true")
    ap.add_argument("--news-db", default=str(base_dir() / "news_queue.db"))
    ap.add_argument("--rag-db", default=str(base_dir() / "data" / "rag_store.db"))
    args = ap.parse_args()
    try:
        rows, start, end = fetch_news(Path(args.news_db), args.days, args.marketplace, args.topic)
        report = build_report(rows, args.days, args.marketplace, args.topic, start, end, args.limit_top, args.include_filtered_debug)
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
