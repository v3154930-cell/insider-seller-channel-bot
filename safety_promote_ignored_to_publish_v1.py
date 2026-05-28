#!/usr/bin/env python3
import os
import sqlite3
from datetime import datetime, date

DB = "/opt/newsbot_v2/news_queue.db"
MIN_WEEKDAY_TARGET = 10
MIN_WEEKEND_TARGET = 3
BATCH_LIMIT = 1  # promote one candidate at a time; publication frequency is controlled by cron/time window

DRY_RUN = os.getenv("NEWSBOT_SAFETY_PROMOTE_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "y"}

HARD_POSITIVE = [
    "выплат", "приостановк", "оферт", "комисси", "тариф", "логист",
    "доставк", "карточк", "маркирован", "остатк", "честный знак",
    "налог", "кабинет", "реклам", "продвиж", "пвз", "возврат",
    "штраф", "блокиров", "склад", "приемк", "приёмк", "fbo", "fbs", "dbs",
    "ozon доставка", "ozon", "озон", "wildberries", "wb", "вайлдберриз",
    "яндекс маркет", "маркетплейс", "селлер", "продавц"
]

SOFT_POSITIVE = [
    "рост заказ", "онлайн-заказ", "покупател", "спрос", "импорт",
    "тамож", "похожие товары", "витрин", "ресейл", "оригинал",
    "личном кабинете", "сервис", "товар", "ассортимент"
]

NEGATIVE = [
    "топ telegram", "top telegram", "подписаться", "подпишитесь",
    "рассылка", "email-рассыл", "usdt", "whitebird", "цфа",
    "плавающей ставкой", "альфа-банк", "банк запустил", "кешбэк",
    "премиальный сервис", "миль", "путешествен", "акционер",
    "акции афк", "доля в ozon", "доля в wb", "инвестор",
    "конференц", "круглый стол", "вебинар", "мероприят",
    "приглаша", "зарегистр", "15 июня", "13:00", "22 мая",
    "день предпринимателя", "поздравляем", "ваканс", "карьера",
    "студентов", "школьников", "опрос", "тендер", "tiktok",
    "тик ток", "тикток", "рекламное агентство"
]

def norm(value):
    return str(value or "").lower()

def text_of(row):
    return " ".join([
        norm(row["title"]),
        norm(row["raw_text"]),
        norm(row["processed_text"]),
        norm(row["reason_tags"]),
        norm(row["category"]),
        norm(row["source"]),
    ])

def has_any(text, words):
    return any(w in text for w in words)

def rank_row(row):
    text = text_of(row)
    base_score = int(row["score"] or 0)

    if has_any(text, NEGATIVE):
        return None, "negative_filter"

    hard_hits = sum(1 for w in HARD_POSITIVE if w in text)
    soft_hits = sum(1 for w in SOFT_POSITIVE if w in text)

    if hard_hits == 0 and soft_hits == 0:
        return None, "no_seller_signal"

    if base_score < 40 and hard_hits < 2:
        return None, "score_too_low"

    rank = base_score + hard_hits * 25 + soft_hits * 8

    decision = norm(row["seller_decision"])
    if decision == "digest":
        rank += 20
    elif decision == "ignore":
        rank -= 20

    source = norm(row["source"])
    if "oborot" in source or "marketplace_biz" in source or "mpgo" in source:
        rank += 10

    return rank, f"rank={rank} hard_hits={hard_hits} soft_hits={soft_hits}"

today_obj = date.today()
today = today_obj.isoformat()
since = today + " 00:00:00"
min_daily_target = MIN_WEEKEND_TARGET if today_obj.weekday() >= 5 else MIN_WEEKDAY_TARGET

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

published_today = con.execute("""
    SELECT COUNT(*) AS c
    FROM news
    WHERE is_published = 1
      AND seller_decision = 'publish'
      AND created_at >= ?
""", (since,)).fetchone()["c"]

pending_publish = con.execute("""
    SELECT COUNT(*) AS c
    FROM news
    WHERE IFNULL(is_published,0) = 0
      AND seller_decision = 'publish'
""").fetchone()["c"]

minimum_met = published_today >= min_daily_target
# IMPORTANT PROJECT POLICY:
# min_daily_target is a minimum floor, not a maximum cap.
# Weekdays: at least 10. Weekends: at least 3.
# Upper bound is only publication time window + availability of good candidates.
# Therefore we must NOT stop just because minimum is already met.

if pending_publish > 0:
    print(f"SKIP already has pending_publish={pending_publish}")
    raise SystemExit(0)

need = BATCH_LIMIT

rows = con.execute("""
    SELECT id, created_at, source, score, title, raw_text, processed_text,
           reason_tags, category, seller_decision
    FROM news
    WHERE created_at >= ?
      AND IFNULL(is_published,0) = 0
      AND IFNULL(max_message_id,'') = ''
      AND seller_decision IN ('digest', 'ignore')
    ORDER BY score DESC, created_at DESC
    LIMIT 120
""", (since,)).fetchall()

scored = []
skipped = []

for r in rows:
    rank, reason = rank_row(r)
    if rank is None:
        skipped.append((r, reason))
        continue
    scored.append((rank, reason, r))

scored.sort(key=lambda x: (x[0], int(x[2]["score"] or 0), str(x[2]["created_at"] or "")), reverse=True)
selected = scored[:need]
ids = [r["id"] for _, _, r in selected]

print(
    f"SAFETY_CHECK at={datetime.now().isoformat(timespec='seconds')} "
    f"published_today={published_today} pending_publish={pending_publish} "
    f"need={need} candidates={len(scored)} selected={ids} dry_run={DRY_RUN}"
)

print("TOP_CANDIDATES:")
for rank, reason, r in scored[:15]:
    print(
        f"CANDIDATE #{r['id']} rank={rank} score={r['score']} "
        f"decision={r['seller_decision']} source={r['source']} reason={reason} "
        f"title={(r['title'] or '')[:180]}"
    )

print("TOP_SKIPPED:")
for r, reason in skipped[:10]:
    print(
        f"SKIP #{r['id']} score={r['score']} decision={r['seller_decision']} "
        f"source={r['source']} reason={reason} title={(r['title'] or '')[:160]}"
    )

if ids and not DRY_RUN:
    q = ",".join("?" for _ in ids)
    con.execute(f"""
        UPDATE news
        SET seller_decision = 'publish',
            seller_relevance_score = CASE
                WHEN IFNULL(seller_relevance_score,0) < 8 THEN 8
                ELSE seller_relevance_score
            END,
            actionability_score = CASE
                WHEN IFNULL(actionability_score,0) < 7 THEN 7
                ELSE actionability_score
            END
        WHERE id IN ({q})
          AND IFNULL(is_published,0) = 0
          AND IFNULL(max_message_id,'') = ''
          AND seller_decision IN ('digest', 'ignore')
    """, ids)
    con.commit()

con.close()
print(f"DONE promoted={0 if DRY_RUN else len(ids)} selected={ids}")
