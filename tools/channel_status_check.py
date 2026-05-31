#!/usr/bin/env python3
import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import py_compile


@dataclass
class Status:
    level: str
    reason: str
    recommended_action: str
    published_today: int = 0
    pending_publish: int = 0
    digest_unpublished: int = 0
    seller_like_candidates: int = 0
    last_published_at: str = ""
    collector_recent: bool = False
    publisher_recent_error: bool = False
    daily_min_target: int = 10


def parse_ts(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def is_recent_file(path: Path, hours: int) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - mtime <= timedelta(hours=hours)


def has_recent_error(path: Path, hours: int) -> bool:
    if not path.exists():
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) < cutoff:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")[-200000:]
    for m in ("ERROR_SEND", "ERROR_DB", "ERROR_SELECT"):
        if m in text:
            return True
    return False


def _daily_min_target(now_local: datetime) -> int:
    return 3 if now_local.weekday() >= 5 else 10

def check(args) -> Status:
    env_missing = [k for k in ("MAX_BOT_TOKEN", "CHANNEL_ID") if not os.getenv(k, "").strip()]
    try:
        py_compile.compile(str(Path(__file__).resolve().parents[1] / "stable_publisher_v3.py"), doraise=True)
    except Exception:
        return Status("BROKEN", "stable_publisher_not_compilable", "manual_investigation")
    if env_missing:
        return Status("BROKEN", "missing_required_env", "check_env")

    dbp = Path(args.db)
    if not dbp.exists():
        return Status("BROKEN", "db_not_found", "check_logs")

    try:
        conn = sqlite3.connect(str(dbp))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news'")
        if not cur.fetchone():
            return Status("BROKEN", "news_table_missing", "manual_investigation")

        published_today = int(cur.execute("SELECT COUNT(*) FROM news WHERE is_published=1 AND DATE(COALESCE(full_article_published_at, created_at))=DATE('now','localtime')").fetchone()[0])
        pending_publish = int(cur.execute("SELECT COUNT(*) FROM news WHERE is_published=0 AND seller_decision='publish'").fetchone()[0])
        digest_unpublished = int(cur.execute("SELECT COUNT(*) FROM news WHERE is_published=0 AND seller_decision IN ('digest','ignore')").fetchone()[0])
        seller_like_candidates = int(cur.execute("SELECT COUNT(*) FROM news WHERE is_published=0 AND (LOWER(COALESCE(title,'')||' '||COALESCE(raw_text,'')) LIKE '%селлер%' OR LOWER(COALESCE(title,'')||' '||COALESCE(raw_text,'')) LIKE '%seller%' OR LOWER(COALESCE(title,'')||' '||COALESCE(raw_text,'')) LIKE '%комис%' OR LOWER(COALESCE(title,'')||' '||COALESCE(raw_text,'')) LIKE '%маркетплейс%')").fetchone()[0])
        publishable_fallback_candidates = int(cur.execute("SELECT COUNT(*) FROM news WHERE is_published=0 AND seller_decision IN ('digest','ignore','duplicate','pending') AND COALESCE(seller_relevance_score,0) >= 2 AND COALESCE(actionability_score,0) >= 2").fetchone()[0])
        last_published_at = cur.execute("SELECT COALESCE(full_article_published_at, created_at) FROM news WHERE is_published=1 ORDER BY datetime(COALESCE(full_article_published_at, created_at)) DESC LIMIT 1").fetchone()
        last_published_at = last_published_at[0] if last_published_at else ""
    except sqlite3.Error:
        return Status("BROKEN", "db_schema_error", "manual_investigation")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    collector_recent = is_recent_file(Path(args.collector_log), args.recent_hours)
    daily_min_target = _daily_min_target(datetime.now().astimezone())
    publisher_recent_error = has_recent_error(Path(args.publisher_log), args.error_hours)
    last_pub_dt = parse_ts(last_published_at)
    last_pub_recent = bool(last_pub_dt and datetime.now(timezone.utc) - last_pub_dt.astimezone(timezone.utc) <= timedelta(hours=args.publish_stale_hours))

    if publisher_recent_error:
        return Status("BROKEN", "publisher_recent_error", "check_logs", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, True, daily_min_target)
    if pending_publish > 0:
        return Status("OK", "pending_publish_present", "do_nothing", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
    if published_today >= daily_min_target and pending_publish == 0:
        has_candidates = digest_unpublished > 0 or seller_like_candidates > 0
        if collector_recent and has_candidates:
            if publishable_fallback_candidates > 0:
                return Status("WARN_PUBLISHABLE_CANDIDATES", "daily_min_done_publishable_candidates_exist", "publish_or_review", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
            return Status("OK_LOW_VALUE_ONLY", "daily_min_done_only_low_value_candidates", "publish_or_review", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
        return Status("OK_NO_NEWS", "daily_min_done_no_pending", "do_nothing", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
    if pending_publish == 0 and seller_like_candidates == 0 and collector_recent and last_pub_recent:
        return Status("OK_NO_NEWS", "publisher_alive_queue_empty_no_seller_candidates", "do_nothing", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
    if pending_publish == 0 and not collector_recent:
        return Status("WARN", "collector_stale", "run_collector", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
    if pending_publish == 0 and digest_unpublished > 0 and seller_like_candidates > 0:
        return Status("WARN", "possible_scoring_filter_issue", "review_scoring", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)
    return Status("WARN", "low_traffic_needs_review", "run_stable_publisher_dry_run", published_today, pending_publish, digest_unpublished, seller_like_candidates, last_published_at, collector_recent, False, daily_min_target)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--collector-log", required=True)
    p.add_argument("--publisher-log", required=True)
    p.add_argument("--recent-hours", type=int, default=6)
    p.add_argument("--error-hours", type=int, default=12)
    p.add_argument("--publish-stale-hours", type=int, default=72)
    args = p.parse_args()
    s = check(args)
    print(f"CHANNEL_STATUS={s.level}")
    print(f"reason={s.reason}")
    print(f"daily_min_target={s.daily_min_target}")
    print(f"published_today={s.published_today}")
    print(f"pending_publish={s.pending_publish}")
    print(f"digest_unpublished={s.digest_unpublished}")
    print(f"seller_like_candidates={s.seller_like_candidates}")
    print(f"last_published_at={s.last_published_at}")
    print(f"collector_recent={str(s.collector_recent).lower()}")
    print(f"publisher_recent_error={str(s.publisher_recent_error).lower()}")
    print(f"recommended_action={s.recommended_action}")


if __name__ == "__main__":
    main()
