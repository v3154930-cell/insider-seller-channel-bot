import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")

LOOKBACK_DAYS = int(os.getenv("OFFICIAL_SIGNAL_LOOKBACK_DAYS", "3"))

SIGNAL_RULES = {
    "tariff": [
        "тариф", "тарифы", "комиссия", "комиссии", "ставка", "ставки",
        "вознаграждение", "стоимость услуг"
    ],
    "offer": [
        "оферта", "договор", "условия", "правила", "регламент",
        "вступит в силу", "вступает в силу"
    ],
    "logistics": [
        "логистика", "доставка", "склад", "fbo", "fbs", "dbs",
        "экспресс", "фулфилмент", "fulfillment", "fulfilment"
    ],
    "returns": [
        "возврат", "возвраты", "невыкуп", "отмена заказа", "брак"
    ],
    "storage": [
        "хранение", "размещение", "платное хранение"
    ],
    "payouts": [
        "выплата", "выплаты", "расчеты", "расчёты",
        "взаиморасчеты", "взаиморасчёты", "деньги", "банк"
    ],
    "penalties": [
        "штраф", "штрафы", "удержание", "удержания", "блокировка"
    ],
    "api": [
        "api", "апи", "метод", "методы", "лимит", "лимиты",
        "интеграция", "интеграции", "отчет", "отчёт", "endpoint",
        "post /", "get /", "release notes"
    ],
    "marking": [
        "маркировка", "честный знак", "киз", "код маркировки"
    ],
    "regulator": [
        "фас", "роспотребнадзор", "минпромторг", "минцифры",
        "закон", "регулятор"
    ],
}

STRONG_WORDS = [
    "измен", "обнов", "вступит в силу", "вступает в силу",
    "с 1 ", "с 01.", "с 18 мая", "новые правила",
    "новый метод", "новые методы", "ограничим", "лимит",
    "лимиты", "повыш", "сниж", "теперь", "запрет"
]

NOISE_WORDS = [
    "конкурс", "розыгрыш", "мерч", "вебинар", "эфир", "подкаст",
    "обучение", "акция", "промо", "распродажа"
]


STRICT_OFFICIAL_DROP_WORDS = [
    "подарки",
    "выигрывайте",
    "праздничн",
    "джем",
    "день рождения",
    "в честь этого события",
    "яндекс банка",
    "яндекс банк",
    "быстрые выплаты",
    "график работы",
    "майские праздники",
    "длинные выходные",
    "если планируете отдых",
]


STRICT_OFFICIAL_KEEP_WORDS = [
    "изменится",
    "изменятся",
    "изменили",
    "изменяем",
    "обновим лимиты",
    "обновили лимиты",
    "лимиты методов",
    "ограничим",
    "вступит в силу",
    "вступает в силу",
    "новые правила",
    "обновили оферту",
    "обновил оферту",
    "тарифы",
    "комиссии",
    "стоимость услуг",
    "новый api-метод",
    "новый метод",
    "изменения в методах",
    "изменения в отчет",
    "изменения в отчёт",
    "возвраты",
    "маркировка",
    "штраф",
    "штрафы",
    "удержания",
]


def is_publishable_official_signal_text(text: str) -> bool:
    t = norm(text)

    if any(w in t for w in STRICT_OFFICIAL_DROP_WORDS):
        return False

    return any(w in t for w in STRICT_OFFICIAL_KEEP_WORDS)


def norm(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_dt(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def is_recent(published_at: str, collected_at: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    dt = parse_dt(published_at) or parse_dt(collected_at)
    if not dt:
        return True

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt >= cutoff


def detect_signal_types(text: str):
    t = norm(text)
    result = []

    for signal_type, words in SIGNAL_RULES.items():
        if any(w in t for w in words):
            result.append(signal_type)

    return result


def score_signal(text: str, signal_types):
    t = norm(text)
    score = 2  # official_channel baseline trust boost

    score += len(signal_types) * 2

    for w in STRONG_WORDS:
        if w in t:
            score += 2

    if "оферта" in t or "тариф" in t or "комисси" in t or "api" in t or "лимит" in t:
        score += 2

    if any(w in t for w in NOISE_WORDS):
        score -= 3

    if score >= 9:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def ensure_tariff_signals(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tariff_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        news_id INTEGER,
        source TEXT,
        marketplace TEXT,
        signal_type TEXT,
        signal_level TEXT,
        title TEXT,
        link TEXT,
        published_at TEXT,
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new',
        reason TEXT,
        UNIQUE(news_id, signal_type)
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_tariff_signals_status ON tariff_signals(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tariff_signals_marketplace ON tariff_signals(marketplace)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tariff_signals_type ON tariff_signals(signal_type)")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ensure_tariff_signals(cur)

    table_exists = cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name='official_channel_posts'
    """).fetchone()

    if not table_exists:
        print("official_channel_posts table not found")
        return

    rows = cur.execute("""
        SELECT
            id,
            source_name,
            marketplace,
            title,
            raw_text,
            link,
            published_at,
            collected_at
        FROM official_channel_posts
        ORDER BY id DESC
        LIMIT 300
    """).fetchall()

    checked = 0
    skipped_old = 0
    inserted = 0

    for row in rows:
        checked += 1

        if not is_recent(row["published_at"], row["collected_at"]):
            skipped_old += 1
            continue

        title = row["title"] or ""
        raw_text = row["raw_text"] or ""
        full = f"{title}\n{raw_text}"

        signal_types = detect_signal_types(full)
        if not signal_types:
            continue

        # Строгий фильтр official-каналов:
        # не тащим промо, подарки, банковский маркетинг и графики праздников
        # в монитор изменений условий/тарифов.
        if not is_publishable_official_signal_text(full):
            continue

        level = score_signal(full, signal_types)

        if level == "low" and not any(s in signal_types for s in ["tariff", "offer", "api", "regulator"]):
            continue

        pseudo_news_id = -int(row["id"])

        for signal_type in signal_types:
            reason = f"official_channel; matched signal_type={signal_type}; level={level}"

            cur.execute("""
            INSERT OR IGNORE INTO tariff_signals (
                news_id,
                source,
                marketplace,
                signal_type,
                signal_level,
                title,
                link,
                published_at,
                detected_at,
                status,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
            """, (
                pseudo_news_id,
                row["source_name"],
                row["marketplace"],
                signal_type,
                level,
                title[:500],
                row["link"],
                row["published_at"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                reason
            ))

            if cur.rowcount:
                inserted += 1

    conn.commit()

    print("official_signal_monitor done")
    print("checked official posts:", checked)
    print("skipped old posts:", skipped_old)
    print("inserted official signals:", inserted)

    print()
    print("latest official signals:")
    for r in cur.execute("""
        SELECT id, news_id, source, marketplace, signal_type, signal_level, substr(title,1,120) AS title, status
        FROM tariff_signals
        WHERE source LIKE 'OFFICIAL:%'
        ORDER BY id DESC
        LIMIT 30
    """):
        print(dict(r))

    conn.close()


if __name__ == "__main__":
    main()
