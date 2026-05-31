from __future__ import annotations

import re

NATIVE_AD_LEADGEN_PATTERNS: tuple[str, ...] = (
    "работаете на wb/ozon",
    "деньги приходят, не те",
    "проведём аудит",
    "вернём деньги",
    "разберём каждый",
    "идём вглубь",
    "штрафы начислены",
    "по документам всё проведено",
    "оставьте заявку",
    "напишите нам",
    "аудит кабинета",
    "поможем вернуть",
)

NATIVE_AD_EVENT_ANCHORS: tuple[str, ...] = (
    "вебинар",
    "круглый стол",
    "мероприятие",
    "эфир",
    "встреча",
)

NATIVE_AD_EVENT_PROMO_SIGNALS: tuple[str, ...] = (
    "приглашаем",
    "зарегистрируйтесь",
    "регистрация",
    "участие",
    "разберём",
    "обсудим",
    "расскажем",
    "как торговать на маркетплейсах",
    "начать зарабатывать на маркетплейсах",
)

NATIVE_AD_EVENT_DATE_TIME_RE = re.compile(
    r"(?:\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b\s*(?:в\s*)?\d{1,2}:\d{2}\b|\bв\s*\d{1,2}:\d{2}\s*(?:мск|мск\.)\b)",
    re.IGNORECASE,
)


def detect_native_ad_leadgen_reason(title: str, text: str) -> str | None:
    haystack = f"{title or ''} {text or ''}".lower()
    for pattern in NATIVE_AD_LEADGEN_PATTERNS:
        if pattern in haystack:
            return "native_ad_leadgen"
    if any(anchor in haystack for anchor in NATIVE_AD_EVENT_ANCHORS):
        has_promo_signal = any(signal in haystack for signal in NATIVE_AD_EVENT_PROMO_SIGNALS)
        has_date_time_signal = bool(NATIVE_AD_EVENT_DATE_TIME_RE.search(haystack))
        if has_promo_signal or has_date_time_signal:
            return "native_ad_leadgen"
    return None
