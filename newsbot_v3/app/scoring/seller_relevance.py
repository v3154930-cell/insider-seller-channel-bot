from __future__ import annotations

from .seller_actionability import determine_importance, score_seller_actionability


def evaluate_seller_relevance(title: str, text: str, marketplace: str | None = None, source: str | None = None) -> dict:
    scored = score_seller_actionability(title, text, source=source, marketplace=marketplace)
    importance, reason = determine_importance(scored)
    scored["importance_indicator"] = importance
    scored["importance_reason"] = reason
    scored["marketplace"] = marketplace or _detect_marketplace(f"{title or ''} {text or ''}")
    return scored


def _detect_marketplace(text: str) -> str:
    t = (text or "").lower()
    if "wildberries" in t or " wb " in f" {t} ":
        return "wildberries"
    if "ozon" in t:
        return "ozon"
    if "яндекс" in t:
        return "yandex_market"
    return "unknown"
