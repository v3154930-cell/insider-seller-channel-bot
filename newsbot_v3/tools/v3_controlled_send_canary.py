#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from uuid import uuid4

from app.collector.v2_news_adapter import load_unpublished_news
from app.db import get_v3_db_path, init_v3_runtime_db
from app.max_client import MaxClient, MaxClientGuardError, MaxClientSendError
from app.publisher.candidate_normalizer import is_v2_row_already_published, normalize_v2_row_to_candidate
from app.publisher.native_ad_filter import detect_native_ad_leadgen_reason
from app.publisher.post_builder import build_post
from app.publisher.selection_policy import dry_run_selection
from app.publisher.quality_gate import evaluate_selection_quality_gate
from app.publisher.cta import SELLER_HELPER_BUTTON_TEXT, SELLER_HELPER_CTA
from app.visual.mascot_assets import select_mascot_asset, visuals_enabled

REQUIRED_CONFIRM = "I_UNDERSTAND_V3_SENDS_TO_PRODUCTION"


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() == "true"


def _nonempty(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _raw(row: dict) -> dict:
    return row.get("raw") if isinstance(row.get("raw"), dict) else row


def _raw_value(row: dict, key: str):
    val = row.get(key)
    if val is None:
        val = _raw(row).get(key)
    return val


def _is_v2_publish_candidate(row: dict) -> bool:
    decision = str(_raw_value(row, "seller_decision") or "").strip().lower()
    if decision != "publish":
        return False
    if is_v2_row_already_published(row):
        return False
    seller_relevance = int(_raw_value(row, "seller_relevance_score") or 0)
    actionability = int(_raw_value(row, "actionability_score") or 0)
    if seller_relevance < 3 or actionability < 3:
        return False
    if not str(row.get("link") or row.get("source_link") or "").strip():
        return False
    title = str(_raw_value(row, "title") or "")
    text = str(_raw_value(row, "text") or "")
    if detect_native_ad_leadgen_reason(title, text):
        return False
    return True


def _candidate_sort_key(row: dict) -> tuple:
    actionability = int(_raw_value(row, "actionability_score") or 0)
    seller_relevance = int(_raw_value(row, "seller_relevance_score") or 0)
    has_link = 1 if str(row.get("link") or row.get("source_link") or "").strip() else 0
    created_at = str(_raw_value(row, "created_at") or _raw_value(row, "published_at") or "")
    return (actionability, seller_relevance, has_link, created_at)


def _load_candidate(v2_db: str, limit: int = 200, v2_id: str | None = None) -> tuple[dict | None, str, dict]:
    try:
        rows = load_unpublished_news(v2_db, limit=limit)
    except Exception:
        gate = evaluate_selection_quality_gate(None, after_daily_min=False)
        return None, "skipped_no_candidate", gate

    if v2_id:
        rows = [r for r in rows if str(r.get("v2_news_id") or r.get("id") or "") == str(v2_id)]

    skipped_digest = 0
    skipped_low_score = 0
    skipped_published = 0
    skipped_native_ad_leadgen = 0
    publish_candidates_seen = 0
    filtered_rows = []
    for row in rows:
        decision = str(_raw_value(row, "seller_decision") or "").strip().lower()
        if decision != "publish":
            skipped_digest += 1
            continue
        publish_candidates_seen += 1
        if is_v2_row_already_published(row):
            skipped_published += 1
            continue
        seller_relevance = int(_raw_value(row, "seller_relevance_score") or 0)
        actionability = int(_raw_value(row, "actionability_score") or 0)
        if seller_relevance < 3 or actionability < 3:
            skipped_low_score += 1
            continue
        if not str(row.get("link") or row.get("source_link") or "").strip():
            continue
        title = str(_raw_value(row, "title") or "")
        text = str(_raw_value(row, "text") or "")
        if detect_native_ad_leadgen_reason(title, text):
            skipped_native_ad_leadgen += 1
            continue
        filtered_rows.append(row)

    if not filtered_rows:
        gate = evaluate_selection_quality_gate(None, after_daily_min=False)
        gate.update(
            {
                "v2_publish_candidates_seen": publish_candidates_seen,
                "v2_publish_candidates_eligible": 0,
                "v2_candidate_loader_limit": limit,
                "v2_digest_candidates_skipped": skipped_digest,
                "v2_low_score_candidates_skipped": skipped_low_score,
                "v2_published_candidates_skipped": skipped_published,
                "native_ad_leadgen_candidates_skipped": skipped_native_ad_leadgen,
                "duplicate_v2_published_skipped": skipped_published > 0,
                "selected_candidate_id": None,
                "selection_reason": "skipped_native_ad_leadgen" if skipped_native_ad_leadgen > 0 else "skipped_no_unpublished_v2_publish_candidate",
                "canary_editorial_gate_reason": "native_ad_leadgen" if skipped_native_ad_leadgen > 0 else "",
            }
        )
        return None, "skipped_no_unpublished_v2_publish_candidate", gate

    filtered_rows.sort(key=_candidate_sort_key, reverse=True)
    candidates = [normalize_v2_row_to_candidate(row) for row in filtered_rows]
    sel = dry_run_selection(candidates, published_today=0)
    sel["v2_digest_candidates_skipped"] = skipped_digest
    sel["v2_low_score_candidates_skipped"] = skipped_low_score
    sel["v2_published_candidates_skipped"] = skipped_published
    sel["native_ad_leadgen_candidates_skipped"] = skipped_native_ad_leadgen
    sel["v2_publish_candidates_seen"] = publish_candidates_seen
    sel["v2_publish_candidates_eligible"] = len(filtered_rows)
    sel["v2_candidate_loader_limit"] = limit
    sel["duplicate_v2_published_skipped"] = skipped_published > 0
    selected_id = sel.get("selected_candidate_id")
    selected = next((c for c in candidates if c.get("id") == selected_id), None)
    if not selected or not selected.get("link"):
        return None, "skipped_no_candidate", sel
    return selected, "quality_gate_passed_with_source_link", sel


def _guard_ok() -> tuple[bool, list[str]]:
    misses = []
    if not _truthy("NEWSBOT_V3_PRODUCTION_SEND"):
        misses.append("NEWSBOT_V3_PRODUCTION_SEND=true")
    if os.getenv("NEWSBOT_V3_CUTOVER_CONFIRM", "") != REQUIRED_CONFIRM:
        misses.append("NEWSBOT_V3_CUTOVER_CONFIRM")
    if not _nonempty("NEWSBOT_V3_PRODUCTION_CHANNEL_ID"):
        misses.append("NEWSBOT_V3_PRODUCTION_CHANNEL_ID")
    if not _nonempty("NEWSBOT_V3_MAX_TOKEN"):
        misses.append("NEWSBOT_V3_MAX_TOKEN")
    if os.getenv("NEWSBOT_V3_MOCK_MAX", "true").strip().lower() != "false":
        misses.append("NEWSBOT_V3_MOCK_MAX=false")
    if not _truthy("NEWSBOT_V3_REAL_SEND"):
        misses.append("NEWSBOT_V3_REAL_SEND=true")
    return (len(misses) == 0), misses


def _exists_duplicate(con: sqlite3.Connection, v2_news_id: str, content_hash: str) -> bool:
    if v2_news_id:
        row = con.execute("SELECT 1 FROM published_messages WHERE candidate_id LIKE ? LIMIT 1", (f"%{v2_news_id}%",)).fetchone()
        if row:
            return True
        row = con.execute("SELECT 1 FROM send_attempts WHERE candidate_id LIKE ? LIMIT 1", (f"%{v2_news_id}%",)).fetchone()
        if row:
            return True
    row = con.execute("SELECT 1 FROM published_messages WHERE candidate_id LIKE ? LIMIT 1", (f"%{content_hash}%",)).fetchone()
    if row:
        return True
    row = con.execute("SELECT 1 FROM send_attempts WHERE candidate_id LIKE ? LIMIT 1", (f"%{content_hash}%",)).fetchone()
    return bool(row)


def _fetch_v2_publish_state(v2_db: str, v2_news_id: str) -> tuple[int | None, str]:
    if not v2_news_id:
        return None, ""
    con = sqlite3.connect(v2_db)
    try:
        row = con.execute("SELECT is_published, COALESCE(max_message_id, '') FROM news WHERE id = ? LIMIT 1", (v2_news_id,)).fetchone()
        if not row:
            return None, ""
        return int(row[0]) if row[0] is not None else 0, str(row[1] or "")
    finally:
        con.close()


def _mark_v2_published(v2_db: str, v2_news_id: str, max_message_id: str) -> bool:
    if not v2_news_id:
        return False
    con = sqlite3.connect(v2_db)
    try:
        cur = con.execute(
            "UPDATE news SET is_published = 1, max_message_id = ? WHERE id = ?",
            (str(max_message_id or ""), v2_news_id),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--v2-db", default="/opt/newsbot_v2/news_queue.db")
    ap.add_argument("--v2-id", default=None)
    args = ap.parse_args()

    candidate, reason, selection_diag = _load_candidate(args.v2_db, v2_id=args.v2_id)
    real_send = args.execute
    target_channel = os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "")
    visual_assets_enabled = visuals_enabled()
    mascot_asset_kind, mascot_asset_selected = select_mascot_asset(post_kind="regular")
    mascot_attachment_planned = visual_assets_enabled and bool(mascot_asset_selected)
    mascot_send_status = "dry_run" if (not real_send and mascot_attachment_planned) else "skipped"

    item = candidate["item"] if candidate else None
    source_image_present = bool(
        getattr(item, "image_url", None)
        or getattr(item, "media_url", None)
        or getattr(item, "picture", None)
        or getattr(item, "thumbnail", None)
    )

    result = {
        "V3_CONTROLLED_SEND_STATUS": "DRY_RUN" if not real_send else "FAIL",
        "send_status": "dry_run",
        "real_send": str(real_send).lower(),
        "target_channel": target_channel,
        "quality_gate_passed": "false",
        "selected_candidate_id": "None",
        "selection_reason": reason,
        "source_link_present": "false",
        "read_more_needed": "false",
        "read_more_button_type": "none",
        "read_more_button_text": "",
        "read_more_button_present": "false",
        "read_more_payload": "",
        "callback_button_used": "false",
        "source_url_button_used": "false",
        "external_url_button_forbidden": "true",
        "raw_source_url_in_main_post": "false",
        "source_link_preview_suppressed": "true",
        "seller_helper_cta_planned": "true",
        "seller_helper_cta_present": "true",
        "seller_helper_cta_mode": "separate_message",
        "seller_helper_cta_text": SELLER_HELPER_BUTTON_TEXT,
        "seller_helper_cta_url_present": "true",
        "seller_helper_cta_send_attempted": "false",
        "seller_helper_cta_send_status": "dry_run",
        "seller_helper_cta_message_id": "",
        "seller_helper_cta_error": "",
        "seller_helper_cta_visible_delivery_confirmed": "false",
        "separate_seller_helper_message_sent": "false",
        "keyboard_contract_valid": "true",
        "max_send_method": "",
        "max_message_id": "",
        "send_attempt_recorded": "false",
        "published_message_recorded": "false",
        "v2_db_mutation": "false",
        "production_mutation": "false",
        "v2_recheck_before_send": "true",
        "v2_pre_send_is_published": "",
        "v2_pre_send_max_message_id": "",
        "v2_mark_published_enabled": str(_truthy("NEWSBOT_V3_MARK_V2_PUBLISHED")).lower(),
        "v2_marked_published_by_v3": "false",
        "rollback_hint": "disable NEWSBOT_V3_PRODUCTION_SEND and keep v2 production",
        "selection_quality_gate_status": selection_diag.get("selection_quality_gate_status", "skipped"),
        "candidate_seller_relevance_score": str(selection_diag.get("candidate_seller_relevance_score", 0)),
        "candidate_actionability_score": str(selection_diag.get("candidate_actionability_score", 0)),
        "candidate_topic_tags": selection_diag.get("candidate_topic_tags", ""),
        "candidate_direct_action_status": selection_diag.get("candidate_direct_action_status", "none"),
        "v2_digest_candidates_skipped": str(selection_diag.get("v2_digest_candidates_skipped", 0)),
        "v2_low_score_candidates_skipped": str(selection_diag.get("v2_low_score_candidates_skipped", 0)),
        "v2_published_candidates_skipped": str(selection_diag.get("v2_published_candidates_skipped", 0)),
        "native_ad_leadgen_candidates_skipped": str(selection_diag.get("native_ad_leadgen_candidates_skipped", 0)),
        "v2_publish_candidates_seen": str(selection_diag.get("v2_publish_candidates_seen", 0)),
        "v2_publish_candidates_eligible": str(selection_diag.get("v2_publish_candidates_eligible", 0)),
        "v2_candidate_loader_limit": str(selection_diag.get("v2_candidate_loader_limit", 0)),
        "duplicate_v2_published_skipped": str(bool(selection_diag.get("duplicate_v2_published_skipped", False))).lower(),
        "canary_editorial_gate_reason": selection_diag.get("canary_editorial_gate_reason", ""),
        "max_mode": "",
        "max_guard_ok": "false",
        "mock_message_id_forbidden": str(real_send).lower(),
        "visual_assets_enabled": str(visual_assets_enabled).lower(),
        "mascot_asset_selected": mascot_asset_selected if visual_assets_enabled else "",
        "mascot_asset_kind": mascot_asset_kind if visual_assets_enabled else "",
        "mascot_attachment_planned": str(bool(mascot_attachment_planned)).lower(),
        "mascot_attachment_sent": "false",
        "mascot_send_status": mascot_send_status,
        "source_image_present": str(source_image_present).lower(),
    }

    if not candidate:
        result["V3_CONTROLLED_SEND_STATUS"] = "SKIPPED"
        result["send_status"] = reason if str(reason).startswith("skipped_") else "skipped_no_candidate"
        for k, v in result.items():
            print(f"{k}={v}")
        return 0

    post = build_post(candidate["item"])
    result.update(
        {
            "quality_gate_passed": "true",
            "selected_candidate_id": candidate["id"],
            "source_link_present": str(bool(candidate.get("link"))).lower(),
            "read_more_needed": str(bool(post.get("read_more_needed"))).lower(),
            "read_more_button_type": str(post.get("read_more_button_type") or "none"),
            "read_more_button_text": str(post.get("read_more_button_text") or ""),
            "read_more_button_present": str(bool(post.get("read_more_button_present"))).lower(),
            "read_more_payload": post.get("callback_payload") or "",
            "callback_button_used": str(bool(post.get("callback_button_used", False))).lower(),
            "source_url_button_used": str(bool(post.get("source_url_button_used", False))).lower(),
            "external_url_button_forbidden": str(bool(post.get("external_url_button_forbidden", True))).lower(),
            "raw_source_url_in_main_post": str(bool(post.get("raw_source_url_in_main_post", False))).lower(),
            "source_link_preview_suppressed": str(bool(post.get("source_link_preview_suppressed", True))).lower(),
            "source_image_present": str(source_image_present).lower(),
        }
    )

    if post.get("read_more_needed") and not str(post.get("callback_payload", "")).startswith("full_article:"):
        result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
        result["send_status"] = "fail_invalid_read_more_payload"
        for k, v in result.items():
            print(f"{k}={v}")
        return 1

    if not real_send:
        for k, v in result.items():
            print(f"{k}={v}")
        return 0

    ok, misses = _guard_ok()
    if not ok:
        result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
        result["send_status"] = "failed_closed_missing_guards"
        result["selection_reason"] = f"missing_guards:{','.join(misses)}"
        for k, v in result.items():
            print(f"{k}={v}")
        return 1

    v2_news_id = str(candidate.get("v2_news_id") or "")
    v2_pre_is_published, v2_pre_max_message_id = _fetch_v2_publish_state(args.v2_db, v2_news_id)
    result["v2_pre_send_is_published"] = "" if v2_pre_is_published is None else str(v2_pre_is_published)
    result["v2_pre_send_max_message_id"] = v2_pre_max_message_id
    if v2_pre_is_published == 1:
        result["V3_CONTROLLED_SEND_STATUS"] = "SKIPPED"
        result["send_status"] = "skipped_v2_already_published"
        result["production_mutation"] = "false"
        for k, v in result.items():
            print(f"{k}={v}")
        return 0

    init_v3_runtime_db()
    con = sqlite3.connect(str(get_v3_db_path()))
    try:
        if _exists_duplicate(con, candidate.get("v2_news_id", ""), candidate.get("content_hash", "")):
            result["V3_CONTROLLED_SEND_STATUS"] = "SKIPPED"
            result["send_status"] = "skipped_duplicate_v3"
            for k, v in result.items():
                print(f"{k}={v}")
            return 0

        client = MaxClient.from_env(target_channel=target_channel)
        client_diag = client.diagnostics()
        result["max_mode"] = str(client_diag.get("max_mode", ""))
        result["max_guard_ok"] = str(bool(client_diag.get("max_guard_ok", False))).lower()
        result["mock_message_id_forbidden"] = str(real_send).lower()
        try:
            if post.get("read_more_needed"):
                resp = client.send_text_with_callback_button(target_channel, post["text"], post["button_text"], post["callback_payload"])
                result["max_send_method"] = "send_text_with_callback_button"
            else:
                resp = client.send_text(target_channel, post["text"])
                result["max_send_method"] = "send_text"
        except MaxClientGuardError:
            result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
            result["send_status"] = "failed_closed_max_guard"
            for k, v in result.items():
                print(f"{k}={v}")
            return 1
        except MaxClientSendError:
            result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
            result["send_status"] = "failed_main_send"
            for k, v in result.items():
                print(f"{k}={v}")
            return 1

        msg_id = client.extract_message_id(resp)
        if not (client.validate_visible_delivery(resp) and msg_id):
            result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
            result["send_status"] = "failed_main_send"
            for k, v in result.items():
                print(f"{k}={v}")
            return 1

        if real_send and str(msg_id).startswith("mock-msg-"):
            result["V3_CONTROLLED_SEND_STATUS"] = "FAIL"
            result["send_status"] = "failed_mock_message_id_for_real_send"
            result["max_message_id"] = str(msg_id)
            for k, v in result.items():
                print(f"{k}={v}")
            return 1

        attempt_id = f"canary-{uuid4().hex[:12]}"
        candidate_key = f"{candidate['id']}|h:{candidate['content_hash']}|v2:{candidate.get('v2_news_id','')}"
        con.execute("INSERT INTO send_attempts(attempt_id,candidate_id,sent_at,status,error_message) VALUES(?,?,?,?,?)", (attempt_id, candidate_key, datetime.utcnow().isoformat(), "sent", None))
        con.execute("INSERT INTO published_messages(candidate_id,message_id,channel,published_at,status) VALUES(?,?,?,?,?)", (candidate_key, msg_id, target_channel, datetime.utcnow().isoformat(), "sent"))
        con.execute("INSERT INTO system_events(event_id,event_type,severity,message) VALUES(?,?,?,?)", (f"canary-{uuid4().hex[:10]}", "canary_send", "info", f"sent:{candidate_key}"))
        con.commit()
        result["V3_CONTROLLED_SEND_STATUS"] = "OK"
        result["send_status"] = "sent"
        result["max_message_id"] = str(msg_id)
        result["send_attempt_recorded"] = "true"
        result["published_message_recorded"] = "true"
        result["production_mutation"] = "true"
        helper_url = os.getenv("SELLER_HELPER_URL", "").strip()
        if not helper_url:
            helper_url = os.getenv("SELLER_HELPER_BOT_URL", "").strip()
        if not helper_url:
            result["seller_helper_cta_send_status"] = "error"
            result["seller_helper_cta_error"] = "missing_url"
        else:
            result["seller_helper_cta_send_attempted"] = "true"
            try:
                cta_resp = client.send_text_with_url_button(target_channel, SELLER_HELPER_CTA, SELLER_HELPER_BUTTON_TEXT, helper_url)
                cta_mid = client.extract_message_id(cta_resp) or ""
                is_real_like = bool(cta_mid) and (not real_send or not cta_mid.startswith("mock-msg-"))
                if client.validate_visible_delivery(cta_resp) and is_real_like:
                    result["seller_helper_cta_send_status"] = "sent"
                    result["seller_helper_cta_message_id"] = cta_mid
                    result["seller_helper_cta_visible_delivery_confirmed"] = "true"
                    result["separate_seller_helper_message_sent"] = "true"
                elif client.validate_visible_delivery(cta_resp) and not cta_mid:
                    result["seller_helper_cta_send_status"] = "error"
                    result["seller_helper_cta_error"] = "no_message_id"
                else:
                    result["seller_helper_cta_send_status"] = "error"
                    result["seller_helper_cta_error"] = "delivery_not_confirmed"
            except Exception as exc:
                result["seller_helper_cta_send_status"] = "error"
                result["seller_helper_cta_error"] = str(exc).splitlines()[0][:80]
        if _truthy("NEWSBOT_V3_MARK_V2_PUBLISHED"):
            marked = _mark_v2_published(args.v2_db, v2_news_id, str(msg_id))
            result["v2_marked_published_by_v3"] = str(marked).lower()
            result["v2_db_mutation"] = str(marked).lower()
    finally:
        con.close()

    for k, v in result.items():
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
