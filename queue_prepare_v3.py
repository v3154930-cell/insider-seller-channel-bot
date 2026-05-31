#!/usr/bin/env python3
import re
import sqlite3
from datetime import datetime

DB = "/opt/newsbot_v2/news_queue.db"

MARKETPLACE_WORDS = (
    "ozon", "wildberries", "wb", "яндекс", "yandex",
    "маркетплейс", "маркет"
)

SELLER_IMPACT_WORDS = (
    "тариф", "тарифы", "комисси", "логист", "доставк",
    "оферт", "выплат", "штраф", "блокиров", "маркиров",
    "честный знак", "api", "апи", "fbo", "fbs", "realfbs",
    "возврат", "хранение", "склад", "карточк", "пвз",
    "заказ", "остатк", "киз", "приостановк", "витрин",
    "кабинет другого продавца"
)

BAD_REGULAR_WORDS = (
    "вебинар", "круглый стол", "зарегистр", "обучение",
    "курс", "эфир", "подкаст", "поздравляем",
    "день предпринимателя", "розыгрыш", "конкурс",
    "sellerden", "генератор видео", "tiktok", "тик ток",
    "все, что вы могли пропустить", "всё, что вы могли пропустить",
    "#дайджест_ozon", "дайджест ozon"
)

def norm(value):
    return (value or "").lower().replace("ё", "е")

def has_any(text, words):
    return any(w in text for w in words)

def row_text(row):
    return norm(
        str(row["title"] or "") + " " +
        str(row["raw_text"] or "") + " " +
        str(row["source"] or "")
    )

def topic_key(text):
    rules = (
        ("gosuslugi_complaints", ("госуслуг", "жалоб")),
        ("ozon_realfbs_partners", ("ozon", "realfbs", "экспресс")),
        ("ozon_delivery_external", ("ozon доставка", "без выхода на витрину")),
        ("wb_payout_offer", ("wildberries", "приостанов", "выплат")),
        ("wb_payout_offer", ("wb", "приостанов", "выплат")),
        ("wb_marked_cards_transfer", ("wb", "перенос", "карточ", "маркиров")),
        ("wb_marked_cards_transfer", ("wildberries", "перенос", "карточ", "маркиров")),
        ("wb_foreign_commission", ("wb", "иностран", "комисси")),
        ("wb_foreign_commission", ("wildberries", "иностран", "комисси")),
        ("wb_foreign_commission", ("китайск", "селлер", "комисси")),
    )
    for key, words in rules:
        if all(w in text for w in words):
            return key

    cleaned = re.sub(r"[^a-zа-я0-9 ]+", " ", text)
    tokens = [x for x in cleaned.split() if len(x) >= 4]
    return "kw:" + "_".join(tokens[:12])

def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    published_topics = set()
    for r in con.execute("""
        SELECT title, raw_text, source
        FROM news
        WHERE COALESCE(is_published,0)=1
           OR COALESCE(max_message_id,'')!=''
    """):
        published_topics.add(topic_key(row_text(r)))

    rows = con.execute("""
        SELECT id, title, raw_text, source, seller_decision,
               seller_relevance_score, actionability_score,
               is_published, max_message_id
        FROM news
        WHERE COALESCE(is_published,0)=0
          AND COALESCE(max_message_id,'')=''
          AND COALESCE(seller_decision,'') IN ('publish','digest','pending','ignore','')
        ORDER BY id DESC
        LIMIT 800
    """).fetchall()

    seen_current_publish = set()
    updated = 0
    promoted = 0
    demoted = 0
    duplicates = 0

    for r in rows:
        rid = int(r["id"])
        old_decision = r["seller_decision"] or "pending"
        old_rel = int(r["seller_relevance_score"] or 0)
        old_act = int(r["actionability_score"] or 0)

        text = row_text(r)
        key = topic_key(text)

        is_marketplace = has_any(text, MARKETPLACE_WORDS)
        is_impact = has_any(text, SELLER_IMPACT_WORDS)
        is_bad = has_any(text, BAD_REGULAR_WORDS)

        decision = old_decision
        rel = old_rel
        act = old_act
        reason = "keep"

        if is_bad:
            decision = "digest"
            reason = "bad_regular_to_digest"
        elif key in published_topics:
            decision = "digest"
            reason = "semantic_duplicate_published"
            duplicates += 1
        elif is_marketplace and is_impact:
            decision = "publish"
            rel = max(rel, 4)
            act = max(act, 4)
            reason = "seller_impact_to_publish"
        elif old_decision == "publish":
            decision = "digest"
            reason = "weak_publish_to_digest"

        if decision == "publish":
            if key in seen_current_publish:
                decision = "digest"
                reason = "semantic_duplicate_pending"
                duplicates += 1
            else:
                seen_current_publish.add(key)

        if decision != old_decision or rel != old_rel or act != old_act:
            if decision == "publish" and old_decision != "publish":
                promoted += 1
            if old_decision == "publish" and decision != "publish":
                demoted += 1

            con.execute("""
                UPDATE news
                SET seller_decision=?,
                    seller_relevance_score=?,
                    actionability_score=?,
                    reason_tags=TRIM(COALESCE(reason_tags,'') || ' | queue_prepare_v3_single_gateway:' || ?)
                WHERE id=?
                  AND COALESCE(is_published,0)=0
                  AND COALESCE(max_message_id,'')=''
            """, (decision, rel, act, reason, rid))
            updated += 1

    con.commit()

    print("QUEUE_PREPARE_V3_SINGLE_GATEWAY_STATUS=OK")
    print("checked=", len(rows))
    print("updated=", updated)
    print("promoted_to_publish=", promoted)
    print("demoted_from_publish=", demoted)
    print("duplicates_demoted=", duplicates)

    print("=== publish pending ===")
    for r in con.execute("""
        SELECT id, source, seller_decision, seller_relevance_score,
               actionability_score, substr(title,1,240) AS title
        FROM news
        WHERE seller_decision='publish'
          AND COALESCE(is_published,0)=0
          AND COALESCE(max_message_id,'')=''
        ORDER BY seller_relevance_score DESC, actionability_score DESC, id DESC
        LIMIT 30
    """):
        print(dict(r))

    con.close()

if __name__ == "__main__":
    main()
