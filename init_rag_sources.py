import sqlite3
from pathlib import Path

DB_PATH = Path("data/rag_store.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS rag_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    marketplace TEXT,
    rag_layer TEXT NOT NULL,
    trust_level TEXT NOT NULL DEFAULT 'medium',
    url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

sources = [
    (
        "Ozon official commissions and tariffs",
        "official",
        "ozon",
        "tariff_official",
        "high",
        "https://docs.ozon.ru/global/ru/commissions/",
        "Официальный раздел Ozon по комиссиям, тарифам и услугам."
    ),
    (
        "Ozon seller docs",
        "official",
        "ozon",
        "legal_official",
        "high",
        "https://docs.ozon.ru/",
        "Официальная документация Ozon для продавцов."
    ),
    (
        "Wildberries tariffs API docs",
        "official",
        "wildberries",
        "tariff_official",
        "high",
        "https://dev.wildberries.ru/openapi/analytics#tag/Tarify",
        "Официальная документация WB API по тарифам."
    ),
    (
        "Wildberries seller offer",
        "official",
        "wildberries",
        "legal_official",
        "high",
        "https://seller.wildberries.ru/terms",
        "Официальные условия и оферта WB для продавцов."
    ),
    (
        "Yandex Market rates",
        "official",
        "yandex_market",
        "tariff_official",
        "high",
        "https://yandex.ru/support/marketplace/ru/introduction/rates/",
        "Официальная справка Яндекс Маркета по тарифам и взаиморасчётам."
    ),
    (
        "Yandex Market seller docs",
        "official",
        "yandex_market",
        "legal_official",
        "high",
        "https://yandex.ru/support/marketplace/",
        "Официальная справка Яндекс Маркета для продавцов."
    ),
    (
        "Oborot.ru",
        "media",
        "multiple",
        "news_signal",
        "medium",
        "https://oborot.ru/",
        "Новостной и аналитический источник. Использовать как сигнал, не как официальный источник."
    ),
    (
        "TG marketplace_biz",
        "telegram",
        "multiple",
        "news_signal",
        "medium",
        None,
        "Telegram-источник. Использовать как новостной сигнал."
    ),
    (
        "TG mpgo_ru",
        "telegram",
        "multiple",
        "news_signal",
        "medium",
        None,
        "Telegram-источник. Использовать как новостной сигнал."
    ),
    (
        "TG crmmarketplace",
        "telegram",
        "multiple",
        "news_signal",
        "medium",
        None,
        "Telegram-источник. Использовать как новостной сигнал."
    )
]

for item in sources:
    name, source_type, marketplace, rag_layer, trust_level, url, notes = item

    cur.execute("""
    SELECT id FROM rag_sources
    WHERE name = ?
      AND COALESCE(url, '') = COALESCE(?, '')
    """, (name, url))

    exists = cur.fetchone()

    if exists:
        cur.execute("""
        UPDATE rag_sources
        SET source_type = ?,
            marketplace = ?,
            rag_layer = ?,
            trust_level = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (source_type, marketplace, rag_layer, trust_level, notes, exists[0]))
    else:
        cur.execute("""
        INSERT INTO rag_sources (
            name, source_type, marketplace, rag_layer, trust_level, url, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, source_type, marketplace, rag_layer, trust_level, url, notes))

conn.commit()

print("rag_sources ready")
print("total sources:", cur.execute("SELECT COUNT(*) FROM rag_sources").fetchone()[0])

for row in cur.execute("""
SELECT id, source_type, marketplace, rag_layer, trust_level, enabled, name
FROM rag_sources
ORDER BY source_type, marketplace, rag_layer, id
"""):
    print(row)

conn.close()
