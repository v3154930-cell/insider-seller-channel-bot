from __future__ import annotations

import hashlib
from typing import Any

from app.models import NewsItem
from app.scoring.seller_actionability import determine_importance, score_seller_actionability

SELLER_SIGNALS = (
    "seller", "селлер", "продав", "маркетплейс", "wildberries", "wb", "ozon", "яндекс маркет", "avito",
    "комис", "тариф", "маркиров", "налог", "фнс", "документ", "отчет", "комплаенс", "платформ"
)


def _content_hash(source: str, link: str, title: str) -> str:
    return hashlib.sha1(f"{source}|{link}|{title}".encode("utf-8")).hexdigest()


def is_v2_row_already_published(row: dict[str, Any]) -> bool:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else row

    is_published = raw.get("is_published")
    if is_published is not None and str(is_published).strip().lower() in {"1", "true", "yes"}:
        return True

    max_message_id = raw.get("max_message_id")
    if max_message_id is not None and str(max_message_id).strip():
        return True

    full_article_message_id = raw.get("full_article_message_id")
    if full_article_message_id is not None and str(full_article_message_id).strip():
        return True

    return False


def normalize_v2_row_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    # V2 rows usually store full article text in raw_text/processed_text, not in text.
    # If we only pass title forward, V3 post_builder creates empty "headline + takeaway" posts.
    text = (
        row.get("processed_text")
        or row.get("text")
        or row.get("raw_text")
        or row.get("summary")
        or row.get("description")
        or row.get("content")
        or ""
    )
    text = str(text or "").strip()

    link = (row.get("link") or "").strip()
    title = (row.get("title") or "").strip()
    source = (row.get("source") or "v2").strip()
    tl = f"{title} {text}".lower()

    seller_relevant = any(token in tl for token in SELLER_SIGNALS)
    scored = score_seller_actionability(title, text, source=source)
    tags = list(scored.get("topics", []))
    direct = bool(scored.get("direct_actions"))
    importance, _importance_reason = determine_importance(scored)

    if seller_relevant:
        rel = max(3, int(row.get("seller_relevance_score") or scored.get("seller_relevance_score") or 0))
        act = max(3, int(row.get("actionability_score") or scored.get("actionability_score") or 0))
        score = 0.8
    else:
        rel, act, direct, importance, score = 1, 1, False, "🔵", 0.3
        tags = ["low_value_background"]
        if any(token in tl for token in ("штраф", "суд", "закон")):
            tags = ["generic_non_seller_legal", "low_value_background"]

    item = NewsItem(
        news_id=str(row.get("v2_news_id") or row.get("id") or ""),
        title=title or "v2 news",
        text=text,
        link=link or None,
        source_name=source,
        importance=importance,
    )
    return {
        "id": f"candidate-v2-{row.get('v2_news_id') or row.get('id')}",
        "v2_news_id": str(row.get("v2_news_id") or row.get("id") or ""),
        "source": source,
        "title": title,
        "link": link,
        "item": item,
        "seller_relevance_score": rel,
        "actionability_score": act,
        "direct_action": direct,
        "direct_publish": direct,
        "importance": importance,
        "score": score,
        "topic_tags": tags,
        "content_hash": _content_hash(source, link, title),
    }
