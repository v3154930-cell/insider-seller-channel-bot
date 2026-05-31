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


def detect_direct_seller_action(title: str, text: str) -> list[str]:
    t = f"{title or ''} {text or ''}".lower()
    actions: list[str] = []
    if any(x in t for x in ["комисс", "тариф", "стоимост", "логист", "хранен"]):
        actions.append("пересчитать юнит-экономику и проверить маржинальность по SKU")
    if any(x in t for x in ["дедлайн", "до ", "срок", "обязател"]):
        actions.append("зафиксировать дедлайн и обновить операционный календарь")
    if any(x in t for x in ["честный знак", "маркиров", "сертифик", "ндс", "усн", "фнс"]):
        actions.append("проверить комплаенс-документы и регуляторные требования")
    return list(dict.fromkeys(actions))


def detect_low_value_background(topics: list[str], text: str) -> bool:
    t = (text or "").lower()
    if "corporate_pr" in topics and not any(k in t for k in ["выплат", "тариф", "дедлайн", "блокиров", "штраф"]):
        return True
    if "low_value_background" in topics and len(topics) <= 2:
        return True
    return False


def score_seller_actionability(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> dict:
    topics = classify_seller_topic(title, text, source, marketplace)
    actions = detect_direct_seller_action(title, text)
    low_background = detect_low_value_background(topics, text)

    relevance = min(5, len(topics) + (1 if "analytics_market" in topics else 0))
    actionability = min(5, len(actions) * 2)
    if low_background:
        relevance = min(relevance, 2)
        actionability = min(actionability, 1)

    return {
        "topics": topics,
        "direct_actions": actions,
        "no_direct_action": not actions,
        "seller_relevance_score": relevance,
        "actionability_score": actionability,
        "is_low_value": low_background,
    }


def determine_importance(scored: dict) -> tuple[str, str]:
    topics = set(scored.get("topics", []))
    actions = scored.get("direct_actions", [])

    if not actions:
        if "corporate_pr" in topics or "low_value_background" in topics:
            return "🔵", "corporate_or_background_without_direct_action"
        if "marketplace_banking_fintech" in topics or "finance_payments" in topics:
            return "🟡", "potential_finance_impact_but_no_direct_action"
        return "🟡", "useful_context_no_direct_action"

    if topics & HIGH_TOPICS:
        return "🔴", "direct_seller_action_required"
    if "marketplace_banking_fintech" in topics or "finance_payments" in topics:
        return "🟡", "finance_operational_action"
    return "🟡", "action_exists_but_not_critical"
