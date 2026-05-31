#!/usr/bin/env python3
import sqlite3
from datetime import date, datetime

DB = "/opt/newsbot_v2/news_queue.db"
DAILY_TARGET = 10
BATCH_LIMIT = 1
FAIL_OPEN_MIN_PUBLISHED = 3

GOOD_MARKERS = [
    "ozon", "озон", "wildberries", "wb", "вайлдберриз", "яндекс маркет",
    "маркетплейс", "селлер", "продавец", "продавцов", "кабинет селлера",
    "отзывы", "рейтинг", "тариф", "комиссия", "логистика", "возврат", "пвз",
]

BAD_MARKERS = [
    "нефть", "нефтяным", "бумажного ндс", "epharma", "аптек", "цфа",
    "баранов", "отели", "usdt", "telegram-каналов",
]


def marker_hits(text: str, markers: list[str]) -> list[str]:
    return [m for m in markers if m in text]


def main() -> None:
    today = date.today().isoformat()
    since = today + " 00:00:00"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    published_today = con.execute(
        """
        SELECT COUNT(*) AS c
        FROM news
        WHERE is_published = 1
          AND seller_decision = 'publish'
          AND created_at >= ?
    """,
        (since,),
    ).fetchone()["c"]

    pending_publish = con.execute(
        """
        SELECT COUNT(*) AS c
        FROM news
        WHERE IFNULL(is_published,0) = 0
          AND seller_decision = 'publish'
    """
    ).fetchone()["c"]

    if published_today >= DAILY_TARGET:
        print(f"INFO daily minimum already satisfied published_today={published_today} target={DAILY_TARGET}")

    if pending_publish > 0:
        print(f"SKIP already has pending_publish={pending_publish}")
        raise SystemExit(0)

    need = BATCH_LIMIT

    selected: list[sqlite3.Row] = []
    candidate_rows: list[sqlite3.Row] = []

    if pending_publish == 0:
        print(
            f"PROMOTE enabled published_today={published_today} "
            f"pending_publish={pending_publish} need={need}"
        )

        candidate_rows = con.execute(
            """
            SELECT id, created_at, source, score, title, raw_text,
                   seller_decision, seller_relevance_score, actionability_score
            FROM news
            WHERE IFNULL(is_published,0) = 0
              AND seller_decision IN ('digest', 'ignore', 'duplicate')
            ORDER BY IFNULL(score,0) DESC, created_at DESC
            LIMIT 200
        """
        ).fetchall()

        ranked: list[tuple[int, sqlite3.Row, list[str], list[str], str]] = []
        for r in candidate_rows:
            blob = " ".join(
                [
                    (r["title"] or ""),
                    (r["raw_text"] or ""),
                    (r["source"] or ""),
                ]
            ).lower()
            good_hits = marker_hits(blob, GOOD_MARKERS)
            bad_hits = marker_hits(blob, BAD_MARKERS)

            if bad_hits:
                print(
                    f"REJECT #{r['id']} reason=bad_markers bad={bad_hits} "
                    f"score={r['score']} decision={r['seller_decision']} "
                    f"title={(r['title'] or '')[:180]}"
                )
                continue

            if not good_hits:
                print(
                    f"REJECT #{r['id']} reason=no_good_markers score={r['score']} "
                    f"decision={r['seller_decision']} title={(r['title'] or '')[:180]}"
                )
                continue

            rank = len(good_hits) * 1000 + int(r["score"] or 0)
            explain = f"good={good_hits} score={r['score']} decision={r['seller_decision']}"
            ranked.append((rank, r, good_hits, bad_hits, explain))

        ranked.sort(key=lambda x: (x[0], x[1]["created_at"]), reverse=True)
        selected = [x[1] for x in ranked[:need]]

        for _, r, good_hits, _, explain in ranked:
            verdict = "SELECT" if any(s["id"] == r["id"] for s in selected) else "REJECT"
            print(
                f"{verdict} #{r['id']} explain={explain} "
                f"title={(r['title'] or '')[:180]}"
            )

    ids = [r["id"] for r in selected]

    print(
        f"SAFETY_CHECK at={datetime.now().isoformat(timespec='seconds')} "
        f"published_today={published_today} pending_publish={pending_publish} need={need} selected={ids}"
    )

    if not ids:
        print("no_seller_like_candidates")

    if ids:
        q = ",".join("?" for _ in ids)
        con.execute(
            f"""
            UPDATE news
            SET seller_decision = 'publish',
                seller_relevance_score = CASE
                    WHEN IFNULL(seller_relevance_score,0) < 4 THEN 4
                    ELSE seller_relevance_score
                END,
                actionability_score = CASE
                    WHEN IFNULL(actionability_score,0) < 4 THEN 4
                    ELSE actionability_score
                END
            WHERE id IN ({q})
              AND IFNULL(is_published,0) = 0
      AND COALESCE(seller_relevance_score,0) >= 5
      AND COALESCE(actionability_score,0) >= 5
        """,
            ids,
        )
        con.commit()

    pending_after = con.execute(
        """
        SELECT COUNT(*) AS c
        FROM news
        WHERE IFNULL(is_published,0) = 0
          AND seller_decision = 'publish'
    """
    ).fetchone()["c"]

    print(f"DONE promoted={len(ids)} pending_publish_after={pending_after}")


if __name__ == "__main__":
    main()
