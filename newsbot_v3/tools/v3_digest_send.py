#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.max_client import MaxClient, MaxClientSendError
from app.visual.mascot_assets import select_mascot_asset, visuals_enabled

MOSCOW_OFFSET = timedelta(hours=3)

NATIVE_AD_TERMS = (
    "вебинар", "webinar", "лидоген", "leadgen", "лид-магнит", "натив", "native ad", "лиды", "event", "ивент",
)
LOW_VALUE_TERMS = (
    "дайджест", "подборка", "подкаст", "эфир", "эмоцион", "история", "обзор",
)
EVENT_EPISODE_TERMS = (
    "круглый стол", "вебинар", "мероприятие", "в новом выпуске", "обсудили в выпуске", "эфир", "регистрация", "приглашаем",
)
SOCIAL_LOW_VALUE_TERMS = (
    "поддерживаем?", "👍", "👎", "кто для вас", "по вайбу", "морковки",
)
MARKETPLACE_TERMS = (
    "ozon", "wb", "wildberries", "яндекс", "yandex", "маркетплейс", "маркетплейсы",
)

STRONG_ACTIONABLE_TERMS = (
    "тариф", "комис", "логист", "fbo", "fbs", "dbs", "выплат", "компенсац", "штраф", "оферт",
    "маркиров", "заявк на вывоз", "sku", "скопирован", "личный кабинет продавца", "жалоб", "фас",
    "возврат", "пвз", "склад",
)

SELLER_FACING_TERMS = (
    "селлер", "продавц", "для продав", "кабинет продав", "личный кабинет",
)

GENERIC_BACKGROUND_TERMS = (
    "бренд", "развити", "среда для развития", "нейросет", " ии ", " ai ", "поисков", "выдач", "интерфейс",
    "кладовщик", "мужчин", "дискриминац",
)

DIGEST_HARD_DENY_TERMS = (
    "поддержке почты россии",
    "почты россии",
    "только ии и нейросети",
    "китайские маркетплейсы",
    "полностью отказываются от обычной поисковой выдачи",
    "поисковой выдачи",
    "ии-агент",
    "кладовщика-мужчину",
    "искать кладовщика",
    "суд запретил яндекс маркету искать кладовщика",
    "маркетплейсы постепенно становятся средои для развития брендов",
    "средои для развития брендов",
    "развития брендов а не только каналом продаж",
    "не только каналом продаж",
    "работать с карточкои товара ценои отзывами",
    "карточкои товара ценои отзывами и прод",
)


def moscow_now() -> datetime:
    return datetime.utcnow() + MOSCOW_OFFSET


def norm(v: Any) -> str:
    text = str(v or "").lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def item_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            norm(item.get("title")),
            norm(item.get("raw_text")),
            norm(item.get("processed_text")),
            norm(item.get("source")),
            norm(item.get("link")),
        ]
    )


def is_native_ad_leadgen(item: dict[str, Any]) -> bool:
    text = item_text(item)
    return any(t in text for t in NATIVE_AD_TERMS)


def is_low_value(item: dict[str, Any]) -> bool:
    text = item_text(item)
    return any(t in text for t in LOW_VALUE_TERMS)


def is_event_episode(item: dict[str, Any]) -> bool:
    text = item_text(item)
    return any(t in text for t in EVENT_EPISODE_TERMS)


def is_social_low_value(item: dict[str, Any]) -> bool:
    text = item_text(item)
    return any(t in text for t in SOCIAL_LOW_VALUE_TERMS)


def _has_strong_actionable_signal(text: str) -> bool:
    return any(t in text for t in STRONG_ACTIONABLE_TERMS)


def _has_seller_facing_marketplace_signal(text: str) -> bool:
    has_marketplace = any(t in text for t in MARKETPLACE_TERMS)
    has_seller_facing = any(t in text for t in SELLER_FACING_TERMS)
    return has_marketplace and has_seller_facing




def is_digest_hard_deny_non_actionable(item: dict[str, Any]) -> bool:
    text = f" {item_text(item)} "
    return any(t in text for t in DIGEST_HARD_DENY_TERMS)

def is_non_actionable(item: dict[str, Any]) -> bool:
    text = f" {item_text(item)} "
    has_strong_actionable = _has_strong_actionable_signal(text)
    has_seller_facing_marketplace = _has_seller_facing_marketplace_signal(text)
    has_generic_background = any(t in text for t in GENERIC_BACKGROUND_TERMS)

    if has_generic_background and not has_strong_actionable and not has_seller_facing_marketplace:
        return True

    if not has_strong_actionable and not has_seller_facing_marketplace:
        return True

    return False


def select_candidates(raw: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: list[dict[str, Any]] = []
    counters = {
        "native_ad_leadgen_skipped": 0,
        "low_value_skipped": 0,
        "digest_event_leadgen_skipped": 0,
        "digest_social_low_value_skipped": 0,
        "digest_non_actionable_skipped": 0,
    }
    for it in raw:
        if is_native_ad_leadgen(it):
            counters["native_ad_leadgen_skipped"] += 1
            continue
        if is_low_value(it):
            counters["low_value_skipped"] += 1
            continue
        if is_event_episode(it):
            counters["digest_event_leadgen_skipped"] += 1
            continue
        if is_social_low_value(it):
            counters["digest_social_low_value_skipped"] += 1
            continue
        if is_digest_hard_deny_non_actionable(it):
            counters["digest_non_actionable_skipped"] += 1
            continue
        if is_non_actionable(it):
            counters["digest_non_actionable_skipped"] += 1
            continue
        if it.get("is_published") == 1:
            continue
        if it.get("in_digest") == 1:
            continue
        selected.append(it)
        if len(selected) >= limit:
            break
    return selected, counters


def load_candidates(v2_db: str, hours_back: int, limit: int) -> list[dict[str, Any]]:
    cutoff = (moscow_now() - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{v2_db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            SELECT id,title,raw_text,link,source,seller_decision,is_published,in_digest,score,priority_bucket,seller_relevance_score,actionability_score,created_at
            FROM news
            WHERE created_at >= ?
              AND seller_decision IN ('publish','digest')
            ORDER BY
              CASE seller_decision WHEN 'publish' THEN 1 WHEN 'digest' THEN 2 ELSE 3 END,
              seller_relevance_score DESC,
              actionability_score DESC,
              score DESC,
              id DESC
            LIMIT ?
            """,
            (cutoff, limit * 5),
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        out.append({"id": r[0], "title": r[1], "raw_text": r[2], "link": r[3], "source": r[4], "seller_decision": r[5], "is_published": r[6], "in_digest": r[7]})
    return out


def build_digest(items: list[dict[str, Any]], kind: str) -> str:
    head = "🌅 <b>УТРЕННИЙ ДАЙДЖЕСТ ДЛЯ СЕЛЛЕРОВ</b>" if kind == "morning" else "🌙 <b>ВЕЧЕРНИЙ ДАЙДЖЕСТ ДЛЯ СЕЛЛЕРОВ</b>"
    lines = [head, f"📅 {moscow_now().strftime('%d.%m.%Y')}", "", "<b>📌 Главное</b>", ""]
    if not items:
        lines.append("Подходящих новостей не найдено.")
    else:
        for i, it in enumerate(items, start=1):
            lines.append(f"{i}. <b>{(it.get('title') or 'Без заголовка')[:180]}</b>")
            if it.get("link"):
                lines.append(f"   Ссылка: {it['link']}")
            lines.append("")
    return "\n".join(lines).strip()


def ensure_v3_tables(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.executescript("""
CREATE TABLE IF NOT EXISTS send_attempts (id INTEGER PRIMARY KEY, attempt_id TEXT, candidate_id TEXT, sent_at TEXT, status TEXT, error_message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS published_messages (id INTEGER PRIMARY KEY, candidate_id TEXT, message_id TEXT, channel TEXT, published_at TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY, event_id TEXT, event_type TEXT, severity TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
""")
        con.commit()
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["morning", "final"], required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--v2-db", default="/opt/newsbot_v2/news_queue.db")
    args = ap.parse_args()

    hours_back = 12 if args.kind == "morning" else 24
    limit = 8 if args.kind == "morning" else 12
    raw = load_candidates(args.v2_db, hours_back=hours_back, limit=limit)
    candidates_seen = len(raw)

    selected, counters = select_candidates(raw, limit)

    text = build_digest(selected, args.kind)
    visual_assets_enabled = visuals_enabled()
    mascot_asset_kind, mascot_asset_selected = select_mascot_asset(post_kind="digest", digest_kind=args.kind)
    mascot_attachment_planned = visual_assets_enabled and bool(mascot_asset_selected)
    mascot_send_status = "dry_run" if (not args.execute and mascot_attachment_planned) else "skipped"
    real_send = args.execute
    status = "DRY_RUN"
    max_message_id = ""
    send_attempt_recorded = False
    published_message_recorded = False
    v2_mark_enabled = os.getenv("NEWSBOT_V3_MARK_V2_DIGESTED", "false").lower() == "true"
    v2_rows_marked = 0

    if real_send:
        guard_ok = all([
            os.getenv("NEWSBOT_V3_PRODUCTION_SEND", "false").lower() == "true",
            os.getenv("NEWSBOT_V3_REAL_SEND", "false").lower() == "true",
            os.getenv("NEWSBOT_V3_MOCK_MAX", "true").lower() == "false",
            os.getenv("NEWSBOT_V3_CUTOVER_CONFIRM", "") == "I_UNDERSTAND_V3_SENDS_TO_PRODUCTION",
            bool(os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "").strip()),
            bool(os.getenv("NEWSBOT_V3_MAX_TOKEN", "").strip()),
        ])
        if not guard_ok:
            print("V3_DIGEST_STATUS=FAIL")
            print(f"digest_kind={args.kind}")
            print(f"visual_assets_enabled={str(visual_assets_enabled).lower()}")
            print(f"mascot_asset_selected={mascot_asset_selected}")
            print(f"mascot_asset_kind={mascot_asset_kind if visual_assets_enabled else ""}")
            print(f"mascot_attachment_planned={str(bool(mascot_attachment_planned)).lower()}")
            print(f"mascot_send_status=skipped")
            print("real_send=true")
            print("send_status=failed_guard")
            return 1
        channel = os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "").strip()
        os.environ["NEWSBOT_V3_TEST_CHANNEL_ID"] = channel
        os.environ["NEWSBOT_MAX_CHANNEL_ID"] = channel
        client = MaxClient.from_env(target_channel=channel)
        try:
            primary_send_error = ""
            if mascot_attachment_planned and mascot_asset_selected:
                try:
                    resp = client.send_text_with_image(channel, text, mascot_asset_selected)
                    mascot_send_status = "sent"
                except MaxClientSendError as exc:
                    primary_send_error = str(exc)[:1000]
                    resp = client.send_text(channel, text)
                    mascot_send_status = "fallback_text_after_image_failed"
            else:
                resp = client.send_text(channel, text)
                mascot_send_status = "skipped"

            max_message_id = client.extract_message_id(resp) or ""
            if max_message_id.startswith("mock-msg-"):
                raise RuntimeError("mock message id forbidden in real mode")
            ensure_v3_tables(os.getenv("V3_DB", "/opt/newsbot_v3/runtime/newsbot_v3.db"))
            con = sqlite3.connect(os.getenv("V3_DB", "/opt/newsbot_v3/runtime/newsbot_v3.db"))
            try:
                con.execute("INSERT INTO send_attempts(attempt_id,candidate_id,sent_at,status,error_message) VALUES(?,?,?,?,?)", (f"digest-{uuid4().hex[:12]}", f"digest-{args.kind}", datetime.utcnow().isoformat(), "sent", None))
                con.execute("INSERT INTO published_messages(candidate_id,message_id,channel,published_at,status) VALUES(?,?,?,?,?)", (f"digest-{args.kind}", max_message_id, channel, datetime.utcnow().isoformat(), "sent"))
                con.execute("INSERT INTO system_events(event_id,event_type,severity,message) VALUES(?,?,?,?)", (f"digest-{uuid4().hex[:12]}", "v3_digest_send", "info", f"digest_sent:{args.kind}"))
                con.commit()
                send_attempt_recorded = True; published_message_recorded = True
            finally:
                con.close()
            if v2_mark_enabled and selected:
                con2 = sqlite3.connect(args.v2_db)
                try:
                    ids = [int(x["id"]) for x in selected]
                    q = ",".join(["?"] * len(ids))
                    con2.execute(f"UPDATE news SET in_digest=1 WHERE id IN ({q})", ids)
                    con2.commit(); v2_rows_marked = len(ids)
                finally:
                    con2.close()
            status = "OK"
        except Exception:
            status = "FAIL"

    print(f"V3_DIGEST_STATUS={status}")
    print(f"digest_kind={args.kind}")
    print(f"visual_assets_enabled={str(visual_assets_enabled).lower()}")
    print(f"mascot_asset_selected={mascot_asset_selected if visual_assets_enabled else ""}")
    print(f"mascot_asset_kind={mascot_asset_kind if visual_assets_enabled else ""}")
    print(f"mascot_attachment_planned={str(bool(mascot_attachment_planned)).lower()}")
    print(f"mascot_send_status={mascot_send_status}")
    print(f"primary_image_send_error={locals().get('primary_send_error', '')}")
    print(f"real_send={'true' if real_send else 'false'}")
    print(f"candidates_seen={candidates_seen}")
    print(f"candidates_selected={len(selected)}")
    print(f"native_ad_leadgen_skipped={counters['native_ad_leadgen_skipped']}")
    print(f"low_value_skipped={counters['low_value_skipped']}")
    print(f"digest_event_leadgen_skipped={counters['digest_event_leadgen_skipped']}")
    print(f"digest_social_low_value_skipped={counters['digest_social_low_value_skipped']}")
    print(f"digest_non_actionable_skipped={counters['digest_non_actionable_skipped']}")
    print(f"v2_mutation_enabled={'true' if v2_mark_enabled else 'false'}")
    print(f"v2_rows_marked_digest={v2_rows_marked}")
    print(f"max_message_id={max_message_id}")
    print(f"send_attempt_recorded={'true' if send_attempt_recorded else 'false'}")
    print(f"published_message_recorded={'true' if published_message_recorded else 'false'}")
    print(f"production_mutation={'true' if real_send else 'false'}")
    if not real_send:
        print(text)
    return 0 if status in {"OK", "DRY_RUN"} else 1

if __name__ == '__main__':
    raise SystemExit(main())

