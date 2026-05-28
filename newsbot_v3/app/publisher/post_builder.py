from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from app.models import NewsItem

READ_MORE_MIN_FULL_TEXT_CHARS = 1200
READ_MORE_MIN_EXTRA_CHARS_OVER_POST = 500


@dataclass
class ReadMoreDecision:
    needed: bool
    reason: str


def _pick_full_text(item: NewsItem) -> str:
    return (getattr(item, "raw_text", None) or getattr(item, "text", None) or "").strip()


def _strip_raw_urls(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", str(text or ""))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip(" \n,;:-")


def _source_label(item: NewsItem) -> str:
    if getattr(item, "source_name", None):
        return _strip_raw_urls(str(item.source_name)) or "unknown"
    link = getattr(item, "link", "") or ""
    return (urlparse(link).netloc or "unknown") if link else "unknown"


def _main_post_has_raw_url(text: str) -> bool:
    return bool(re.search(r"https?://", str(text or "")))


def should_add_read_more_button(item: NewsItem, post_text: str) -> ReadMoreDecision:
    full_text = _pick_full_text(item)
    if not full_text:
        return ReadMoreDecision(False, "full_text_missing")
    if len(full_text) < READ_MORE_MIN_FULL_TEXT_CHARS:
        return ReadMoreDecision(False, "full_text_below_threshold")
    if len(full_text) - len(post_text or "") < READ_MORE_MIN_EXTRA_CHARS_OVER_POST:
        return ReadMoreDecision(False, "full_text_not_materially_longer")
    return ReadMoreDecision(True, "full_text_materially_longer")


def build_post(item: NewsItem, seller_result: dict | None = None) -> dict:
    seller_result = seller_result or {}
    title = _strip_raw_urls(getattr(item, "title", "") or "") or "Новость для селлеров"
    summary = _strip_raw_urls(seller_result.get("summary") or (getattr(item, "text", "") or "")[:420])
    conclusion = _strip_raw_urls(seller_result.get("seller_conclusion") or "Прямых действий пока нет.")
    importance = _strip_raw_urls(seller_result.get("importance_indicator") or getattr(item, "importance", "🟡"))
    source_name = _source_label(item)
    source_url = (getattr(item, "link", "") or "").strip()

    text = f"**{title}**\n{summary}\n\nВывод для селлера:\n{conclusion}\n\n{importance}\nИсточник: {source_name}"
    source_link_present = bool(source_url)
    raw_source_url_in_main_post = _main_post_has_raw_url(text)

    decision = should_add_read_more_button(item, text)
    callback_payload = f"full_article:{item.news_id}" if decision.needed else None
    callback_button_used = bool(decision.needed and callback_payload)

    return {
        "text": text,
        "button_text": "Читать полностью" if decision.needed else None,
        "callback_payload": callback_payload,
        "forbidden_external_button": True,
        "read_more_button_type": "callback" if decision.needed else "none",
        "read_more_button_text": "Читать полностью" if decision.needed else "",
        "read_more_payload": callback_payload if decision.needed else "",
        "callback_button_used": callback_button_used,
        "source_url_button_used": False,
        "external_url_button_forbidden": True,
        "read_more_needed": decision.needed,
        "read_more_reason": decision.reason,
        "read_more_button_present": decision.needed,
        "read_more_callback_payload_present": bool(callback_payload and callback_payload.startswith("full_article:")),
        "source_link_present": source_link_present,
        "source_url_present": source_link_present,
        "source_name_present": bool(source_name),
        "raw_source_url_in_main_post": raw_source_url_in_main_post,
        "source_link_preview_suppressed": True,
        "post_length": len(text),
        "summary_mode": seller_result.get("summary_mode", "rules"),
    }
