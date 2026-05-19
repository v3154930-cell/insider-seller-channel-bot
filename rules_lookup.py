#!/usr/bin/env python3
import argparse
import re
import sqlite3
import unicodedata
from pathlib import Path

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")

STOPWORDS = {
    "для", "или", "при", "что", "как", "это", "если", "надо", "нужно",
    "через", "после", "перед", "между", "когда", "где", "его", "её",
    "маркетплейс", "маркетплейса", "маркетплейсов", "селлер", "селлера",
    "продавец", "продавца", "товар", "товара", "товары",
}

def normalize(value: str) -> str:
    value = (value or "").lower().replace("ё", "е")
    # Убираем комбинируемые символы из OCR/PDF, например "Вайлдберриз".
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zа-я0-9%./\s-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def tokens(query: str):
    raw = normalize(query).split()
    out = []
    for w in raw:
        if len(w) < 3:
            continue
        if w in STOPWORDS:
            continue
        out.append(w)
    return out

def token_hit(token: str, hay: str) -> bool:
    if token in hay:
        return True
    if len(token) >= 6 and token[:6] in hay:
        return True
    if len(token) >= 5 and token[:5] in hay:
        return True
    return False

def has_marketplace_mismatch(row) -> bool:
    """
    Защита от перепутанных документов.

    Пример, найденный 04.05.2026:
    marketplace='ozon', document='Оферта товарная.pdf',
    но внутри rule_text встречается Вайлдберриз. Такой документ нельзя
    использовать как Ozon-подтверждение.
    """
    mp = normalize(row["marketplace"] or "")
    document_name = normalize(row["document_name"] or "")
    source_url = normalize(row["source_url"] or "")
    rule_text = normalize(row["rule_text"] or "")

    hay = " ".join([document_name, source_url, rule_text])

    wb_terms = ("wildberries", "вайлдберриз", "ваилдберриз", "wb ")
    ozon_terms = ("ozon", "озон")
    yandex_terms = ("yandex", "яндекс")

    has_wb = any(t in hay for t in wb_terms)
    has_ozon = any(t in hay for t in ozon_terms)
    has_yandex = any(t in hay for t in yandex_terms)

    if mp == "ozon" and has_wb:
        return True

    if mp == "wildberries" and (has_ozon or has_yandex) and not has_wb:
        return True

    if mp == "yandex_market" and (has_ozon or has_wb) and not has_yandex:
        return True

    return False


def classify_document(document_name: str, section: str, source_url: str) -> str:
    dn = normalize(document_name)
    sec = normalize(section)
    url = normalize(source_url)

    if "api" in dn and "комис" in dn:
        return "tariff_api_row"
    if ".xlsx" in dn or ".xlsx" in url:
        return "tariff_table_row"
    if "тариф" in dn or "rates" in dn or "commission" in url:
        return "tariff_or_fee"
    if "legal" in dn or "agreement" in url or "terms" in url or "оферт" in dn:
        return "legal_chunk"
    if "chunk" in sec:
        return "text_chunk"
    return "rule_row"

def score_row(row, query: str, q_tokens):
    rule_text = row["rule_text"] or ""
    hay = normalize(" ".join([
        row["marketplace"] or "",
        row["document_name"] or "",
        row["section"] or "",
        row["topic"] or "",
        rule_text,
        row["source_url"] or "",
    ]))

    q_norm = normalize(query)
    score = 0

    if q_norm and q_norm in hay:
        score += 120

    matched = 0
    for t in q_tokens:
        if token_hit(t, hay):
            matched += 1
            score += 20

    if q_tokens and matched == len(q_tokens):
        score += 80

    # rule_text важнее, чем грязный topic
    rt_norm = normalize(rule_text)
    rt_matches = sum(1 for t in q_tokens if token_hit(t, rt_norm))
    score += rt_matches * 15

    # Длинные осмысленные chunks лучше, чем мусорные строки
    l = len(rule_text)
    if l >= 120:
        score += 20
    if l < 40:
        score -= 40

    # Штраф за явно грязные topic
    topic = normalize(row["topic"] or "")
    if topic in {"", ".", "ble"} or len(topic) < 5:
        score -= 20
    if topic.startswith("http") or "legal/" in topic:
        score -= 10

    return score, matched

def latest_rows(conn, marketplace=None):
    where = ""
    params = []

    if marketplace and marketplace != "all":
        where = "WHERE marketplace = ?"
        params.append(marketplace)

    sql = f"""
    WITH ranked AS (
        SELECT
            id,
            marketplace,
            document_name,
            section,
            topic,
            rule_text,
            effective_date,
            source_url,
            content_hash,
            loaded_at,
            ROW_NUMBER() OVER (
                PARTITION BY marketplace, document_name, section
                ORDER BY loaded_at DESC, id DESC
            ) AS rn
        FROM rules_documents
        {where}
    )
    SELECT *
    FROM ranked
    WHERE rn = 1
    """
    return conn.execute(sql, params)

def search_rules(query: str, marketplace=None, limit=10, min_score=40):
    q_tokens = tokens(query)

    if not q_tokens:
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    results = []
    for row in latest_rows(conn, marketplace):
        if has_marketplace_mismatch(row):
            continue

        score, matched = score_row(row, query, q_tokens)
        if score < min_score:
            continue

        doc_kind = classify_document(row["document_name"], row["section"], row["source_url"])
        results.append({
            "score": score,
            "matched_tokens": matched,
            "id": row["id"],
            "marketplace": row["marketplace"],
            "document_name": row["document_name"],
            "section": row["section"],
            "topic": row["topic"],
            "effective_date": row["effective_date"],
            "loaded_at": row["loaded_at"],
            "source_url": row["source_url"],
            "doc_kind": doc_kind,
            "rule_text": row["rule_text"] or "",
        })

    conn.close()

    results.sort(key=lambda x: (-x["score"], x["marketplace"], x["document_name"], x["section"]))
    return results[:limit]

def excerpt(text: str, query: str, width=420):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= width:
        return text

    q_tokens = tokens(query)
    norm_text = normalize(text)

    pos = -1
    for t in q_tokens:
        p = norm_text.find(t)
        if p >= 0:
            pos = p
            break

    if pos < 0:
        return text[:width].rstrip() + "..."

    start = max(0, pos - 120)
    end = min(len(text), start + width)
    return ("..." if start > 0 else "") + text[start:end].rstrip() + ("..." if end < len(text) else "")

def print_results(query, rows):
    print("QUERY:", query)
    print("RESULTS:", len(rows))
    print("=" * 80)

    if not rows:
        print("NO MATCHES")
        return

    for i, r in enumerate(rows, 1):
        print(f"\n#{i} score={r['score']} matched={r['matched_tokens']} kind={r['doc_kind']}")
        print(f"id: {r['id']}")
        print(f"marketplace: {r['marketplace']}")
        print(f"document: {r['document_name']}")
        print(f"section: {r['section']}")
        print(f"topic: {r['topic']}")
        print(f"effective_date: {r['effective_date']}")
        print(f"loaded_at: {r['loaded_at']}")
        print(f"source_url: {r['source_url']}")
        print("text:")
        print(excerpt(r["rule_text"], query))
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="Read-only lookup over rules_documents.")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--marketplace", default="all", choices=["all", "ozon", "wildberries", "yandex_market"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-score", type=int, default=40)
    args = parser.parse_args()

    rows = search_rules(
        query=args.query,
        marketplace=args.marketplace,
        limit=args.limit,
        min_score=args.min_score,
    )
    print_results(args.query, rows)

if __name__ == "__main__":
    main()
