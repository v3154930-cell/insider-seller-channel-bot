import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")

SIGNAL_RULES = {
    "tariff": [
        "тариф", "тарифы", "комиссия", "комиссии", "ставка", "ставки",
        "вознаграждение", "стоимость услуг", "изменение стоимости",
        "marketplace_service_rate", "service rate"
    ],
    "offer": [
        "оферта", "договор", "условия", "правила", "изменения условий",
        "регламент", "документ вступит в силу", "вступит в силу"
    ],
    "logistics": [
        "логистика", "доставка", "склад", "fbo", "fbs", "dbs",
        "экспресс", "сортировочный центр", "последняя миля"
    ],
    "returns": [
        "возврат", "возвраты", "обратная логистика", "невыкуп",
        "отмена заказа", "брак"
    ],
    "storage": [
        "хранение", "размещение", "платное хранение", "складское хранение"
    ],
    "payouts": [
        "выплата", "выплаты", "расчеты", "расчёты", "взаиморасчеты",
        "взаиморасчёты", "платеж", "платёж", "акт", "закрывающие документы"
    ],
    "penalties": [
        "штраф", "штрафы", "удержание", "удержания", "санкции",
        "блокировка", "ограничение продаж"
    ],
    "api": [
        "api", "апи", "личный кабинет", "кабинет продавца",
        "метод api", "обновление api"
    ],
    "marking": [
        "маркировка", "честный знак", "разрешительный режим",
        "киз", "код маркировки"
    ],
    "regulator": [
        "фас", "роспотребнадзор", "минпромторг", "минцифры",
        "закон", "платформенная экономика", "регулятор"
    ],
}

MARKETPLACE_RULES = {
    "ozon": ["ozon", "озон"],
    "wildberries": ["wildberries", "вайлдберриз", "wb", "вб"],
    "yandex_market": ["яндекс маркет", "яндекс.маркета", "яндекс маркета", "yandex market"],
}

NOISE_WORDS = [
    "конкурс", "розыгрыш", "мерч", "вебинар", "эфир", "подкаст",
    "обучение", "партнерский бонус", "партнёрский бонус",
    "акция", "промо", "распродажа"
]

STRONG_WORDS = [
    "измен", "вступит в силу", "вступает в силу", "с 1 ", "с 01.",
    "новые правила", "обновил", "обновила", "повыш", "сниж",
    "теперь", "начнет", "начнёт", "перестанет", "будет действовать",
    "фас", "штраф", "обязаны", "запрет", "ограничение"
]


def norm(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def table_columns(cur, table: str):
    return [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]


def pick_col(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def detect_marketplace(text: str) -> str:
    t = norm(text)
    found = []
    for mp, words in MARKETPLACE_RULES.items():
        if any(w in t for w in words):
            found.append(mp)
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return "multiple"
    return "unknown"


def detect_signal_types(text: str):
    t = norm(text)
    result = []
    for signal_type, words in SIGNAL_RULES.items():
        if any(w in t for w in words):
            result.append(signal_type)
    return result


def score_signal(text: str, signal_types):
    t = norm(text)
    score = 0
    score += len(signal_types) * 2

    for w in STRONG_WORDS:
        if w in t:
            score += 2

    if "оферта" in t or "комисси" in t or "тариф" in t:
        score += 3

    if any(w in t for w in NOISE_WORDS):
        score -= 2

    if score >= 9:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def ensure_tables(cur):
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

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tariff_signals_status
    ON tariff_signals(status)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tariff_signals_detected_at
    ON tariff_signals(detected_at)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tariff_signals_marketplace
    ON tariff_signals(marketplace)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tariff_signals_type
    ON tariff_signals(signal_type)
    """)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ensure_tables(cur)

    columns = table_columns(cur, "news")

    id_col = pick_col(columns, ["id"])
    title_col = pick_col(columns, ["title"])
    raw_col = pick_col(columns, ["raw_text", "full_text_raw", "content", "text", "clean_text"])
    source_col = pick_col(columns, ["source"])
    link_col = pick_col(columns, ["link", "url", "source_url"])
    published_col = pick_col(columns, ["published_at", "created_at", "collected_at", "date"])

    if not id_col or not title_col:
        raise SystemExit(f"Required columns not found. news columns: {columns}")

    select_cols = [id_col, title_col]
    for c in [raw_col, source_col, link_col, published_col]:
        if c and c not in select_cols:
            select_cols.append(c)

    sql = f"""
    SELECT {", ".join(select_cols)}
    FROM news
    ORDER BY {id_col} DESC
    LIMIT 700
    """

    rows = cur.execute(sql).fetchall()

    inserted = 0
    checked = 0

    for row in rows:
        checked += 1

        news_id = row[id_col]
        title = row[title_col] or ""
        raw_text = row[raw_col] if raw_col else ""
        source = row[source_col] if source_col else ""
        link = row[link_col] if link_col else ""
        published_at = row[published_col] if published_col else ""

        full = f"{title}\n{raw_text}\n{source}\n{link}"

        signal_types = detect_signal_types(full)
        if not signal_types:
            continue

        marketplace = detect_marketplace(full)
        level = score_signal(full, signal_types)

        if level == "low" and not any(s in signal_types for s in ["tariff", "offer", "regulator"]):
            continue

        for signal_type in signal_types:
            reason = f"matched signal_type={signal_type}; level={level}"

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
                news_id,
                source,
                marketplace,
                signal_type,
                level,
                title[:500],
                link,
                published_at,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                reason
            ))

            if cur.rowcount:
                inserted += 1

    conn.commit()

    print("signal_monitor done")
    print("checked news:", checked)
    print("inserted signals:", inserted)

    print()
    print("latest signals:")
    for r in cur.execute("""
        SELECT id, news_id, marketplace, signal_type, signal_level, source, substr(title, 1, 120) AS title
        FROM tariff_signals
        ORDER BY id DESC
        LIMIT 20
    """):
        print(dict(r))

    conn.close()


if __name__ == "__main__":
    main()
