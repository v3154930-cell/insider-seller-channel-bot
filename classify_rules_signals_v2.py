from db import init_db, _fetch_all, _execute

RULE_CHANGE_WORDS = [
    "оферт",
    "услови",
    "регламент",
    "новые правила",
    "правила заполнения",
    "изменил правила",
    "изменили правила",
    "тариф",
    "комисс",
    "платный инструмент",
    "платная услуга",
    "сроки выплат",
    "удержан",
    "штраф",
    "возврат",
    "компенсац",
    "не требует проверки",
    "товарный знак",
    "бейдж",
    "оригинал",
    "сертификац",
    "маркиров",
]

REGULATORY_WORDS = [
    "фас",
    "минфин",
    "закон",
    "платформенной экономике",
    "предупреждение маркетплейсам",
    "потребовала устранить",
    "вступит в силу",
    "вступает в силу",
]

BUSINESS_ONLY_WORDS = [
    "субсидии",
    "субсидию",
    "компенсируют",
    "лотерею",
    "вабанга",
    "конкурс",
    "пвз что надо",
    "пересобрал кабинет",
    "сводку",
    "цены на маркетплейсах вырастут",
    "пошла подготовка",
    "доходы владельцев пвз",
    "сократил выплаты владельцам пвз",
]


def has_any(text, words):
    t = text.lower()
    return any(w in t for w in words)


def classify(title, reason, signal_type, confidence):
    text = f"{title} {reason or ''} {signal_type or ''}".lower()

    if has_any(text, REGULATORY_WORDS):
        return "regulatory_signal", 1

    if has_any(text, RULE_CHANGE_WORDS):
        return "rule_change", 1

    if has_any(text, BUSINESS_ONLY_WORDS):
        return "business_signal", 0

    if confidence >= 85 and signal_type in ("offer_terms", "tariffs_fees", "payments", "penalties_returns"):
        return "rule_change", 1

    return "business_signal", 0


def main():
    init_db()

    rows = _fetch_all("""
        SELECT id, title, reason, signal_type, confidence
        FROM rules_signals
        ORDER BY id DESC
    """)

    counts = {}

    for r in rows:
        row_id = r[0]
        title = r[1] or ""
        reason = r[2] or ""
        signal_type = r[3] or ""
        confidence = r[4] or 0

        level, digest_candidate = classify(title, reason, signal_type, confidence)

        _execute("""
            UPDATE rules_signals
            SET signal_level = ?, is_digest_candidate = ?
            WHERE id = ?
        """, (level, digest_candidate, row_id))

        counts[level] = counts.get(level, 0) + 1

    print("classified:", counts)

    print("\n=== DIGEST CANDIDATES ===")
    rows = _fetch_all("""
        SELECT id, news_id, marketplace, signal_level, signal_type, confidence, title, source
        FROM rules_signals
        WHERE is_digest_candidate = 1
        ORDER BY confidence DESC, id DESC
        LIMIT 30
    """)

    for r in rows:
        print(r)

    print("\n=== BUSINESS ONLY ===")
    rows = _fetch_all("""
        SELECT id, news_id, marketplace, signal_level, signal_type, confidence, title, source
        FROM rules_signals
        WHERE is_digest_candidate = 0
        ORDER BY id DESC
        LIMIT 20
    """)

    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
