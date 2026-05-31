#!/usr/bin/env python3
import argparse
import hashlib
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from db import add_to_queue_batch

BASE_DIR = Path("/opt/newsbot_v2")
NEWS_DB = BASE_DIR / "news_queue.db"

# These signal types are actionable enough to become publish when signal_level=high.
# This is not a publishing cap. Publisher still decides delivery timing and duplicate guard.
PUBLISH_TYPES = {
    "tariff",
    "api",
    "logistics",
    "returns",
    "storage",
    "penalties",
    "offer",
    "marking",
    "payouts",
    "regulator",
}


def norm(value):
    return str(value or "").strip()


def compact(value):
    return " ".join(norm(value).split())


def group_key_for(row):
    """
    One official post can create several tariff_signals:
    api + logistics + tariff, etc.

    We group signals by the source post identity so that one official post becomes
    one news item in the daily queue.
    """
    source = compact(row["source"])
    marketplace = compact(row["marketplace"])
    link = compact(row["link"])
    title = compact(row["title"])
    news_id = norm(row["news_id"])

    if link:
        base = f"link:{source}|{marketplace}|{link}"
    elif news_id and news_id != "0":
        base = f"news_id:{source}|{marketplace}|{news_id}"
    else:
        base = f"title:{source}|{marketplace}|{title[:220]}"

    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


def make_content_hash(group):
    base = "|".join([
        "official_signal_bridge_grouped",
        group["group_key"],
        group["source"],
        group["marketplace"],
        group["link"],
        group["title"],
        ",".join(group["signal_types"]),
        ",".join(group["signal_levels"]),
    ])
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


def decision_for(group):
    levels = set(group["signal_levels"])
    types = set(group["signal_types"])

    if "high" in levels and (types & PUBLISH_TYPES):
        return "publish"

    if "high" in levels or "medium" in levels:
        return "digest"

    return "ignore"


def score_for(group):
    levels = set(group["signal_levels"])
    types = set(group["signal_types"])

    if "high" in levels:
        rel = 8
        act = 8 if (types & PUBLISH_TYPES) else 5
    elif "medium" in levels:
        rel = 5
        act = 4
    else:
        rel = 2
        act = 1

    # Small boost if several actionable signal types point to the same official post.
    actionable_count = len(types & PUBLISH_TYPES)
    if actionable_count >= 2:
        rel = min(10, rel + 1)
        act = min(10, act + 1)

    return rel, act


def build_group(rows):
    first = rows[0]

    signal_types = sorted({compact(r["signal_type"]).lower() for r in rows if compact(r["signal_type"])})
    signal_levels = sorted({compact(r["signal_level"]).lower() for r in rows if compact(r["signal_level"])})
    signal_ids = [str(r["id"]) for r in rows]

    group_key = group_key_for(first)
    source = compact(first["source"]) or "OFFICIAL"
    marketplace = compact(first["marketplace"]) or "unknown"
    title = compact(first["title"]) or "Официальное обновление маркетплейса"
    link = compact(first["link"]) or f"official-signal-group://{group_key}"
    published_at = compact(first["published_at"])
    detected_at = compact(first["detected_at"])

    return {
        "group_key": group_key,
        "source": source,
        "marketplace": marketplace,
        "title": title,
        "link": link,
        "published_at": published_at,
        "detected_at": detected_at,
        "signal_types": signal_types,
        "signal_levels": signal_levels,
        "signal_ids": signal_ids,
        "rows": rows,
    }


def build_item(group):
    signal_types_label = ", ".join(group["signal_types"]) or "official"
    signal_levels_label = ", ".join(group["signal_levels"]) or "medium"

    raw_text = (
        f"{group['title']}\n\n"
        f"Площадка: {group['marketplace']}\n"
        f"Типы сигналов: {signal_types_label}\n"
        f"Уровни: {signal_levels_label}\n"
        f"Источник: {group['source']}\n"
    )

    if group.get("published_at"):
        raw_text += f"Дата источника: {group['published_at']}\n"

    content_hash = make_content_hash(group)

    return {
        "title": group["title"],
        "description": raw_text,
        "raw_text": raw_text,
        "link": group["link"],
        "url": group["link"],
        "source": group["source"],
        "importance": "high" if "high" in set(group["signal_levels"]) else "normal",
        "category": "marketplace_official",
        "score": 90 if "high" in set(group["signal_levels"]) else 70,
        "priority_bucket": "high" if "high" in set(group["signal_levels"]) else "medium",
        "reason_tags": (
            f"official_signal_bridge_grouped:"
            f"types={signal_types_label}:"
            f"levels={signal_levels_label}:"
            f"group_key={group['group_key']}:"
            f"signal_ids={','.join(group['signal_ids'])}"
        ),
        "content_hash": content_hash,
    }


def already_in_news(cur, group):
    link = group["link"]
    ch = make_content_hash(group)
    group_key = group["group_key"]

    found = cur.execute("""
        SELECT id
        FROM news
        WHERE link = ?
           OR content_hash = ?
           OR reason_tags LIKE ?
        LIMIT 1
    """, (link, ch, f"%group_key={group_key}%")).fetchone()

    return found is not None


def load_signal_groups(cur, lookback_hours, limit):
    rows = cur.execute("""
        SELECT
            id,
            news_id,
            source,
            marketplace,
            signal_type,
            signal_level,
            title,
            link,
            published_at,
            detected_at,
            status
        FROM tariff_signals
        WHERE source LIKE 'OFFICIAL:%'
          AND status IN ('new', 'queued')
          AND datetime(detected_at) >= datetime('now', ?)
          AND signal_level IN ('high', 'medium')
        ORDER BY
          CASE signal_level WHEN 'high' THEN 0 ELSE 1 END,
          datetime(detected_at) DESC,
          id DESC
        LIMIT ?
    """, (f"-{lookback_hours} hours", limit * 5)).fetchall()

    buckets = defaultdict(list)
    for row in rows:
        buckets[group_key_for(row)].append(row)

    groups = [build_group(list(v)) for v in buckets.values()]

    groups.sort(
        key=lambda g: (
            0 if "high" in set(g["signal_levels"]) else 1,
            g.get("detected_at") or "",
            max(int(x) for x in g["signal_ids"] if str(x).isdigit()) if g["signal_ids"] else 0,
        ),
        reverse=False,
    )

    return rows, groups[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(NEWS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    raw_rows, groups = load_signal_groups(cur, args.lookback_hours, args.limit)

    items = []
    decisions = {}
    skipped_existing = 0
    skipped_ignore = 0

    for group in groups:
        decision = decision_for(group)
        if decision == "ignore":
            skipped_ignore += 1
            continue

        if already_in_news(cur, group):
            skipped_existing += 1
            continue

        item = build_item(group)
        rel, act = score_for(group)
        item["seller_decision"] = decision
        item["seller_relevance_score"] = rel
        item["actionability_score"] = act

        items.append(item)
        decisions[item["link"]] = {
            "decision": decision,
            "seller_relevance_score": rel,
            "actionability_score": act,
            "reason": item["reason_tags"],
        }

    conn.close()

    print("official_signal_bridge raw signals checked:", len(raw_rows))
    print("official_signal_bridge groups checked:", len(groups))
    print("official_signal_bridge new grouped items:", len(items))
    print("official_signal_bridge skipped_existing:", skipped_existing)
    print("official_signal_bridge skipped_ignore:", skipped_ignore)

    for item in items[:10]:
        d = decisions[item["link"]]
        print(
            "-",
            d["decision"],
            item["source"],
            f"rel={d['seller_relevance_score']}",
            f"act={d['actionability_score']}",
            item["title"][:140],
        )

    if args.dry_run:
        print("official_signal_bridge dry-run only")
        return 0

    if not items:
        print("official_signal_bridge nothing to queue")
        return 0

    inserted = add_to_queue_batch(items, seller_decisions=decisions)
    print("official_signal_bridge queued via add_to_queue_batch:", inserted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
