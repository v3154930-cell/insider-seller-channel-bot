#!/usr/bin/env python3
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


MARKETPLACE_HINTS = ('ozon', 'wb', 'wildberries', 'seller', 'продав', 'маркетплейс', 'fbo', 'fbs')


def fetch_one(cur, q, p=()):
    cur.execute(q, p)
    r = cur.fetchone()
    return r[0] if r else None


def row_to_text(row):
    if not row:
        return None
    return " | ".join([str(x) for x in row if x is not None])


def parse_dt(v):
    if not v:
        return None
    txt = str(v).strip().replace('T', ' ')
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def get_table_columns(cur, table_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def col_expr(columns, col_name, fallback="NULL"):
    if col_name in columns:
        return col_name
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="news_queue.db")
    ap.add_argument("--collector-log", default="logs/newsbot_collector.log")
    ap.add_argument("--publisher-log", default="logs/newsbot_publisher.log")
    args = ap.parse_args()

    now = datetime.now().astimezone()
    local_hour = now.hour
    publisher_window_active = 7 <= local_hour < 21

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news'")
    if not cur.fetchone():
        print("final_status=WARN")
        print("warning=no_news_table_in_db")
        return

    news_columns = get_table_columns(cur, "news")
    text_field_priority = ["title", "raw_text", "summary", "reason_tags", "source"]
    available_text_fields = [f for f in text_field_priority if f in news_columns]
    text_expr = " || ' ' || ".join([f"IFNULL({f},'')" for f in available_text_fields]) if available_text_fields else "''"

    is_published_expr = f"IFNULL({col_expr(news_columns, 'is_published')},0)"
    seller_decision_expr = f"IFNULL({col_expr(news_columns, 'seller_decision')},'')"
    seller_rel_expr = f"IFNULL({col_expr(news_columns, 'seller_relevance_score')},0)"
    actionability_expr = f"IFNULL({col_expr(news_columns, 'actionability_score')},0)"
    created_at_expr = col_expr(news_columns, "created_at")

    pending_publish = fetch_one(cur, f"SELECT COUNT(*) FROM news WHERE {is_published_expr}=0 AND {seller_decision_expr}='publish'") or 0
    digest_total = fetch_one(cur, f"SELECT COUNT(*) FROM news WHERE {is_published_expr}=0 AND {seller_decision_expr}='digest'") or 0
    digest_pass_threshold = fetch_one(cur, f"SELECT COUNT(*) FROM news WHERE {is_published_expr}=0 AND {seller_decision_expr}='digest' AND {seller_rel_expr}>=3 AND {actionability_expr}>=3") or 0
    ignore_total = fetch_one(cur, f"SELECT COUNT(*) FROM news WHERE {is_published_expr}=0 AND {seller_decision_expr}='ignore'") or 0
    published_today = fetch_one(cur, f"SELECT COUNT(*) FROM news WHERE {is_published_expr}=1 AND date(COALESCE({col_expr(news_columns, 'full_article_published_at', created_at_expr)}, {created_at_expr}))=date('now')") or 0
    last_post_time = fetch_one(cur, f"SELECT MAX({created_at_expr}) FROM news WHERE {is_published_expr}=1")

    cur.execute(f"""
        SELECT
          SUM(CASE WHEN {seller_rel_expr}>=5 AND {actionability_expr}>=5 THEN 1 ELSE 0 END),
          SUM(CASE WHEN {seller_rel_expr}>=3 AND {actionability_expr}>=3 THEN 1 ELSE 0 END),
          SUM(CASE WHEN {seller_rel_expr}<3 OR {actionability_expr}<3 THEN 1 ELSE 0 END)
        FROM news
        WHERE {is_published_expr}=0 AND {seller_decision_expr}='digest'
    """)
    b = cur.fetchone()
    digest_bucket_strong = b[0] or 0
    digest_bucket_mid = b[1] or 0
    digest_bucket_low = b[2] or 0

    cur.execute(f"""
      SELECT id, source, title, {seller_rel_expr} rel, {actionability_expr} act, {created_at_expr} created_at
      FROM news
      WHERE {is_published_expr}=0 AND {seller_decision_expr}='digest'
      ORDER BY rel DESC, act DESC, created_at DESC
      LIMIT 10
    """)
    top_digest = cur.fetchall()

    like_clauses = " OR ".join([f"LOWER({text_expr}) LIKE '%{kw}%'" for kw in MARKETPLACE_HINTS])
    cur.execute(f"""
      SELECT id, source, title, {seller_rel_expr} rel, {actionability_expr} act
      FROM news
      WHERE {is_published_expr}=0 AND {seller_decision_expr}='ignore' AND ({like_clauses})
      ORDER BY {created_at_expr} DESC LIMIT 10
    """)
    possible_seller_ignore = cur.fetchall()

    cur.execute(f"""
        SELECT id, source, title, {seller_rel_expr} rel, {actionability_expr} act, IFNULL({col_expr(news_columns, 'reason_tags', "''")},'') reason_tags
        FROM news
        WHERE {seller_decision_expr}='duplicate' AND {is_published_expr}=0
        ORDER BY {created_at_expr} DESC
    """)
    all_dup_rows = cur.fetchall()
    strong_official_duplicates = [r for r in all_dup_rows if str(r['source'] or '').upper().startswith('OFFICIAL') and r['rel'] >= 5 and r['act'] >= 5]
    strong_nonofficial_duplicates = [r for r in all_dup_rows if not str(r['source'] or '').upper().startswith('OFFICIAL') and r['rel'] >= 5 and r['act'] >= 5]
    high_dup_rows = [r for r in all_dup_rows if r['rel'] >= 3 and r['act'] >= 3]

    collector_log = Path(args.collector_log)
    publisher_log = Path(args.publisher_log)
    collector_lines = collector_log.read_text(encoding='utf-8', errors='ignore').splitlines() if collector_log.exists() else []
    publisher_lines = publisher_log.read_text(encoding='utf-8', errors='ignore').splitlines() if publisher_log.exists() else []

    latest_seller_decisions = next((ln for ln in reversed(collector_lines) if 'Seller decisions' in ln), None)
    latest_publish_selected_fresh = next((ln for ln in reversed(collector_lines) if 'publish_selected_fresh' in ln), None)
    latest_invariant_broken = next((ln for ln in reversed(collector_lines) if 'INVARIANT_BROKEN' in ln), None)

    last_publisher_run = next((ln for ln in reversed(publisher_lines) if 'publisher' in ln.lower() or 'run' in ln.lower()), None)
    last_selected_ids = next((ln for ln in reversed(publisher_lines) if 'selected ids' in ln.lower() or 'selected_ids' in ln.lower()), None)
    last_posted_id = next((ln for ln in reversed(publisher_lines) if 'Posted id' in ln or 'posted id' in ln.lower()), None)
    last_no_pending = next((ln for ln in reversed(publisher_lines) if 'No pending' in ln or 'no pending' in ln.lower()), None)

    collector_last_ts = row_to_text(fetch_one(cur, f"SELECT MAX({created_at_expr}) FROM news", ()))

    strong_candidates_exist = digest_pass_threshold > 0 or len(high_dup_rows) > 0 or len(possible_seller_ignore) > 0
    last_post_dt = parse_dt(last_post_time)
    no_recent_publication = True if not last_post_dt else ((now.replace(tzinfo=None) - last_post_dt).total_seconds() > 6 * 3600)

    if latest_invariant_broken:
        final = "BROKEN"
        recommended_next_action = "investigate_collector_invariant"
    elif published_today >= 3:
        final = "OK"
        recommended_next_action = "daily_target_met"
    elif pending_publish > 0:
        final = "OK"
        recommended_next_action = "run_stable_publisher"
    elif strong_candidates_exist:
        final = "WARN"
        recommended_next_action = "run_stable_publisher_v3"
    else:
        final = "WARN"
        recommended_next_action = "wait_for_collector_or_review_scoring"

    print(f"current_local_time={now.isoformat()}")
    print(f"current_local_hour={local_hour}")
    print(f"publisher_window_7_21_active={'YES' if publisher_window_active else 'NO'}")

    print(f"collector_last_log_timestamp={collector_lines[-1][:23] if collector_lines else 'n/a'}")
    print(f"collector_latest_seller_decisions={latest_seller_decisions or 'n/a'}")
    print(f"collector_latest_publish_selected_fresh={latest_publish_selected_fresh or 'n/a'}")
    print(f"collector_latest_invariant_broken={latest_invariant_broken or 'none'}")

    print(f"publisher_last_run_timestamp={publisher_lines[-1][:23] if publisher_lines else 'n/a'}")
    print(f"publisher_last_selected_ids={last_selected_ids or 'n/a'}")
    print(f"publisher_last_posted_id={last_posted_id or 'n/a'}")
    print(f"publisher_last_no_pending={last_no_pending or 'n/a'}")

    print(f"pending_publish={pending_publish}")
    print(f"digest_total={digest_total}")
    print(f"digest_pass_threshold={digest_pass_threshold}")
    print(f"digest_relact_buckets=strong:{digest_bucket_strong},mid:{digest_bucket_mid},low:{digest_bucket_low}")
    for r in top_digest:
        print(f"digest_top id={r['id']} source={r['source']} rel={r['rel']} act={r['act']} title={r['title']}")

    print(f"ignore_total={ignore_total}")
    for r in possible_seller_ignore:
        print(f"ignore_seller_like id={r['id']} source={r['source']} rel={r['rel']} act={r['act']} title={r['title']}")

    print(f"strong_official_duplicates={len(strong_official_duplicates)}")
    print(f"strong_nonofficial_duplicates={len(strong_nonofficial_duplicates)}")
    for r in high_dup_rows[:20]:
        print(f"duplicate_rel3_act3 id={r['id']} source={r['source']} rel={r['rel']} act={r['act']} title={r['title']} reason_tags={r['reason_tags']}")

    print(f"published_today={published_today}")
    print(f"last_post_time={last_post_time}")
    print(f"final_status={final}")
    print(f"recommended_next_action={recommended_next_action}")


if __name__ == "__main__":
    main()
