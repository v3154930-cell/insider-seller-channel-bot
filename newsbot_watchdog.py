#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path("/opt/newsbot_v2")
NEWS_DB = BASE_DIR / "news_queue.db"
ENV_PATH = BASE_DIR / ".env"
DEFAULT_API_BASE = "https://botapi.max.ru"


def load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_state_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS newsbot_watchdog_state (
            alert_key TEXT PRIMARY KEY,
            last_sent_at TEXT,
            sent_count INTEGER DEFAULT 0,
            last_payload TEXT
        )
    """)


def scalar(cur, sql, params=()):
    row = cur.execute(sql, params).fetchone()
    if not row:
        return 0
    return int(row[0] or 0)


def get_status(silence_hours, lookback_hours, daily_target, min_rel, min_act):
    conn = sqlite3.connect(NEWS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ensure_state_table(cur)

    silence_arg = f"-{silence_hours} hours"
    lookback_arg = f"-{lookback_hours} hours"

    published_recent = scalar(cur, """
        SELECT COUNT(*)
        FROM news
        WHERE is_published = 1
          AND seller_decision = 'publish'
          AND datetime(created_at) >= datetime('now', ?)
    """, (silence_arg,))

    published_today = scalar(cur, """
        SELECT COUNT(*)
        FROM news
        WHERE is_published = 1
          AND seller_decision = 'publish'
          AND date(created_at) = date('now')
    """)

    pending_publish = scalar(cur, """
        SELECT COUNT(*)
        FROM news
        WHERE IFNULL(is_published,0)=0
          AND seller_decision='publish'
    """)

    strong_digest = scalar(cur, """
        SELECT COUNT(*)
        FROM news
        WHERE IFNULL(is_published,0)=0
          AND seller_decision='digest'
          AND datetime(created_at) >= datetime('now', ?)
          AND IFNULL(seller_relevance_score,0) >= ?
          AND IFNULL(actionability_score,0) >= ?
    """, (lookback_arg, min_rel, min_act))

    fresh_unpublished = scalar(cur, """
        SELECT COUNT(*)
        FROM news
        WHERE IFNULL(is_published,0)=0
          AND datetime(created_at) >= datetime('now', ?)
          AND seller_decision IN ('publish','digest')
    """, (lookback_arg,))

    last_publish = cur.execute("""
        SELECT id, created_at, substr(title,1,160) AS title
        FROM news
        WHERE is_published=1
          AND seller_decision='publish'
        ORDER BY datetime(created_at) DESC
        LIMIT 1
    """).fetchone()

    top_pending = cur.execute("""
        SELECT id, created_at, seller_decision, seller_relevance_score, actionability_score, substr(title,1,140) AS title
        FROM news
        WHERE IFNULL(is_published,0)=0
          AND seller_decision IN ('publish','digest')
        ORDER BY
          CASE seller_decision WHEN 'publish' THEN 0 ELSE 1 END,
          actionability_score DESC,
          seller_relevance_score DESC,
          datetime(created_at) DESC
        LIMIT 5
    """).fetchall()

    conn.commit()
    conn.close()

    return {
        "published_recent": published_recent,
        "published_today": published_today,
        "pending_publish": pending_publish,
        "strong_digest": strong_digest,
        "fresh_unpublished": fresh_unpublished,
        "last_publish": dict(last_publish) if last_publish else None,
        "top_pending": [dict(r) for r in top_pending],
        "daily_target": daily_target,
        "silence_hours": silence_hours,
        "lookback_hours": lookback_hours,
        "min_rel": min_rel,
        "min_act": min_act,
    }


def should_alert(status):
    if status["published_recent"] > 0:
        return False, "recent publish exists"

    if status["pending_publish"] > 0:
        return True, "есть publish-кандидаты, но нет публикаций в окне молчания"

    if status["published_today"] < status["daily_target"] and status["strong_digest"] > 0:
        return True, "дневная норма не добрана, есть сильные digest-кандидаты, но публикаций нет"

    if status["published_today"] < status["daily_target"] and status["fresh_unpublished"] > 0:
        return True, "есть свежие неопубликованные кандидаты, но канал молчит"

    return False, "no actionable silence"


def cooldown_allows(alert_key, cooldown_minutes, payload):
    conn = sqlite3.connect(NEWS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ensure_state_table(cur)

    row = cur.execute(
        "SELECT last_sent_at, sent_count FROM newsbot_watchdog_state WHERE alert_key=?",
        (alert_key,),
    ).fetchone()

    now = datetime.now(timezone.utc)
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")

    allowed = True
    if row and row["last_sent_at"]:
        try:
            last = datetime.strptime(row["last_sent_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            delta_min = (now - last).total_seconds() / 60
            if delta_min < cooldown_minutes:
                allowed = False
        except Exception:
            pass

    if allowed:
        if row:
            cur.execute("""
                UPDATE newsbot_watchdog_state
                SET last_sent_at=?, sent_count=COALESCE(sent_count,0)+1, last_payload=?
                WHERE alert_key=?
            """, (now_s, json.dumps(payload, ensure_ascii=False), alert_key))
        else:
            cur.execute("""
                INSERT INTO newsbot_watchdog_state(alert_key, last_sent_at, sent_count, last_payload)
                VALUES (?, ?, 1, ?)
            """, (alert_key, now_s, json.dumps(payload, ensure_ascii=False)))

    conn.commit()
    conn.close()
    return allowed


def build_message(status, reason):
    lines = []
    lines.append("🚨 <b>NEWSBOT watchdog</b>")
    lines.append("Канал может молчать при наличии материала.")
    lines.append("")
    lines.append(f"<b>Причина:</b> {reason}")
    lines.append(f"<b>Публикаций за последние {status['silence_hours']} ч:</b> {status['published_recent']}")
    lines.append(f"<b>Publish сегодня:</b> {status['published_today']} / {status['daily_target']}")
    lines.append(f"<b>Pending publish:</b> {status['pending_publish']}")
    lines.append(f"<b>Сильные digest за {status['lookback_hours']} ч:</b> {status['strong_digest']}")
    lines.append(f"<b>Свежие publish/digest неопубликованные:</b> {status['fresh_unpublished']}")

    if status["last_publish"]:
        lp = status["last_publish"]
        lines.append("")
        lines.append("<b>Последняя publish-новость:</b>")
        lines.append(f"#{lp.get('id')} · {lp.get('created_at')}")
        lines.append(str(lp.get("title") or ""))

    if status["top_pending"]:
        lines.append("")
        lines.append("<b>Первые кандидаты в очереди:</b>")
        for r in status["top_pending"]:
            lines.append(
                f"• #{r.get('id')} · {r.get('seller_decision')} · "
                f"rel={r.get('seller_relevance_score')} act={r.get('actionability_score')} · "
                f"{r.get('title')}"
            )

    lines.append("")
    lines.append("Проверь: collector → DB → publisher, quota fallback, duplicate guard.")
    return "\n".join(lines)


def send_to_admin(text):
    token = os.getenv("ADMIN_ALERT_BOT_TOKEN") or os.getenv("MAX_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_ALERT_CHAT_ID") or os.getenv("MAX_ADMIN_CHAT_ID")
    api_base = os.getenv("MAX_API_BASE") or DEFAULT_API_BASE

    if not token:
        raise RuntimeError("ADMIN_ALERT_BOT_TOKEN / MAX_BOT_TOKEN not set")
    if not chat_id:
        raise RuntimeError("ADMIN_ALERT_CHAT_ID / MAX_ADMIN_CHAT_ID not set")

    url = f"{api_base}/messages?chat_id={chat_id}"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"text": text},
        timeout=20,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"MAX API error {resp.status_code}: {resp.text[:500]}")
    return resp.json()



def effective_daily_target(explicit_target=0):
    """
    Returns the minimum daily publish target.
    This is a fallback/watchdog minimum, not a publishing cap.
    Weekdays: PUBLISH_WEEKDAY_TARGET / PUBLISH_DAILY_TARGET / 10.
    Weekends: PUBLISH_WEEKEND_TARGET / 3.
    """
    try:
        explicit_target = int(explicit_target or 0)
    except Exception:
        explicit_target = 0

    if explicit_target > 0:
        return explicit_target

    weekday_target = int(os.getenv("PUBLISH_WEEKDAY_TARGET", os.getenv("PUBLISH_DAILY_TARGET", "10")) or "10")
    weekend_target = int(os.getenv("PUBLISH_WEEKEND_TARGET", "3") or "3")

    try:
        from zoneinfo import ZoneInfo
        weekday = datetime.now(ZoneInfo(os.getenv("NEWSBOT_TZ", "Europe/Moscow"))).weekday()
    except Exception:
        weekday = datetime.now().weekday()

    return weekend_target if weekday >= 5 else weekday_target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--silence-hours", type=int, default=int(os.getenv("WATCHDOG_SILENCE_HOURS", "2")))
    parser.add_argument("--lookback-hours", type=int, default=int(os.getenv("WATCHDOG_LOOKBACK_HOURS", "3")))
    parser.add_argument("--daily-target", type=int, default=int(os.getenv("WATCHDOG_DAILY_TARGET", "0") or "0"))
    parser.add_argument("--cooldown-minutes", type=int, default=int(os.getenv("WATCHDOG_COOLDOWN_MINUTES", "120")))
    parser.add_argument("--min-rel", type=int, default=int(os.getenv("PUBLISH_FALLBACK_MIN_RELEVANCE", "2")))
    parser.add_argument("--min-act", type=int, default=int(os.getenv("PUBLISH_FALLBACK_MIN_ACTIONABILITY", "2")))
    args = parser.parse_args()

    load_env()

    status = get_status(
        silence_hours=args.silence_hours,
        lookback_hours=args.lookback_hours,
        daily_target=effective_daily_target(args.daily_target),
        min_rel=args.min_rel,
        min_act=args.min_act,
    )

    alert, reason = should_alert(status)
    print("WATCHDOG STATUS:", json.dumps(status, ensure_ascii=False, indent=2))
    print("WATCHDOG DECISION:", "ALERT" if alert else "OK", "-", reason)

    if not alert:
        return 0

    msg = build_message(status, reason)
    if not cooldown_allows("newsbot_silence_watchdog", args.cooldown_minutes, status):
        print("WATCHDOG: alert suppressed by cooldown")
        return 0

    if args.send:
        result = send_to_admin(msg)
        print("WATCHDOG: alert sent")
        print(result)
    else:
        print("WATCHDOG: dry run only")
        print(msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
