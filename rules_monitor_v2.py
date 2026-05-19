import re
from db import init_db, _fetch_all, _execute

RULE_KEYWORDS = {
    "offer_terms": [
        "оферт", "услови", "регламент", "правила", "договор",
    ],
    "tariffs_fees": [
        "тариф", "комисс", "платн", "стоимость", "удорож", "платный инструмент",
    ],
    "payments": [
        "выплат", "деньги", "расчет", "расчёт", "задерж", "удержан",
    ],
    "penalties_returns": [
        "штраф", "возврат", "компенсац", "провер", "брак", "претензи",
    ],
    "logistics_storage": [
        "логистик", "хранен", "хранение", "приёмк", "приемк", "склад", "fbo", "fbs",
    ],
    "documents_compliance": [
        "сертификац", "маркиров", "документ", "товарный знак", "оригинал",
    ],
    "law_regulator": [
        "фас", "закон", "минфин", "регулирован", "платформенной экономике", "вступит в силу",
    ],
}

MARKETPLACE_PATTERNS = {
    "ozon": [
        r"\bozon\b", r"\bозон\b",
    ],
    "wildberries": [
        r"\bwildberries\b", r"\bwb\b", r"\bвайлдберриз\b", r"\bwildberries\b",
    ],
    "yandex_market": [
        r"\bяндекс маркет\b", r"\byandex market\b", r"\bяндекс\.маркет\b",
    ],
}

DOMAIN_WORDS = [
    "маркетплейс",
    "маркетплейсы",
    "селлер",
    "селлерам",
    "селлера",
    "продавец",
    "продавцам",
    "продавцов",
    "пвз",
    "fbo",
    "fbs",
    "карточк",
    "личный кабинет",
    "кабинет продавца",
    "витрина магазина",
]

TRASH_WORDS = [
    "гриб",
    "автоваз",
    "lada",
    "openai",
    "илон маск",
    "смартфон",
    "поезд",
    "путешествия",
    "грузовик",
    "академик ран",
    "цифровой формуляр",
]


def contains_any(text: str, words):
    t = text.lower()
    return any(w in t for w in words)


def has_marketplace_context(text: str) -> bool:
    t = text.lower()

    if contains_any(t, DOMAIN_WORDS):
        return True

    for patterns in MARKETPLACE_PATTERNS.values():
        for p in patterns:
            if re.search(p, t, flags=re.IGNORECASE):
                return True

    return False


def is_trash(text: str) -> bool:
    t = text.lower()
    return contains_any(t, TRASH_WORDS) and not has_marketplace_context(t)

def is_real_rules_signal(text: str) -> bool:
    t = text.lower()

    strong_phrases = [
        "оферт",
        "услови",
        "регламент",
        "новые правила",
        "обновил правила",
        "обновила правила",
        "изменил правила",
        "изменили правила",
        "вступит в силу",
        "вступает в силу",
        "с 1 ",
        "с 01.",
        "тариф",
        "комисс",
        "выплат",
        "сроки выплат",
        "удержан",
        "штраф",
        "возврат",
        "компенсац",
        "фас",
        "предупреждение маркетплейсам",
        "навязывание невыгодных условий",
        "потребовала устранить",
        "платный инструмент",
        "платная услуга",
        "сертификац",
        "маркиров",
        "товарный знак",
        "бейдж",
        "оригинал",
    ]

    weak_news_only = [
        "субсидии",
        "субсидию",
        "компенсируют",
        "цены на маркетплейсах вырастут",
        "пошла подготовка",
        "лотерею",
        "вабанга",
        "конкурс среди пунктов выдачи",
        "пвз что надо",
    ]

    if any(w in t for w in weak_news_only) and not any(s in t for s in strong_phrases):
        return False

    return any(s in t for s in strong_phrases)


def detect_marketplace(text: str) -> str:
    t = text.lower()
    found = []

    for marketplace, patterns in MARKETPLACE_PATTERNS.items():
        for p in patterns:
            if re.search(p, t, flags=re.IGNORECASE):
                found.append(marketplace)
                break

    found = sorted(set(found))

    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return "multiple"

    return "unknown"


def detect_signal_type(text: str):
    t = text.lower()
    matched_types = []

    for signal_type, keywords in RULE_KEYWORDS.items():
        if any(k in t for k in keywords):
            matched_types.append(signal_type)

    if not matched_types:
        return None, 0, ""

    confidence = min(100, 30 + len(matched_types) * 12)

    strong_words = [
        "измен", "новые правила", "обновил", "обновила", "вступит в силу",
        "с 1 ", "с 01.", "фас", "предупреждение", "потребовала",
        "тариф", "комиссия", "выплат", "штраф", "удержан",
        "оферта", "регламент", "условия"
    ]

    strong_hits = [w for w in strong_words if w in t]
    confidence = min(100, confidence + len(strong_hits) * 10)

    return matched_types[0], confidence, ", ".join(matched_types)


def main():
    init_db()

    rows = _fetch_all("""
        SELECT id, title, raw_text, source, link, created_at
        FROM news
        WHERE created_at >= datetime('now', '-7 days')
        ORDER BY id DESC
        LIMIT 500
    """)

    checked = 0
    inserted = 0
    skipped_no_context = 0
    skipped_trash = 0

    for r in rows:
        news_id = r[0]
        title = r[1] or ""
        raw_text = r[2] or ""
        source = r[3] or ""
        link = r[4] or ""

        text = f"{title} {raw_text}"

        if is_trash(text):
            skipped_trash += 1
            continue

        if not has_marketplace_context(text):
            skipped_no_context += 1
            continue

        if not is_real_rules_signal(text):
            continue

        signal_type, confidence, reason = detect_signal_type(text)

        if not signal_type:
            continue

        checked += 1
        marketplace = detect_marketplace(text)

        try:
            _execute("""
                INSERT OR IGNORE INTO rules_signals
                (news_id, marketplace, signal_type, confidence, title, source, link, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                news_id,
                marketplace,
                signal_type,
                confidence,
                title,
                source,
                link,
                reason,
            ))
            inserted += 1
        except Exception as e:
            print("insert failed:", news_id, repr(e))

    print("Rules monitor finished")
    print("rule-like checked:", checked)
    print("inserted or ignored:", inserted)
    print("skipped_no_context:", skipped_no_context)
    print("skipped_trash:", skipped_trash)

    print("\n=== SUMMARY BY MARKETPLACE ===")
    rows = _fetch_all("""
        SELECT marketplace, COUNT(*)
        FROM rules_signals
        GROUP BY marketplace
        ORDER BY COUNT(*) DESC
    """)
    for r in rows:
        print(r)

    print("\n=== SUMMARY BY TYPE ===")
    rows = _fetch_all("""
        SELECT signal_type, COUNT(*)
        FROM rules_signals
        GROUP BY signal_type
        ORDER BY COUNT(*) DESC
    """)
    for r in rows:
        print(r)

    print("\n=== LAST RULE SIGNALS ===")
    rows = _fetch_all("""
        SELECT id, news_id, marketplace, signal_type, confidence, title, source
        FROM rules_signals
        ORDER BY id DESC
        LIMIT 20
    """)

    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
