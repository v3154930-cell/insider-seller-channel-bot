from __future__ import annotations


def _summary(text: str) -> str:
    return (text or "").strip()[:700] or "Нет подробного текста."


def _conclusion(is_low_value: bool, actionability_score: int) -> str:
    if is_low_value or actionability_score == 0:
        return "Прямого действия для селлера не требуется; новость носит справочный характер."
    return "Проверьте применимость изменения к вашему ассортименту и операционным процессам."


def conservative_fallback(text: str, scoring: dict | None = None) -> dict:
    scoring = scoring or {}
    return {
        "summary": _summary(text),
        "seller_conclusion": _conclusion(bool(scoring.get("is_low_value")), int(scoring.get("actionability_score", 0))),
        "importance_indicator": scoring.get("importance_indicator", "🟡"),
        "importance_reason": scoring.get("importance_reason", "fallback"),
    }
