import argparse
import html
import os
import re
import sqlite3
from pathlib import Path

from publisher import send_message

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")
ENV_PATH = Path("/opt/newsbot_v2/.env")


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def norm(value: str) -> str:
    value = (value or "").lower().replace("ё", "е")
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"[^a-zа-я0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE tariff_signals ADD COLUMN urgency TEXT DEFAULT 'daily'")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE tariff_signals ADD COLUMN urgent_published_at TEXT")
    except Exception:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS urgent_signal_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_key TEXT UNIQUE NOT NULL,
        title TEXT,
        sources TEXT,
        source_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'published',
        published_at TEXT DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_tariff_signals_urgency ON tariff_signals(urgency)")

    conn.commit()
    conn.close()


def classify_urgency(title: str, source: str = "") -> str:
    t = norm(title)
    s = norm(source)

    # Срочно: только явные регуляторные/тарифные/блокирующие события.
    if "фас" in t and ("предупреж" in t or "потребовала" in t or "маркетплейс" in t):
        return "urgent"

    if ("с 1 мая" in t or "с 01 05" in t or "с завтрашнего дня" in t or "с сегодняшнего дня" in t) and (
        "тариф" in t or "комисси" in t or "логистик" in t or "оферт" in t
    ):
        return "urgent"

    if ("блокиров" in t or "запрет" in t or "обязаны" in t or "штраф" in t or "маркировк" in t) and (
        "госдума" in t or "фас" in t or "роспотребнадзор" in t or "честный знак" in t
    ):
        # Не все такие сигналы надо сразу публиковать. Если это не официальный источник,
        # лучше оставить на вечерний монитор, кроме явно критичных случаев.
        if source.startswith("OFFICIAL:"):
            return "urgent"
        return "daily"

    if ("api" in s or "api" in t) and (
        "сегодня изменятся лимиты" in t
        or "завтра изменятся лимиты" in t
        or "критично для интеграци" in t
        or "сломать интеграци" in t
    ):
        return "urgent"

    if (
        "изменятся лимиты" in t
        or "обновим лимиты" in t
        or "изменения в методах" in t
        or "новый метод" in t
        or "вступит в силу" in t
        or "новые правила" in t
    ):
        return "daily"

    return "archive"


def event_key(row: dict) -> str:
    title = norm(row.get("title"))
    marketplace = row.get("marketplace") or "unknown"
    news_id = row.get("news_id")

    if "фас" in title and ("маркетплейс" in title or "ozon" in title or "wildberries" in title or "выплат" in title):
        return "fas_marketplace_conditions"

    if "туркменистан" in title and "ozon" in title and ("тариф" in title or "логистик" in title):
        return "ozon_turkmenistan_logistics_tariffs"

    if "честный знак" in title and ("блокиров" in title or "продаж" in title):
        return "regulator_honest_sign_blocking"

    if "оферт" in title and ("обнов" in title or "вступит в силу" in title):
        return f"offer_update:{marketplace}"

    if ("api" in title or "лимит" in title or "метод" in title) and marketplace:
        return f"api_or_limits:{marketplace}:{title[:80]}"

    if news_id is not None:
        return f"news:{news_id}"

    return "title:" + title[:160]


def get_existing_event_keys():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT event_key
        FROM urgent_signal_events
        WHERE status = 'published'
    """).fetchall()

    conn.close()
    return {r[0] for r in rows}


def backfill_urgency_for_new():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT id, title, source
        FROM tariff_signals
        WHERE status = 'new'
    """).fetchall()

    updated = 0

    for row in rows:
        urgency = classify_urgency(row["title"] or "", row["source"] or "")
        cur.execute(
            "UPDATE tariff_signals SET urgency = ? WHERE id = ?",
            (urgency, row["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()

    print("urgency classified for new signals:", updated)


def get_urgent_groups(limit=5):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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
            urgency
        FROM tariff_signals
        WHERE status = 'new'
          AND urgency = 'urgent'
        ORDER BY id DESC
        LIMIT ?
    """, (limit * 50,)).fetchall()

    conn.close()

    published_keys = get_existing_event_keys()
    groups = {}

    for row in rows:
        item = dict(row)
        key = event_key(item)

        if key in published_keys:
            continue

        if key not in groups:
            groups[key] = {
                "event_key": key,
                "representative": item,
                "ids": [item["id"]],
                "news_ids": set([item.get("news_id")]),
                "sources": set([item.get("source") or "источник не указан"]),
            }
        else:
            groups[key]["ids"].append(item["id"])
            groups[key]["news_ids"].add(item.get("news_id"))
            groups[key]["sources"].add(item.get("source") or "источник не указан")

    result = list(groups.values())
    result.sort(key=lambda g: max(g["ids"]), reverse=True)
    return result[:limit]


def mp_label(mp: str) -> str:
    return {
        "ozon": "Ozon",
        "wildberries": "Wildberries",
        "yandex_market": "Яндекс Маркет",
        "multiple": "несколько площадок",
        "unknown": "не определено",
    }.get(mp or "unknown", mp or "не определено")


def clean_title(title: str) -> str:
    title = " ".join((title or "").split())
    title = title.replace("нар...", "нарушения")
    title = title.replace("Д...", "Детали — в полном тексте.")
    if len(title) > 300:
        title = title[:297].rstrip() + "…"
    return title


def build_message(group: dict) -> str:
    signal = group["representative"]

    title = html.escape(clean_title(signal.get("title") or ""))
    marketplace = html.escape(mp_label(signal.get("marketplace")))
    sources = sorted(s for s in group["sources"] if s)
    sources_text = html.escape(", ".join(sources[:5]))

    lines = []
    lines.append("🚨 <b>Срочный сигнал для селлеров</b>")
    lines.append("")
    lines.append(f"<b>Площадка:</b> {marketplace}")
    lines.append(f"<b>Что обнаружено:</b> {title}")
    lines.append("")
    lines.append("<b>Что сделать:</b> проверить официальный источник и оценить влияние на товары, выплаты, оферту, API или расчёты.")
    lines.append(f"<b>Источники:</b> {sources_text}")
    lines.append("<b>Ссылка:</b> сохранена в базе для ручной проверки.")
    lines.append("")
    lines.append("ℹ️ Сигнал не меняет расчёт Seller Helper автоматически. Числовые тарифы обновляются только после проверки официального источника.")

    return "\n".join(lines)


def get_positive_news_id(group: dict):
    news_ids = [x for x in group.get("news_ids", set()) if isinstance(x, int) and x > 0]
    return min(news_ids) if news_ids else None


def save_max_message_id(news_id: int, send_result: dict):
    if not news_id:
        return

    try:
        mid = send_result["message"]["body"]["mid"]
    except Exception:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE news SET max_message_id = ? WHERE id = ?",
            (mid, news_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_group_published(group: dict):
    event_key_value = group["event_key"]
    rep = group["representative"]
    title = rep.get("title") or ""
    sources = sorted(s for s in group["sources"] if s)
    ids = group["ids"]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO urgent_signal_events (
            event_key,
            title,
            sources,
            source_count,
            status,
            published_at
        )
        VALUES (?, ?, ?, ?, 'published', CURRENT_TIMESTAMP)
    """, (
        event_key_value,
        title,
        ", ".join(sources),
        len(sources),
    ))

    placeholders = ",".join(["?"] * len(ids))

    cur.execute(f"""
        UPDATE tariff_signals
        SET status = 'urgent_published',
            urgent_published_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
    """, ids)

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Actually publish urgent signals")
    args = parser.parse_args()

    load_env()
    ensure_schema()
    backfill_urgency_for_new()

    groups = get_urgent_groups()

    if not groups:
        print("No urgent signals to publish.")
        return

    print("urgent event groups:", len(groups))

    token = os.getenv("MAX_BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID") or os.getenv("MAX_CHANNEL_ID")

    if args.publish and (not token or not channel_id):
        raise RuntimeError("MAX_BOT_TOKEN or CHANNEL_ID/MAX_CHANNEL_ID not found")

    for group in groups:
        text = build_message(group)
        news_id = get_positive_news_id(group)

        print()
        print("EVENT:", group["event_key"])
        print("SIGNAL IDS:", group["ids"])
        print("NEWS_ID FOR FULL ARTICLE:", news_id)
        print(text)

        if not args.publish:
            print()
            print("DRY RUN: not published. Use --publish to send.")
            continue

        print()
        print("=== publishing urgent event ===")
        result = send_message(
            token,
            channel_id,
            text,
            add_helper_button=False,
            full_article_news_id=news_id,
            add_full_article_button=True if news_id else False,
        )
        print("publisher.send_message result:", result)

        save_max_message_id(news_id, result)
        mark_group_published(group)


if __name__ == "__main__":
    main()
