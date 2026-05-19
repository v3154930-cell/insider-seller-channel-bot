import re
from db import init_db, _fetch_all, _execute

STOPWORDS = {
    "и", "в", "во", "на", "по", "для", "за", "из", "от", "до", "с", "со",
    "что", "как", "это", "или", "у", "о", "об", "при", "если", "же", "не",
    "новости", "площадок", "маркетплейс", "маркетплейсы", "селлер", "селлерам",
    "продавец", "продавцам", "товар", "товары"
}

IMPORTANT_WORDS = {
    "тариф", "тарифы", "комиссия", "комиссии", "выплаты", "выплат",
    "возврат", "возвраты", "компенсация", "компенсации", "штраф", "штрафы",
    "платный", "платная", "инструмент", "витрина", "документы", "документ",
    "платёжных", "платежных", "бренд", "товарный", "знак", "оригинал",
    "бейдж", "проверки", "проверка", "условия", "оферта", "регламент",
    "фас", "минфин", "закон", "маркировка", "сертификация"
}

def words(text):
    text = (text or "").lower()
    raw = re.findall(r"[а-яa-z0-9ё]+", text)
    return [w for w in raw if len(w) >= 4 and w not in STOPWORDS]

def score_match(signal_text, doc_text):
    sw = set(words(signal_text))
    dw = set(words(doc_text))

    if not sw or not dw:
        return 0

    common = sw & dw
    score = len(common) * 10

    important_common = common & IMPORTANT_WORDS
    score += len(important_common) * 20

    return min(score, 100)

def marketplace_matches(signal_marketplace, doc_marketplace):
    if signal_marketplace in (None, "", "unknown", "multiple"):
        return True
    return signal_marketplace == doc_marketplace

def main():
    init_db()

    signals = _fetch_all("""
        SELECT id, news_id, marketplace, signal_level, signal_type, confidence, title, source, link
        FROM rules_signals
        WHERE is_digest_candidate = 1
        ORDER BY confidence DESC, id DESC
    """)

    docs = _fetch_all("""
        SELECT id, marketplace, document_name, section, topic, rule_text, effective_date, source_url
        FROM rules_documents
    """)

    processed = 0
    confirmed = 0
    signal_only = 0

    for s in signals:
        signal_id, news_id, marketplace, signal_level, signal_type, confidence, title, source, link = s
        signal_text = f"{title or ''} {signal_type or ''} {signal_level or ''}"

        best = None
        best_score = 0

        for d in docs:
            doc_id, doc_marketplace, document_name, section, topic, rule_text, effective_date, source_url = d

            if not marketplace_matches(marketplace, doc_marketplace):
                continue

            doc_text = f"{document_name or ''} {section or ''} {topic or ''} {rule_text or ''}"
            score = score_match(signal_text, doc_text)

            if score > best_score:
                best_score = score
                best = d

        processed += 1

        if best and best_score >= 60:
            doc_id, doc_marketplace, document_name, section, topic, rule_text, effective_date, source_url = best
            confirmation_level = "confirmed_by_docs"
            check_status = "auto_checked"
            can_publish = 1
            matched_document = f"{document_name} / {section} / {topic}"
            confirmed += 1
        else:
            doc_id = None
            effective_date = None
            confirmation_level = "signal_only"
            check_status = "auto_checked"
            can_publish = 0
            matched_document = None
            signal_only += 1

        _execute("""
            INSERT OR REPLACE INTO rules_checks
            (
                signal_id, news_id, marketplace, check_status, confirmation_level,
                matched_document_id, matched_document, match_score, effective_date,
                can_publish, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            signal_id,
            news_id,
            marketplace,
            check_status,
            confirmation_level,
            doc_id,
            matched_document,
            best_score,
            effective_date,
            can_publish,
        ))

    print("Auto check finished")
    print("signals processed:", processed)
    print("confirmed_by_docs:", confirmed)
    print("signal_only:", signal_only)

    print("\n=== CHECK RESULTS ===")
    rows = _fetch_all("""
        SELECT rc.id, rc.signal_id, rc.marketplace, rc.confirmation_level, rc.match_score,
               rc.matched_document, rc.effective_date, rs.title
        FROM rules_checks rc
        JOIN rules_signals rs ON rs.id = rc.signal_id
        ORDER BY rc.id DESC
        LIMIT 30
    """)

    for r in rows:
        print(r)

if __name__ == "__main__":
    main()
