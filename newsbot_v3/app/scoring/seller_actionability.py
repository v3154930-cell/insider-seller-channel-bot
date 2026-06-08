from __future__ import annotations

from .seller_taxonomy import classify_seller_topic


HIGH_TOPICS = {
    "commission_tariff",
    "logistics_storage",
    "returns_disputes",
    "documents_certification",
    "marking_chestny_znak",
    "legal_tax_regulatory",
    "platform_law",
    "api_cabinet",
}

DIRECT_SELLER_ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("пересчитать комиссии, тарифы и маржинальность по SKU", ("комисс", "тариф", "fee", "стоимост", "эквайринг")),
    ("проверить логистику, FBO/FBS/DBS/realFBS, склад, забор или возвраты", ("fbo", "fbs", "dbs", "realfbs", "real fbs", "склад", "пвз", "забор", "вывоз", "поставка", "логист", "хранен", "возврат")),
    ("обновить упаковку и снизить риск штрафов", ("упаков", "штраф", "пеня", "санкци", "удержан", "блокиров")),
    ("проверить маркировку, сертификаты и документы", ("честный знак", "маркиров", "сертифик", "декларац", "разрешитель", "документ", "комплаенс")),
    ("проверить оферту, договор, правила и юридические сроки", ("оферт", "договор", "контракт", "правил", "услови", "регламент", "обязател", "срок", "дедлайн", "измен")),
    ("проверить выплаты, платежи и условия расчетов", ("выплат", "платеж", "платёж", "расчет", "расчёт", "постоплат", "отсроч", "компенсац")),
    ("проверить отзывы, рейтинг и модерацию карточек", ("отзыв", "рейтинг", "карточк", "модерац", "контент")),
    ("обновить интеграции API, кабинет, отчеты или документы", ("api", "личный кабинет", "кабинет продавца", "отчет", "отчёт", "report", "акты", "эдо")),
)

ACTION_CONTEXT_TOKENS = (
    "продав", "селлер", "поставщик", "партнер", "партнёр", "для бизнеса", "личный кабинет",
    "кабинет продавца", "sku", "карточ", "маркетплейс", "wildberries", "wb", "ozon", "яндекс маркет",
)

OFFICIAL_SOURCE_TOKENS = (
    "official", "seller", "seller.ozon", "seller-edu", "wildberries", "wb", "ozon", "yandex", "яндекс маркет",
)

MACRO_CORPORATE_PATTERNS = (
    "инвестиц", "инвестир", "вложит", "вложени", "построит", "строительств", "логистический центр",
    "распределительный центр", "сортировочный центр", "складской комплекс", "партнерств", "партнёрств",
    "сотрудничеств", "соглашение", "меморандум", "республика", "область", "регион", "губернатор",
    "рейтинг", "data insight", "лидер", "лидируют", "топ-", "топ ", "исследован", "аналитик",
    "доля рынка", "m&a", "пакет акций", "акци", "выкуп", "купить долю", "не планирует покупать",
    "банк", "сбер", "греф", "слух", "ipo", "акционер", "ритейлер", "торговая сеть", "выручка",
)

FOREIGN_MARKETPLACE_PATTERNS = (
    "amazon", "alibaba", "temu", "shein", "ebay", "walmart", "korea", "коре", "европ", "eur", "сша", "китай",
)

RUSSIAN_SELLER_CONTEXT = (
    "российск", "росси", "рф", "wildberries", "wb", "ozon", "яндекс маркет", "avito", "авито", "честный знак", "фнс",
)

NEGATED_DIRECT_ACTION_PATTERNS = (
    "без новых комис", "без новой комис", "без изменения комис", "без новых тариф", "без изменения тариф",
    "без новых правил", "без изменения правил", "без прямых правил", "прямых правил нет",
    "без прямого влияния", "прямого влияния нет", "не содержит новых тариф", "не содержит новых правил",
    "нет новых тариф", "нет новых правил", "нет прямых",
)


DIRECT_IMPACT_TOKENS = (
    "штраф", "тариф", "комисс", "оферт", "договор", "контракт", "правил", "срок", "дедлайн", "обязател",
    "выплат", "компенсац", "маркиров", "сертифик", "api", "кабинет", "отчет", "отчёт", "возврат", "fbo", "fbs",
    "dbs", "поставк", "вывоз", "забор", "упаков", "ответствен", "удержан", "блокиров", "рейтинг", "модерац",
)


def _merge_text(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> str:
    return " ".join([title or "", text or "", source or "", marketplace or ""]).lower()


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _has_negated_direct_action(text: str) -> bool:
    if _has_any(text, NEGATED_DIRECT_ACTION_PATTERNS):
        return True
    if "нет" in text and _has_any(text, ("прямых правил", "прямых тариф", "прямого влияния", "прямой ответственности")):
        return True
    if "без" in text and _has_any(text, ("тариф", "комисс", "правил", "срок", "штраф")):
        return True
    return False


def is_direct_seller_action(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> bool:
    """Return True only when the item contains an operational seller action or risk."""
    merged = _merge_text(title, text, source, marketplace)
    if _has_negated_direct_action(merged):
        return False
    has_action = any(_has_any(merged, tokens) for _, tokens in DIRECT_SELLER_ACTION_PATTERNS)
    has_context = _has_any(merged, ACTION_CONTEXT_TOKENS)
    if has_action and has_context:
        return True
    if (source or marketplace) and has_action and _has_any(_merge_text("", "", source, marketplace), OFFICIAL_SOURCE_TOKENS):
        return True
    return False


def is_macro_corporate_noise(title: str, text: str, source: str | None = None) -> bool:
    """Detect background corporate/market-news items unless direct seller impact is explicit."""
    merged = _merge_text(title, text, source)
    if not _has_any(merged, MACRO_CORPORATE_PATTERNS):
        return False
    return not is_direct_seller_action(title, text, source=source)


def is_foreign_marketplace_noise(title: str, text: str, source: str | None = None) -> bool:
    """Detect foreign marketplace/retail news with no clear Russian seller action."""
    merged = _merge_text(title, text, source)
    if not _has_any(merged, FOREIGN_MARKETPLACE_PATTERNS):
        return False
    has_russian_context = _has_any(merged, RUSSIAN_SELLER_CONTEXT)
    return not (has_russian_context and is_direct_seller_action(title, text, source=source))


def seller_action_boost(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> float:
    """Deterministic score boost for standalone-worthy small-seller operations."""
    merged = _merge_text(title, text, source, marketplace)
    matched_groups = sum(1 for _, tokens in DIRECT_SELLER_ACTION_PATTERNS if _has_any(merged, tokens))
    if matched_groups == 0 or not is_direct_seller_action(title, text, source=source, marketplace=marketplace):
        return 0.0
    boost = 0.18 + min(0.24, 0.06 * matched_groups)
    if _has_any(_merge_text("", "", source, marketplace), OFFICIAL_SOURCE_TOKENS):
        boost += 0.06
    if _has_any(merged, ("штраф", "пен", "ответствен", "блокиров", "суд", "обязател")):
        boost += 0.06
    return min(0.42, boost)


def macro_noise_penalty(title: str, text: str, source: str | None = None) -> float:
    """Deterministic score penalty for digest-level macro/corporate background."""
    penalty = 0.0
    if is_macro_corporate_noise(title, text, source=source):
        penalty += 0.32
    if is_foreign_marketplace_noise(title, text, source=source):
        penalty += 0.28
    return min(0.5, penalty)


def detect_direct_seller_action(title: str, text: str) -> list[str]:
    merged = _merge_text(title, text)
    if _has_negated_direct_action(merged):
        return []
    actions = [action for action, tokens in DIRECT_SELLER_ACTION_PATTERNS if _has_any(merged, tokens)]
    return list(dict.fromkeys(actions))


def detect_low_value_background(topics: list[str], text: str) -> bool:
    t = (text or "").lower()
    if "corporate_pr" in topics and not any(k in t for k in DIRECT_IMPACT_TOKENS):
        return True
    if "analytics_market" in topics and not any(k in t for k in DIRECT_IMPACT_TOKENS):
        return True
    if "low_value_background" in topics and len(topics) <= 2:
        return True
    return False


def score_seller_actionability(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> dict:
    topics = classify_seller_topic(title, text, source, marketplace)
    actions = detect_direct_seller_action(title, text)
    direct_action = is_direct_seller_action(title, text, source=source, marketplace=marketplace)
    macro_noise = is_macro_corporate_noise(title, text, source=source)
    foreign_noise = is_foreign_marketplace_noise(title, text, source=source)
    low_background = detect_low_value_background(topics, text) or macro_noise or foreign_noise

    relevance = min(5, len(topics) + (1 if "analytics_market" in topics else 0))
    actionability = min(5, len(actions) * 2)

    if direct_action:
        relevance = max(relevance, 4)
        actionability = max(actionability, 3)
    if macro_noise or foreign_noise:
        relevance = min(relevance, 2)
        actionability = min(actionability, 1)
    elif low_background:
        relevance = min(relevance, 2)
        actionability = min(actionability, 1)

    base_score = 0.25 + relevance * 0.08 + actionability * 0.08
    ranking_score = max(0.05, min(0.98, base_score + seller_action_boost(title, text, source, marketplace) - macro_noise_penalty(title, text, source)))

    return {
        "topics": topics,
        "direct_actions": actions if direct_action else [],
        "no_direct_action": not direct_action,
        "seller_relevance_score": relevance,
        "actionability_score": actionability,
        "is_low_value": low_background,
        "is_macro_corporate_noise": macro_noise,
        "is_foreign_marketplace_noise": foreign_noise,
        "seller_action_boost": seller_action_boost(title, text, source, marketplace),
        "macro_noise_penalty": macro_noise_penalty(title, text, source),
        "ranking_score": ranking_score,
    }


def determine_importance(scored: dict) -> tuple[str, str]:
    topics = set(scored.get("topics", []))
    actions = scored.get("direct_actions", [])

    if not actions:
        if scored.get("is_macro_corporate_noise") or scored.get("is_foreign_marketplace_noise"):
            return "🔵", "macro_or_foreign_background_without_direct_seller_action"
        if "corporate_pr" in topics or "low_value_background" in topics or "analytics_market" in topics:
            return "🔵", "corporate_or_background_without_direct_action"
        if "marketplace_banking_fintech" in topics or "finance_payments" in topics:
            return "🟡", "potential_finance_impact_but_no_direct_action"
        return "🟡", "useful_context_no_direct_action"

    if topics & HIGH_TOPICS:
        return "🔴", "direct_seller_action_required"
    if "marketplace_banking_fintech" in topics or "finance_payments" in topics:
        return "🟡", "finance_operational_action"
    return "🟡", "action_exists_but_not_critical"
