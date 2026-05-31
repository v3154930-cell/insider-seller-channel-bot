import os
import re
import logging
from typing import Dict, Any, List
from seller_filter import evaluate_item as evaluate_seller_filter_item

from db import init_db, add_to_queue_batch, get_all_pending_count, get_existing_news_status, compute_content_hash
from parsers import get_all_news
from telegram_json_sources_v2 import fetch_telegram_json_sources
from scoring import score_items

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("collector_v2")


SELLER_KEYWORDS = [
    "ozon", "озон",
    "wildberries", "вайлдберриз", "wb",
    "яндекс маркет", "yandex market",
    "маркетплейс", "маркетплейсы",
    "селлер", "селлеры",
    "продавец", "продавцы",
    "комиссия", "комиссии",
    "тариф", "тарифы",
    "оферта", "оферты",
    "штраф", "штрафы",
    "возврат", "возвраты",
    "логистика", "фулфилмент", "склад",
    "fbo", "fbs", "dbs",
    "карточка товара", "личный кабинет продавца",
    "маркировка", "честный знак",
    "пвз", "пункт выдачи",
    "кабинет продавца",
    "условия работы", "правила работы", "условия для продавцов",
    "выплаты", "сроки выплат", "платеж", "платежи",
    "ндс", "трансграничные товары", "трансграничная торговля",
    "сводка", "поиск по фото", "обновил оферту", "обновила оферту",
    "личный кабинет", "платформа роста", "фас", "предупреждение фас",
    "e-commerce", "ecommerce", "интернет-торговля", "онлайн-торговля",
]

BLOCK_KEYWORDS = [
    "porsche", "bugatti", "порше", "бугатти",
    "пашинян", "биатлон", "футбол", "хоккей",
    "теннис", "уефа", "uefa",
    "министр обороны", "замминистра обороны",
    "павел иванов",
    "илон маск", "openai", "альтман",
]


def normalize_text(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def item_text(item: Dict[str, Any]) -> str:
    return " ".join([
        normalize_text(item.get("title")),
        normalize_text(item.get("description")),
        normalize_text(item.get("summary")),
        normalize_text(item.get("raw_text")),
        normalize_text(item.get("source")),
        normalize_text(item.get("link")),
    ])


def has_phrase(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase).strip()
    if not phrase:
        return False

    # Для фраз с пробелом оставляем поиск фразы.
    if " " in phrase:
        return phrase in text

    # Для одиночных слов ищем именно слово, а не кусок внутри другого слова.
    return re.search(r"(?<![a-zа-я0-9])" + re.escape(phrase) + r"(?![a-zа-я0-9])", text) is not None


def seller_score(item: Dict[str, Any]) -> int:
    text = item_text(item)

    if any(has_phrase(text, word) for word in BLOCK_KEYWORDS):
        return -100

    return sum(1 for word in SELLER_KEYWORDS if has_phrase(text, word))


def normalize_item_for_queue(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title") or ""
    description = item.get("description") or item.get("summary") or item.get("raw_text") or ""

    return {
        "title": title,
        "description": description,
        "summary": item.get("summary") or description,
        "raw_text": item.get("raw_text") or description,
        "link": item.get("link") or "",
        "source": item.get("source") or "unknown",
        "category": item.get("category") or "marketplace",
        "score": item.get("score", 0),
        "image_url": item.get("image_url") or item.get("image") or "",
    }


def main():
    logger.info("=== Collector v2 started ===")

    # Жёстко запрещаем LLM внутри collector.
    os.environ["USE_LLM"] = "false"
    os.environ["SELLER_FILTER_MODE"] = "keyword"

    init_db()

    hours = int(os.getenv("COLLECTOR_HOURS", "24"))

    news = get_all_news(hours=hours)

    try:
        tg_news = fetch_telegram_json_sources()
        logger.info("Fetched TG JSON news: %s", len(tg_news))
        news.extend(tg_news)
    except Exception as e:
        logger.warning("TG JSON fetch failed: %s", e)

    logger.info("Fetched raw news: %s", len(news))

    if not news:
        logger.warning("No news fetched")
        return

    try:
        news = score_items(news)
        logger.info("Scored news: %s", len(news))
    except Exception as e:
        logger.warning("Scoring failed, continuing without scoring: %s", e)

    selected = []
    seller_decisions = {}
    selected_diagnostics = []

    for item in news:
        score = seller_score(item)
        title = str(item.get("title", ""))[:120]

        logger.info("candidate score=%s title=%s", score, title)

        # Routing logic:
        # score >= 3  -> publish as a separate post
        # score 1-2   -> keep for digest
        # score <= 0  -> ignore
        if score >= 1:
            q_item = normalize_item_for_queue(item)
            q_item["seller_score"] = score
            link = q_item.get("link") or ""
            content_hash = compute_content_hash(q_item.get("title", ""), link)
            existing_status = get_existing_news_status(link, content_hash)

            if score >= 3:
                decision = "publish"
                actionability = min(score, 10)
            else:
                decision = "digest"
                actionability = max(1, min(score, 10))

            q_item["seller_decision"] = decision
            q_item["seller_relevance_score"] = min(score, 10)
            q_item["actionability_score"] = actionability
            q_item["existing_db_status"] = existing_status.get("status", "new")
            q_item["canonical_published"] = existing_status.get("canonical_published", "0")

            if link:
                seller_decisions[link] = {
                    "decision": decision,
                    "seller_relevance_score": min(score, 10),
                    "actionability_score": actionability,
                    "reason": f"keyword_score={score}",
                }

            selected.append(q_item)
            selected_diagnostics.append(
                "existing DB status title=%r source=%r decision=%s rel=%s act=%s status=%s canonical_published=%s link=%r" % (
                    str(q_item.get("title", ""))[:120],
                    str(q_item.get("source", ""))[:60],
                    decision,
                    q_item["seller_relevance_score"],
                    q_item["actionability_score"],
                    q_item["existing_db_status"],
                    q_item["canonical_published"],
                    str(link)[:180],
                )
            )

    for line in selected_diagnostics[:80]:
        logger.info(line)

    logger.info("Selected seller-relevant news: %s", len(selected))
    logger.info(
        "Seller decisions: publish=%s digest=%s",
        sum(1 for v in seller_decisions.values() if v.get("decision") == "publish"),
        sum(1 for v in seller_decisions.values() if v.get("decision") == "digest"),
    )

    if not selected:
        logger.warning("No seller-relevant news selected. Queue unchanged.")
        return

    inserted = add_to_queue_batch(selected, seller_decisions=seller_decisions)
    logger.info("Inserted to queue: %s", inserted)

    pending = get_all_pending_count()
    logger.info("Pending after collector v2: %s", pending)
    try:
        from db import _fetch_one
        pending_publish_row = _fetch_one(
            "SELECT COUNT(*) FROM news WHERE IFNULL(is_published,0)=0 AND seller_decision='publish'"
        )
        pending_publish_after_write = int((pending_publish_row or [0])[0] or 0)
    except Exception as e:
        logger.warning("Failed to read pending_publish_after_write: %s", e)
        pending_publish_after_write = -1

    publish_selected = [
        i for i in selected
        if i.get("seller_decision") == "publish"
        and not (
            i.get("existing_db_status") in ("existing_published", "duplicate")
            and str(i.get("canonical_published", "0")) == "1"
        )
    ]
    logger.info("publish_selected_fresh=%s total_publish_selected=%s", len(publish_selected), sum(1 for i in selected if i.get("seller_decision") == "publish"))
    if publish_selected and pending_publish_after_write == 0:
        examples = [
            f"{idx+1}) title={str(i.get('title',''))[:120]!r} link={str(i.get('link',''))[:120]!r}"
            for idx, i in enumerate(publish_selected[:5])
        ]
        logger.error(
            "INVARIANT_BROKEN publish decisions > 0 but pending_publish_after_write == 0; publish_selected=%s inserted=%s examples=%s",
            len(publish_selected),
            inserted,
            " | ".join(examples),
        )

    logger.info("=== Collector v2 finished ===")


if __name__ == "__main__":
    main()
