#!/usr/bin/env python3
import os
import sqlite3
from datetime import datetime

from seller_filter import evaluate_item

DB_PATH = os.getenv("NEWSBOT_DB_PATH", "/opt/newsbot_v2/news_queue.db")
LOOKBACK_DAYS = int(os.getenv("PROMOTE_LOOKBACK_DAYS", "3"))
MAX_PROMOTE = int(os.getenv("PROMOTE_MAX_PER_RUN", "1"))
MIN_HOURS_BETWEEN_AUTO_PROMOTE = int(os.getenv("PROMOTE_MIN_HOURS_BETWEEN", "3"))

BAD_TITLE_PARTS = [
    "подписаться",
    "реклама",
    "дайджест каналов",
    "скидка",
    "промокод",
    "whitebird",
    "signup",
    "refid",
    "курс",
    "ваканси",
    "бюллетень",
]


def norm(v):
    return (v or "").strip()


def is_bad(row):
    text = (norm(row["title"]) + " " + norm(row["raw_text"]) + " " + norm(row["processed_text"])).lower()
    return any(x in text for x in BAD_TITLE_PARTS)


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Не поднимаем новые digest-кандидаты, если уже есть publish в очереди.
    pending_publish = con.execute(
        """
        SELECT COUNT(*)
        FROM news
        WHERE is_published = 0
          AND seller_decision = 'publish'
        """
    ).fetchone()[0]
    if pending_publish:
        print(f"SUMMARY skip=already_has_pending_publish count={pending_publish} db={DB_PATH} at={datetime.now().isoformat(timespec='seconds')}")
        con.close()
        return

    # Не чаще одного автоподнятия раз в несколько часов, чтобы не выгребать старый digest-бэклог.
    recent_auto = con.execute(
        """
        SELECT COUNT(*)
        FROM news
        WHERE reason_tags LIKE '%auto_promoted_by_seller_filter%'
          AND datetime(created_at) >= datetime('now','localtime', '-3 days')
          AND id IN (
              SELECT id FROM news
              WHERE max_message_id IS NOT NULL
                 OR is_published = 1
                 OR seller_decision = 'publish'
          )
        """
    ).fetchone()[0]

    published_today = con.execute(
        """
        SELECT COUNT(*)
        FROM news
        WHERE is_published = 1
          AND date(created_at) = date('now','localtime')
        """
    ).fetchone()[0]

    if published_today >= int(os.getenv("PROMOTE_MAX_PUBLISHED_TODAY", "6")):
        print(f"SUMMARY skip=published_today_limit published_today={published_today} db={DB_PATH} at={datetime.now().isoformat(timespec='seconds')}")
        con.close()
        return

    rows = con.execute(
        """
        SELECT
            id,
            title,
            raw_text,
            processed_text,
            link,
            source,
            importance,
            category,
            score,
            priority_bucket,
            reason_tags,
            seller_decision,
            seller_relevance_score,
            actionability_score,
            created_at
        FROM news
        WHERE is_published = 0
          AND COALESCE(seller_decision, '') IN ('digest', 'pending', '')
          AND datetime(created_at) >= datetime('now','localtime', ?)
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 300
        """,
        (f"-{LOOKBACK_DAYS} days",),
    ).fetchall()

    promoted = 0
    checked = 0

    for row in rows:
        checked += 1

        if promoted >= MAX_PROMOTE:
            break

        if is_bad(row):
            continue

        item = {
            "title": norm(row["title"]),
            "description": norm(row["processed_text"]) or norm(row["raw_text"]) or norm(row["title"]),
            "raw_text": norm(row["raw_text"]),
            "processed_text": norm(row["processed_text"]),
            "link": norm(row["link"]),
            "source": norm(row["source"]),
            "importance": norm(row["importance"]),
            "category": norm(row["category"]),
            "score": row["score"] or 0,
            "priority_bucket": norm(row["priority_bucket"]),
            "reason_tags": norm(row["reason_tags"]),
        }

        try:
            decision = evaluate_item(item)
        except Exception as e:
            print(f"SKIP id={row['id']} filter_error={e}")
            continue

        d = decision.get("decision")
        rel = int(decision.get("seller_relevance_score") or 0)
        act = int(decision.get("actionability_score") or 0)
        reason = norm(decision.get("reason"))

        if d == "publish" and rel >= 5 and act >= 5:
            con.execute(
                """
                UPDATE news
                SET
                    seller_decision = 'publish',
                    seller_relevance_score = ?,
                    actionability_score = ?,
                    reason_tags = COALESCE(reason_tags, '') || ' | auto_promoted_by_seller_filter: ' || ?
                WHERE id = ?
                  AND is_published = 0
                """,
                (rel, act, reason, row["id"]),
            )
            promoted += 1
            print(f"PROMOTED id={row['id']} score={rel}/{act} reason={reason} title={norm(row['title'])[:120]}")

    con.commit()
    con.close()

    print(f"SUMMARY checked={checked} promoted={promoted} db={DB_PATH} at={datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
