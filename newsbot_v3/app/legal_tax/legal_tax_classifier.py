from __future__ import annotations

from typing import Iterable

TOPICS = [
    "tax_usn",
    "tax_vat_nds",
    "online_cash_registers",
    "fns_reports",
    "marking_chestny_znak",
    "certification_declarations",
    "product_safety",
    "import_documents",
    "platform_law",
    "advertising_restrictions",
    "personal_data",
    "fines_blocks_checks",
]

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tax_usn", ("усн", "упрощен", "упрощён")),
    ("tax_vat_nds", ("ндс", "vat", "налог на добавленную")),
    ("online_cash_registers", ("ккт", "онлайн-касс", "54-фз", "кассов")),
    ("fns_reports", ("фнс", "декларац", "отчетност", "отчётност")),
    ("marking_chestny_znak", ("честный знак", "маркировк", "коды маркировки")),
    ("certification_declarations", ("сертифик", "декларац соответств", "аккредитац")),
    ("product_safety", ("безопасност", "санитар", "роспотребнадзор")),
    ("import_documents", ("импорт", "ввоз", "тамож", "еаэс")),
    ("platform_law", ("маркетплейс", "договор оферты", "правила площадки")),
    ("advertising_restrictions", ("реклама", "маркировка рекламы", "ограничени рекламы")),
    ("personal_data", ("персональн", "152-фз", "обработка данных")),
    ("fines_blocks_checks", ("штраф", "блокиров", "проверк", "санкц")),
]


def _normalize(parts: Iterable[str]) -> str:
    return " ".join(part.strip().lower() for part in parts if part)


def classify_legal_tax_topic(title: str, text: str, source_id: str | None = None) -> dict[str, object]:
    haystack = _normalize([title, text, source_id or ""])
    matches: list[str] = []
    for topic, keywords in _RULES:
        if any(keyword in haystack for keyword in keywords):
            matches.append(topic)
    primary = matches[0] if matches else "fines_blocks_checks"
    confidence = "high" if matches else "low"
    return {
        "primary_topic": primary,
        "matched_topics": matches,
        "confidence": confidence,
    }


def estimate_seller_impact(title: str, text: str, source_id: str | None = None) -> str:
    if not source_id:
        return "impact_uncertain"
    cls = classify_legal_tax_topic(title, text, source_id=source_id)
    high_impact = {"tax_usn", "tax_vat_nds", "online_cash_registers", "marking_chestny_znak", "fines_blocks_checks"}
    if cls["primary_topic"] in high_impact:
        return "action_required_review"
    if cls["confidence"] == "low":
        return "impact_uncertain"
    return "monitor_only"


def build_seller_impact_note(title: str, text: str, source_id: str | None = None) -> str:
    impact = estimate_seller_impact(title, text, source_id=source_id)
    if impact == "impact_uncertain":
        return "Контекст источника недостаточен: влияние для селлера не подтверждено, требуется ручная проверка." 
    if impact == "action_required_review":
        return "Возможны действия для селлера, но юридическая трактовка не дается: проверьте источник, дату и статус документа." 
    return "Подтвержденных обязательных действий для селлера пока нет; продолжайте мониторинг официальных обновлений."
