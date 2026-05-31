from __future__ import annotations

DIRECT_IMPACT_TOKENS = {
    "комисси", "тариф", "правил", "штраф", "блокир", "логист", "поставк", "api", "регуля", "закон", "оферт"
}
CONTEXT_TOKENS = {"рынок", "отчет", "аналит", "тренд", "исслед"}
LOW_VALUE_TOKENS = {"слух", "мнение", "общие слова", "фон", "обзор"}


def score_rules(text: str) -> dict:
    t = (text or "").lower()
    direct_hits = sum(1 for token in DIRECT_IMPACT_TOKENS if token in t)
    context_hits = sum(1 for token in CONTEXT_TOKENS if token in t)
    low_hits = sum(1 for token in LOW_VALUE_TOKENS if token in t)

    seller_relevance_score = min(5, direct_hits * 2 + context_hits)
    actionability_score = min(5, direct_hits * 2)
    is_low_value = direct_hits == 0 and (low_hits > 0 or context_hits <= 1)

    if direct_hits >= 1 and actionability_score >= 2:
        importance = "🔴"
        reason = "direct_seller_impact"
    elif seller_relevance_score >= 2:
        importance = "🟡"
        reason = "useful_context"
    else:
        importance = "🔵"
        reason = "background_low_action"

    should_publish = not is_low_value or importance != "🔵"

    return {
        "seller_relevance_score": seller_relevance_score,
        "actionability_score": actionability_score,
        "importance_indicator": importance,
        "importance_reason": reason,
        "is_low_value": is_low_value,
        "should_publish_candidate": should_publish,
        "score_diagnostics": {
            "direct_hits": direct_hits,
            "context_hits": context_hits,
            "low_hits": low_hits,
        },
    }
