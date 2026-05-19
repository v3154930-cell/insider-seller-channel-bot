#!/usr/bin/env python3
import os
import re
import sqlite3
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("rag_archive_v1")

NEWS_DB = os.getenv("NEWSBOT_DB_PATH", "/opt/newsbot_v2/news_queue.db")
RAG_DB = os.getenv("RAG_STORE_DB_PATH", "/opt/newsbot_v2/data/rag_store.db")


PUBLISH_KEYWORDS = [
    "оферта", "договор", "регламент", "условия",
    "тариф", "тарифы", "комиссия", "комиссии",
    "логистика", "хранение", "размещение",
    "возврат", "возвраты", "штраф", "штрафы",
    "удержание", "удержания", "выплаты", "сроки выплат",
    "маркировка", "честный знак", "сертификат", "сертификаты",
    "блокировка", "блокировки", "модерация",
    "фас", "фнс", "роспотребнадзор", "минпромторг",
    "закон", "законопроект", "платформенная экономика",
    "суд", "арбитраж", "претензия", "досудебная",
]

DROP_KEYWORDS = [
    "поздравляем", "поздравление", "праздник",
    "вебинар", "эфир", "мероприятие",
    "открытие пвз", "открылся пвз", "новый пвз",
    "история успеха", "интервью",
    "подборка товаров", "товары для покупателей",
]

MARKETPLACE_PATTERNS = [
    ("ozon", ["ozon", "озон"]),
    ("wildberries", ["wildberries", "wb", "вайлдберриз", "вб"]),
    ("yandex_market", ["яндекс маркет", "yandex market", "маркет яндекс"]),
]

TOPIC_PATTERNS = [
    ("offer", ["оферта", "договор", "регламент", "условия"]),
    ("tariff", ["тариф", "тарифы", "комиссия", "комиссии", "стоимость услуг"]),
    ("logistics", ["логистика", "доставка", "склад", "фбо", "fbo", "фбс", "fbs", "dbs"]),
    ("storage", ["хранение", "размещение"]),
    ("returns", ["возврат", "возвраты"]),
    ("payouts", ["выплаты", "сроки выплат", "удержание", "удержания"]),
    ("penalties", ["штраф", "штрафы", "санкции"]),
    ("marking", ["маркировка", "честный знак", "сертификат", "сертификаты"]),
    ("blocking", ["блокировка", "блокировки", "модерация"]),
    ("regulator", ["фас", "фнс", "роспотребнадзор", "минпромторг", "закон", "законопроект"]),
    ("court_case", ["суд", "арбитраж", "иск", "претензия", "досудебная"]),
]


def norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def short_title(title: str, limit: int = 120) -> str:
    t = clean_text(title).replace("...", "…")
    if "…" in t:
        before = t.split("…", 1)[0].strip()
        if len(before) >= 25:
            t = before

    markers = [
        " Мне часто ", " За выходные ", " В этом кейсе ",
        " Ранее ", " Также ", " При этом ", " Сейчас ",
        " Модель ", " Схема ", " Компания ", " Эксперты ",
        " Помогает ", " Товары размещаются ",
    ]
    for marker in markers:
        pos = t.find(marker)
        if pos >= 30:
            t = t[:pos].strip(" -—:;,.")
            break

    if len(t) > limit:
        cut = t[:limit].rstrip()
        last_space = cut.rfind(" ")
        if last_space > 60:
            cut = cut[:last_space]
        t = cut.rstrip(" -—:;,.") + "…"

    return t or "Без заголовка"


def detect_source_type(source: str, link: str) -> str:
    s = norm(source)
    l = norm(link)

    if s.startswith("official:"):
        return "official_marketplace"

    if any(x in s for x in ["фас", "фнс", "роспотребнадзор", "минпромторг"]):
        return "regulator"

    if any(x in l for x in ["fas.gov", "nalog.gov", "rospotrebnadzor", "minpromtorg", "duma.gov"]):
        return "regulator"

    if any(x in l for x in ["seller.ozon", "seller.wildberries", "wildberries.ru/seller", "partner.market.yandex", "yandex.ru/legal"]):
        return "official_marketplace"

    if s.startswith("tg:"):
        return "tg"

    return "media"


def detect_marketplace(text: str) -> str:
    t = norm(text)
    found = []
    for code, words in MARKETPLACE_PATTERNS:
        if any(w in t for w in words):
            found.append(code)
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return "multiple"
    return "unknown"


def detect_topic(text: str) -> str:
    t = norm(text)
    for topic, words in TOPIC_PATTERNS:
        if any(w in t for w in words):
            return topic
    return "general"


def detect_document_type(source_type: str, topic: str, text: str) -> str:
    t = norm(text)

    if source_type == "regulator":
        return "regulator_news"

    if topic == "offer":
        return "offer_change"
    if topic == "tariff":
        return "tariff_change"
    if topic in ("logistics", "storage", "returns", "payouts", "penalties"):
        return "operational_change"
    if topic in ("court_case",):
        return "case"
    if source_type == "official_marketplace":
        return "official_news"

    if "суд" in t or "арбитраж" in t or "претенз" in t:
        return "case"

    return "news_analysis"


def detect_impact_level(source_type: str, topic: str, text: str) -> str:
    t = norm(text)

    critical_words = [
        "изменится с", "вступает в силу", "с 1 ", "с 15 ", "с 30 ",
        "обязатель", "штраф", "блокиров", "удержан", "оферта", "договор",
    ]

    high_topics = {"offer", "tariff", "logistics", "storage", "returns", "payouts", "penalties", "marking", "blocking", "regulator"}

    if any(w in t for w in critical_words):
        return "critical"

    if source_type in ("official_marketplace", "regulator") and topic in high_topics:
        return "high"

    if topic in high_topics:
        return "medium"

    return "low"


def is_rag_eligible(row: Dict[str, Any]) -> Tuple[bool, str]:
    source = row.get("source") or ""
    link = row.get("link") or ""
    title = row.get("title") or ""
    raw_text = row.get("raw_text") or ""
    seller_decision = row.get("seller_decision") or ""

    text = " ".join([title, raw_text, source, link])
    t = norm(text)

    if len(clean_text(raw_text)) < 80:
        return False, "too_short"

    if any(w in t for w in DROP_KEYWORDS) and not any(w in t for w in PUBLISH_KEYWORDS):
        return False, "drop_noise"

    source_type = detect_source_type(source, link)

    if source_type in ("official_marketplace", "regulator"):
        if any(w in t for w in PUBLISH_KEYWORDS):
            return True, "official_or_regulator_important"
        return False, "official_but_no_seller_impact"

    if any(w in t for w in PUBLISH_KEYWORDS):
        return True, "seller_legal_tariff_operational_value"

    if seller_decision == "publish" and any(w in t for w in ["селлер", "маркетплейс", "ozon", "wildberries", "яндекс"]):
        return True, "published_seller_case"

    return False, "no_rag_value"


def content_hash(title: str, text: str, link: str) -> str:
    base = "|".join([str(title or ""), str(text or ""), str(link or "")])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def make_markdown(row: Dict[str, Any], meta: Dict[str, str]) -> str:
    title = short_title(row.get("title") or "")
    source = row.get("source") or ""
    link = row.get("link") or ""
    raw = clean_text(row.get("raw_text") or "")
    created_at = row.get("created_at") or ""

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Источник:** {source}")
    lines.append(f"**Тип источника:** {meta.get('source_type')}")
    lines.append(f"**Маркетплейс:** {meta.get('marketplace')}")
    lines.append(f"**Тип документа:** {meta.get('document_type')}")
    lines.append(f"**Тема:** {meta.get('topic')}")
    lines.append(f"**Влияние:** {meta.get('impact_level')}")
    lines.append(f"**Дата в очереди:** {created_at}")
    if link:
        lines.append(f"**Ссылка:** {link}")
    lines.append("")
    lines.append("## Кратко")
    lines.append("")
    lines.append(title)
    lines.append("")
    lines.append("## Полный текст")
    lines.append("")
    lines.append(raw)
    lines.append("")
    lines.append("## Для будущего разбора")
    lines.append("")
    lines.append("- определить, влияет ли материал на деньги, обязанности или риски селлера;")
    lines.append("- проверить дату вступления изменений в силу;")
    lines.append("- связать с офертой, тарифами, регламентом или нормами закона;")
    lines.append("- при необходимости подготовить вывод для Seller Helper / Docobrazec.")
    return "\n".join(lines).strip()


def init_rag_db():
    os.makedirs(os.path.dirname(RAG_DB), exist_ok=True)

    conn = sqlite3.connect(RAG_DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_news_id INTEGER,
            title TEXT,
            clean_text TEXT,
            markdown_text TEXT,
            source TEXT,
            source_type TEXT,
            marketplace TEXT,
            document_type TEXT,
            topic TEXT,
            impact_level TEXT,
            published_at TEXT,
            effective_date TEXT,
            link TEXT,
            content_hash TEXT UNIQUE,
            rag_eligible INTEGER DEFAULT 1,
            eligibility_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_source_news_id ON rag_documents(source_news_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_source_type ON rag_documents(source_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_marketplace ON rag_documents(marketplace)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_topic ON rag_documents(topic)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_document_type ON rag_documents(document_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_impact ON rag_documents(impact_level)")

    try:
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS rag_documents_fts
            USING fts5(title, clean_text, markdown_text, content='rag_documents', content_rowid='id')
        """)
        logger.info("FTS5 table ready")
    except Exception as e:
        logger.warning("FTS5 is not available or failed to init: %s", e)

    conn.commit()
    conn.close()


def fetch_news_rows(limit: int = 500) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(NEWS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            title,
            raw_text,
            processed_text,
            link,
            source,
            seller_decision,
            is_published,
            in_digest,
            created_at
        FROM news
        WHERE raw_text IS NOT NULL
          AND length(raw_text) >= 80
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def upsert_rag_document(row: Dict[str, Any]) -> bool:
    eligible, reason = is_rag_eligible(row)
    if not eligible:
        return False

    title = short_title(row.get("title") or "")
    raw = clean_text(row.get("raw_text") or "")
    link = row.get("link") or ""
    source = row.get("source") or ""
    all_text = " ".join([title, raw, source, link])

    source_type = detect_source_type(source, link)
    marketplace = detect_marketplace(all_text)
    topic = detect_topic(all_text)
    document_type = detect_document_type(source_type, topic, all_text)
    impact_level = detect_impact_level(source_type, topic, all_text)

    meta = {
        "source_type": source_type,
        "marketplace": marketplace,
        "topic": topic,
        "document_type": document_type,
        "impact_level": impact_level,
    }

    markdown = make_markdown(row, meta)
    h = content_hash(title, raw, link)

    conn = sqlite3.connect(RAG_DB)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO rag_documents (
            source_news_id,
            title,
            clean_text,
            markdown_text,
            source,
            source_type,
            marketplace,
            document_type,
            topic,
            impact_level,
            published_at,
            effective_date,
            link,
            content_hash,
            rag_eligible,
            eligibility_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 1, ?)
    """, (
        row.get("id"),
        title,
        raw,
        markdown,
        source,
        source_type,
        marketplace,
        document_type,
        topic,
        impact_level,
        row.get("created_at"),
        link,
        h,
        reason,
    ))

    inserted = cur.rowcount > 0

    if inserted:
        doc_id = cur.lastrowid
        try:
            cur.execute("""
                INSERT INTO rag_documents_fts(rowid, title, clean_text, markdown_text)
                VALUES (?, ?, ?, ?)
            """, (doc_id, title, raw, markdown))
        except Exception as e:
            logger.warning("FTS insert failed for doc_id=%s: %s", doc_id, e)

    conn.commit()
    conn.close()
    return inserted


def archive(limit: int = 500):
    init_rag_db()
    rows = fetch_news_rows(limit=limit)

    inserted = 0
    skipped = 0

    for row in rows:
        if upsert_rag_document(row):
            inserted += 1
        else:
            skipped += 1

    logger.info("RAG archive finished. scanned=%s inserted=%s skipped=%s", len(rows), inserted, skipped)


def stats():
    init_rag_db()
    conn = sqlite3.connect(RAG_DB)
    cur = conn.cursor()

    print("=== rag_documents total ===")
    cur.execute("SELECT COUNT(*) FROM rag_documents")
    print(cur.fetchone()[0])

    print("\n=== by source_type ===")
    for row in cur.execute("SELECT source_type, COUNT(*) FROM rag_documents GROUP BY source_type ORDER BY COUNT(*) DESC"):
        print(row)

    print("\n=== by topic ===")
    for row in cur.execute("SELECT topic, COUNT(*) FROM rag_documents GROUP BY topic ORDER BY COUNT(*) DESC"):
        print(row)

    print("\n=== latest ===")
    for row in cur.execute("""
        SELECT id, source, source_type, marketplace, topic, impact_level, substr(title,1,90)
        FROM rag_documents
        ORDER BY id DESC
        LIMIT 10
    """):
        print(row)

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archive valuable NEWSBOT items into persistent RAG store.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        stats()
    else:
        archive(limit=args.limit)
