import os
import re
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List

from db import init_db, get_pending_news, mark_published, cleanup_by_retention_policy, _fetch_all, _execute
from publisher_imports import send_message, send_seller_helper_cta, format_news, append_source_line, save_link, has_full_article

import sys
from llm import enhance_post_with_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("publisher_v2")

MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "2"))

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


def item_text(item: Dict[str, Any]) -> str:
    return " ".join([
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("description", "")),
        str(item.get("raw_text", "")),
        str(item.get("source", "")),
        str(item.get("link", "")),
    ]).lower().replace("ё", "е")


def normalize_text(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def has_phrase(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase).strip()
    if not phrase:
        return False

    if " " in phrase:
        return phrase in text

    return re.search(r"(?<![a-zа-я0-9])" + re.escape(phrase) + r"(?![a-zа-я0-9])", text) is not None


def seller_score(item: Dict[str, Any]) -> int:
    text = item_text(item)

    if any(has_phrase(text, word) for word in BLOCK_KEYWORDS):
        return -100

    return sum(1 for word in SELLER_KEYWORDS if has_phrase(text, word))


def select_items(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """
    Publisher must trust collector routing.
    Collector decides seller_decision and scores.
    Publisher only sorts already-approved publish items.
    """
    scored = []

    for item in items:
        seller_relevance = int(item.get("seller_relevance_score") or 0)
        actionability = int(item.get("actionability_score") or 0)
        total_score = seller_relevance + actionability

        logger.info(
            "candidate id=%s db_score=%s/%s total=%s title=%s",
            item.get("id"),
            seller_relevance,
            actionability,
            total_score,
            str(item.get("title", ""))[:100],
        )

        scored.append((total_score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:limit]]


def normalize_channel_id(channel_id: str) -> str:
    channel_id = str(channel_id or "").strip()

    if channel_id.startswith("@"):
        return "-73160979033512"

    if channel_id.isdigit():
        return f"-{channel_id}"

    return channel_id



def extract_max_message_id(send_result):
    if isinstance(send_result, dict):
        msg = send_result.get("message")
        if isinstance(msg, dict):
            body = msg.get("body")
            if isinstance(body, dict) and body.get("mid"):
                return str(body.get("mid"))
            if msg.get("id"):
                return str(msg.get("id"))
        for key in ("message_id", "id", "mid"):
            if send_result.get(key):
                return str(send_result.get(key))
    return ""


def save_max_message_id(news_id, max_message_id):
    if not news_id or not max_message_id:
        return
    import sqlite3
    conn = sqlite3.connect("news_queue.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE news SET max_message_id = ? WHERE id = ?",
        (str(max_message_id), int(news_id)),
    )
    conn.commit()
    conn.close()



# PUBLISHER SEMANTIC DEDUP V1
# Collector решает маршрут publish/digest, но publisher обязан не отправлять
# второй пост по уже опубликованной теме.

def _pd_norm(value):
    return str(value or "").lower().replace("ё", "е")


def _pd_clean(value):
    t = _pd_norm(value)
    replacements = [
        ("wildberries", "вб"),
        ("вайлдберриз", "вб"),
        ("wb", "вб"),
        ("ozon", "озон"),
        ("яндекс маркет", "яндекс"),
        ("oborot.ru", ""),
        ("oborot ru", ""),
        ("tg:oborotru", ""),
        ("tg:marketplace_biz", ""),
        ("tg:mpgo_ru", ""),
        ("tg:crmmarketplace", ""),
    ]

    for a, b in replacements:
        t = t.replace(a, b)

    t = re.sub(r"[^0-9a-zа-яё%₽ ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def publisher_topic_key(item):
    title = _pd_clean(item.get("title") or "")
    raw = _pd_clean(item.get("raw_text") or "")
    source = _pd_clean(item.get("source") or "")
    text = f"{title} {raw} {source}".strip()

    # Жёсткие ключи для частых дублей.
    if "инфляц" in text and "маркетплейс" in text:
        return "marketplace_inflation"

    if "озон" in text and ("отзыв" in text or "рейтинг" in text) and ("вид" in text or "склейк" in text):
        return "ozon_reviews_by_variant"

    if "авито" in text and "платн" in text and "возврат" in text:
        return "avito_paid_return_low_buyout"

    if "вб" in text and ("возврат" in text or "обратн" in text) and ("тариф" in text or "логист" in text or "остатк" in text or "21 мая" in text):
        return "wb_return_tariff_logistics"

    if "вб" in text and "маркировк" in text and ("бизнес" in text or "юрлиц" in text or "ип" in text):
        return "wb_marking_business_resale"

    if "вб" in text and ("выплат" in text or "вернут 5" in text or "5 от оборота" in text or "комисси" in text) and "сотрудничеств" in text:
        return "wb_extended_cooperation_payout"

    if "озон" in text and "пвз" in text and ("утилизирован" in text or "списан" in text):
        return "ozon_utilized_goods_pvz"

    if "озон" in text and "штраф" in text and "выходн" in text:
        return "ozon_weekend_return_penalty"

    if "сменить ип" in text or ("передать" in text and "карточк" in text and "озон" in text):
        return "ozon_ip_change_cards_transfer"

    # Общий ключ по словам.
    stop = {
        "это", "как", "что", "или", "для", "при", "без", "под", "над",
        "селлер", "селлера", "селлеров", "продавец", "продавцов",
        "маркетплейс", "маркетплейса", "маркетплейсов",
        "новости", "день", "сегодня", "теперь", "уже", "если",
        "может", "будет", "стали", "стал", "сообщил", "сообщила",
    }

    words = [w for w in text.split() if len(w) > 2 and w not in stop]
    return " ".join(words[:12])


def publisher_topics_similar(a, b):
    a = _pd_clean(a)
    b = _pd_clean(b)

    if not a or not b:
        return False

    wa = set(w for w in a.split() if len(w) > 3)
    wb = set(w for w in b.split() if len(w) > 3)

    if not wa or not wb:
        return False

    overlap = len(wa & wb)
    smaller = min(len(wa), len(wb))

    if smaller and overlap / smaller >= 0.62:
        return True

    pairs = [
        ("инфляц", "маркетплейс"),
        ("возврат", "тариф"),
        ("возврат", "логистик"),
        ("отзыв", "рейтинг"),
        ("маркировк", "бизнес"),
        ("пвз", "утилизирован"),
        ("сотрудничеств", "выплат"),
    ]

    for x, y in pairs:
        if x in a and y in a and x in b and y in b:
            return True

    return False


def find_recent_published_duplicate(item, hours=48):
    """
    Ищет уже опубликованную похожую тему за последние 7 дней.
    Возвращает row или None.
    """
    current_id = item.get("id")
    current_key = publisher_topic_key(item)
    current_title = item.get("title") or ""

    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    rows = _fetch_all("""
        SELECT
            id,
            title,
            raw_text,
            link,
            source,
            score,
            created_at
        FROM news
        WHERE is_published = 1
          AND id != ?
          AND created_at >= ?
        ORDER BY created_at DESC, score DESC, id DESC
        LIMIT 300
    """, (current_id, cutoff))

    for row in rows:
        other = {
            "id": row[0],
            "title": row[1],
            "raw_text": row[2],
            "link": row[3],
            "source": row[4],
            "score": row[5],
            "created_at": row[6],
        }

        other_key = publisher_topic_key(other)
        other_title = other.get("title") or ""

        if current_key and other_key and current_key == other_key:
            return other

        if publisher_topics_similar(current_title, other_title):
            return other

    return None


def mark_duplicate_as_digest(news_id, duplicate_of):
    """
    Чтобы не пытаться публиковать дубль снова на следующем запуске,
    переводим его из publish в digest. Историю не удаляем.
    """
    _execute("""
        UPDATE news
        SET seller_decision = 'duplicate', is_published = 1
        WHERE id = ?
          AND is_published = 0
          AND seller_decision = 'publish'
    """, (news_id,))

    logger.info(
        "SKIP_DUP_TOPIC id=%s duplicate_of=%s -> seller_decision=duplicate",
        news_id,
        duplicate_of,
    )

# END PUBLISHER SEMANTIC DEDUP V1

def main():
    token = os.getenv("MAX_BOT_TOKEN")
    channel_id = normalize_channel_id(os.getenv("CHANNEL_ID"))

    if not token:
        raise SystemExit("MAX_BOT_TOKEN is empty")

    if not channel_id:
        raise SystemExit("CHANNEL_ID is empty")

    logger.info("=== Publisher v2 started ===")

    init_db()

    try:
        cleanup_result = cleanup_by_retention_policy()
        if cleanup_result:
            logger.info("Retention cleanup result: %s", cleanup_result)
    except Exception as e:
        logger.warning("Retention cleanup failed: %s", e)


    # park_stale_publish_before_pending
    try:
        stale_hours = int(os.getenv("PUBLISH_STALE_GUARD_HOURS", "8") or "8")
        _execute(
            """
            UPDATE news
            SET
                seller_decision = 'duplicate',
                reason_tags = COALESCE(reason_tags, '') || ' | parked_by_publisher_stale_guard'
            WHERE is_published = 0
              AND seller_decision = 'publish'
              AND datetime(created_at) < datetime('now','localtime', ?)
            """,
            (f"-{stale_hours} hours",),
        )
        logger.info("Stale publish guard applied. hours=%s", stale_hours)
    except Exception as e:
        logger.warning("Stale publish guard failed: %s", e)

    # quota_fallback_auto_promote_digest
    # If the daily publish quota is under target and there are no normal publish candidates,
    # promote strong digest items into publish so the channel does not go silent.
    try:
        fallback_enabled = (os.getenv("PUBLISH_QUOTA_FALLBACK_ENABLED", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
        # Daily target is a minimum for quota fallback, not a publishing cap.
        # Weekdays: default minimum 10. Weekends: default minimum 3.
        weekday_target = int(os.getenv("PUBLISH_WEEKDAY_TARGET", os.getenv("PUBLISH_DAILY_TARGET", "10")) or "10")
        weekend_target = int(os.getenv("PUBLISH_WEEKEND_TARGET", "3") or "3")
        try:
            from datetime import datetime as _quota_dt
            from zoneinfo import ZoneInfo as _QuotaZoneInfo
            _weekday = _quota_dt.now(_QuotaZoneInfo(os.getenv("NEWSBOT_TZ", "Europe/Moscow"))).weekday()
        except Exception:
            from datetime import datetime as _quota_dt
            _weekday = _quota_dt.now().weekday()
        daily_target = weekend_target if _weekday >= 5 else weekday_target
        fallback_batch = int(os.getenv("PUBLISH_FALLBACK_BATCH", "6") or "6")
        fallback_lookback_hours = int(os.getenv("PUBLISH_FALLBACK_LOOKBACK_HOURS", "24") or "24")
        fallback_min_relevance = int(os.getenv("PUBLISH_FALLBACK_MIN_RELEVANCE", "2") or "2")
        fallback_min_actionability = int(os.getenv("PUBLISH_FALLBACK_MIN_ACTIONABILITY", "2") or "2")

        if fallback_enabled and daily_target > 0 and fallback_batch > 0:
            import sqlite3 as _sqlite3

            _qconn = _sqlite3.connect("news_queue.db")
            try:
                _qcur = _qconn.cursor()

                _published_today_row = _qcur.execute(
                    """
                    SELECT COUNT(*)
                    FROM news
                    WHERE is_published = 1
                      AND seller_decision = 'publish'
                      AND datetime(created_at) >= datetime('now','localtime','start of day')
                    """
                ).fetchone()
                published_today = int((_published_today_row or [0])[0] or 0)

                _pending_publish_row = _qcur.execute(
                    """
                    SELECT COUNT(*)
                    FROM news
                    WHERE IFNULL(is_published,0) = 0
                      AND seller_decision = 'publish'
                    """
                ).fetchone()
                pending_publish = int((_pending_publish_row or [0])[0] or 0)

                logger.info(
                    "quota fallback check: enabled=%s published_today=%s target=%s pending_publish=%s",
                    fallback_enabled,
                    published_today,
                    daily_target,
                    pending_publish,
                )

                if published_today < daily_target and pending_publish == 0:
                    need = min(fallback_batch, max(0, daily_target - published_today))
                    lookback_arg = f"-{fallback_lookback_hours} hours"

                    _qcur.execute(
                        """
                        WITH candidates AS (
                            SELECT id
                            FROM news
                            WHERE IFNULL(is_published,0) = 0
                              AND seller_decision = 'digest'
                              AND datetime(created_at) >= datetime('now','localtime', ?)
                              AND IFNULL(actionability_score,0) >= ?
                              AND IFNULL(seller_relevance_score,0) >= ?
                            ORDER BY
                              actionability_score DESC,
                              seller_relevance_score DESC,
                              datetime(created_at) DESC
                            LIMIT ?
                        )
                        UPDATE news
                        SET
                            seller_decision = 'publish',
                            created_at = CURRENT_TIMESTAMP,
                            reason_tags = COALESCE(reason_tags,'') || ' | quota_fallback_auto'
                        WHERE id IN (SELECT id FROM candidates)
                        """,
                        (
                            lookback_arg,
                            fallback_min_actionability,
                            fallback_min_relevance,
                            need,
                        ),
                    )
                    promoted = _qcur.rowcount if _qcur.rowcount is not None else 0
                    _qconn.commit()

                    _after_row = _qcur.execute(
                        """
                        SELECT COUNT(*)
                        FROM news
                        WHERE IFNULL(is_published,0) = 0
                          AND seller_decision = 'publish'
                        """
                    ).fetchone()
                    pending_after = int((_after_row or [0])[0] or 0)

                    logger.info(
                        "quota fallback promoted digest->publish: need=%s promoted_rowcount=%s pending_after=%s lookback_hours=%s min_rel=%s min_act=%s",
                        need,
                        promoted,
                        pending_after,
                        fallback_lookback_hours,
                        fallback_min_relevance,
                        fallback_min_actionability,
                    )
            finally:
                _qconn.close()
    except Exception as e:
        logger.warning("quota fallback failed: %s", e)

    pending = get_pending_news(30)
    logger.info("pending loaded=%s", len(pending))

    if not pending:
        logger.info("No pending news")
        return

    selected = select_items(pending, MAX_POSTS_PER_RUN)
    logger.info("selected=%s", [item.get("id") for item in selected])

    if not selected:
        logger.warning("No seller-relevant items selected. Nothing published.")
        return

    sent = 0

    for item in selected:
        link = item.get("link") or ""

        duplicate = find_recent_published_duplicate(item, hours=168)
        if duplicate:
            logger.info(
                "SKIP_DUP_TOPIC id=%s duplicate_of=%s current_title=%r duplicate_title=%r",
                item.get("id"),
                duplicate.get("id"),
                item.get("title"),
                duplicate.get("title"),
            )
            mark_duplicate_as_digest(item.get("id"), duplicate.get("id"))
            continue

        logger.info("Final LLM enhance started for id=%s", item.get("id"))

        enhanced = None
        try:
            enhanced = enhance_post_with_llm(item)
        except Exception as e:
            logger.warning("Final LLM enhance exception for id=%s: %s", item.get("id"), e)

        if enhanced:
            logger.info("Final LLM enhance ok for id=%s", item.get("id"))
            text = enhanced
        else:
            logger.warning("Final LLM enhance failed for id=%s, using template fallback", item.get("id"))
            text = format_news(item)

        text = append_source_line(text, link)

        full_article_available = has_full_article(item)


        ok = send_message(


            token,


            channel_id,


            text,


            full_article_news_id=item.get("id"),


            add_full_article_button=full_article_available,


        )

        if ok:
            max_message_id = extract_max_message_id(ok)
            if max_message_id:
                save_max_message_id(item.get("id"), max_message_id)
                logger.info("Saved max_message_id for id=%s mid=%s", item.get("id"), max_message_id)

            if link:
                save_link(link)
            mark_published(item["id"])
            sent += 1
            logger.info("Posted id=%s", item.get("id"))
        else:
            logger.error("Failed to post id=%s", item.get("id"))

    if sent > 0:
        logger.info("Sending Seller Helper CTA after published batch. sent=%s", sent)
        try:
            send_seller_helper_cta(token, channel_id)
        except Exception as e:
            logger.warning("Seller Helper CTA failed: %s", e)

    logger.info("=== Publisher v2 finished. Sent=%s ===", sent)


if __name__ == "__main__":
    main()
