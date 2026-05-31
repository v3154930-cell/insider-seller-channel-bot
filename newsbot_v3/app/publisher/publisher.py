from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from uuid import uuid4

from app.max_client import MaxClient
from app.models import PublishedMessage, SendAttempt
from app.publisher.cta import plan_helper_cta
from app.publisher.media import media_plan_to_dict, resolve_image_for_post
from app.publisher.post_builder import build_post
from app.publisher.selection_policy import dry_run_selection
from app.visual.mascot_assets import select_mascot_asset, visuals_enabled


def _valid_fullarticle_payload(payload: str | None) -> bool:
    return bool(payload and payload.startswith("full_article:") and len(payload.split(":", 1)[1]) > 0)


def dry_run_publish(candidates: list[dict], published_today: int = 0, helper_cta_enabled: bool = True) -> dict:
    selection = dry_run_selection(candidates, published_today)
    selected = next((c for c in candidates if c.get("id") == selection.get("selected_candidate_id")), None)
    if not selected:
        return {
            **selection,
            "post_built": False,
            "send_status": "skipped_no_candidate",
            "max_mock_send": False,
            "max_send_method": "",
            "max_message_id": "",
            "send_attempt_planned": False,
            "published_message_planned": False,
            "db_update_planned": False,
            "production_mutation": False,
            "external_url_button_used": False,
        }

    post = build_post(selected["item"], selected.get("seller_result"))
    media_plan = resolve_image_for_post(selected["item"], topic_tags=selected.get("topic_tags"), marketplace=selected.get("marketplace"))
    client = MaxClient(mock_mode=True)
    visual_enabled = visuals_enabled()
    mascot_kind, mascot_path = select_mascot_asset(post_kind="regular", tags=selected.get("topic_tags") or [], title=getattr(selected["item"], "title", ""), text=getattr(selected["item"], "text", ""), source=getattr(selected["item"], "source_name", ""))
    mascot_planned = visual_enabled and bool(mascot_path)

    if post["read_more_needed"]:
        send_resp = client.send_text_with_callback_button("mock-channel", post["text"], post["button_text"], post["callback_payload"])
        send_method = "send_text_with_callback_button"
    else:
        send_resp = client.send_text("mock-channel", post["text"])
        send_method = "send_text"

    msg_id = client.extract_message_id(send_resp)
    send_attempt = SendAttempt(attempt_id=f"dry-{uuid4().hex[:12]}", candidate_id=selected["id"], sent_at=datetime.utcnow().isoformat(), status="planned")
    published_message = PublishedMessage(candidate_id=selected["id"], message_id=msg_id, channel="mock-channel", published_at=datetime.utcnow().isoformat(), status="planned")
    cta = plan_helper_cta(enabled=helper_cta_enabled)
    return {
        **selection,
        "post_built": True,
        "send_status": "dry_run_sent",
        "read_more_needed": post["read_more_needed"],
        "read_more_button_present": post["read_more_button_present"],
        "source_link_present": post["source_link_present"],
        "max_mock_send": True,
        "max_send_method": send_method,
        "max_message_id": msg_id,
        "visible_delivery": True,
        "external_url_button_used": False,
        "fullarticle_callback_payload": post.get("callback_payload") or "",
        "fullarticle_payload_valid": _valid_fullarticle_payload(post.get("callback_payload")) if post["read_more_needed"] else True,
        "send_attempt_planned": isinstance(send_attempt, SendAttempt),
        "published_message_planned": isinstance(published_message, PublishedMessage),
        "db_update_planned": False,
        "production_mutation": False,
        "media_plan": media_plan_to_dict(media_plan),
        "visual_assets_enabled": visual_enabled,
        "mascot_asset_selected": mascot_path if visual_enabled else "",
        "mascot_asset_kind": mascot_kind if visual_enabled else "",
        "mascot_attachment_planned": mascot_planned,
        "mascot_attachment_sent": False,
        "mascot_send_status": "dry_run" if mascot_planned else "skipped",
        "source_image_present": bool(getattr(selected["item"], "image_url", None) or getattr(selected["item"], "media_url", None) or getattr(selected["item"], "picture", None) or getattr(selected["item"], "thumbnail", None)),
        **cta,
    }


def limited_live_publish_one(candidate: dict, target_channel: str, helper_cta_enabled: bool = True) -> dict:
    from app.db import get_v3_db_path, init_v3_runtime_db
    import sqlite3

    post = build_post(candidate["item"], candidate.get("seller_result"))
    media_plan = resolve_image_for_post(candidate["item"], topic_tags=candidate.get("topic_tags"), marketplace=candidate.get("marketplace"))
    client = MaxClient.from_env(target_channel=target_channel)
    diag = client.diagnostics()

    if post["read_more_needed"] and not _valid_fullarticle_payload(post.get("callback_payload")):
        return {"send_status": "error", "error": "invalid_fullarticle_payload", **diag}

    attempt_id = f"live-{uuid4().hex[:12]}"
    send_resp = {}
    send_status = "error"
    helper_status = "skipped"
    msg_id = None

    try:
        send_resp = client.send_visible_message(target_channel, post["text"])
        msg_id = client.extract_message_id(send_resp)
        send_status = "sent" if client.validate_visible_delivery(send_resp) else "error"
    except Exception as exc:
        send_status = "error"
        send_resp = {"ok": False, "error": str(exc)}

    db_write = False
    published_recorded = False
    send_attempt_recorded = False
    if send_status == "sent" and msg_id:
        init_v3_runtime_db()
        con = sqlite3.connect(str(get_v3_db_path()))
        try:
            con.execute("INSERT INTO send_attempts(attempt_id, candidate_id, sent_at, status, error_message) VALUES(?,?,?,?,?)", (attempt_id, candidate["id"], datetime.utcnow().isoformat(), "sent", None))
            con.execute("INSERT INTO published_messages(candidate_id, message_id, channel, published_at, status) VALUES(?,?,?,?,?)", (candidate["id"], msg_id, target_channel, datetime.utcnow().isoformat(), "sent"))
            con.commit()
            db_write = True
            published_recorded = True
            send_attempt_recorded = True
        finally:
            con.close()
        cta = plan_helper_cta(enabled=helper_cta_enabled)
        helper_status = cta.get("helper_cta_send_status", "planned")
    else:
        if diag.get("max_mode") == "blocked":
            send_resp["error"] = send_resp.get("error") or "guard_blocked"

    return {
        "post_built": True,
        "send_status": send_status,
        "max_message_id": msg_id or "",
        "read_more_needed": post["read_more_needed"],
        "source_link_present": post["source_link_present"],
        "fullarticle_callback_payload": post.get("callback_payload") or "",
        "fullarticle_payload_valid": _valid_fullarticle_payload(post.get("callback_payload")) if post["read_more_needed"] else True,
        "send_attempt_recorded": send_attempt_recorded,
        "published_message_recorded": published_recorded,
        "helper_cta_status": helper_status,
        "v3_db_write": db_write,
        "media_plan": media_plan_to_dict(media_plan),
        **diag,
    }


def shadow_publish_one(candidate: dict, source: str = "v2", helper_cta_enabled: bool = True) -> dict:
    from app.db import get_v3_db_path, init_v3_runtime_db

    init_v3_runtime_db()
    post = build_post(candidate["item"], candidate.get("seller_result"))
    media_plan = resolve_image_for_post(candidate["item"], topic_tags=candidate.get("topic_tags"), marketplace=candidate.get("marketplace"))
    cta = plan_helper_cta(enabled=helper_cta_enabled)
    diagnostics = {
        "max_send": False,
        "real_send": False,
        "production_mutation": False,
        "v2_db_mutation": False,
    }
    con = sqlite3.connect(str(get_v3_db_path()))
    try:
        con.execute(
            "INSERT INTO send_attempts(attempt_id, candidate_id, sent_at, status, error_message) VALUES(?,?,?,?,?)",
            (f"shadow-{uuid4().hex[:12]}", candidate["id"], datetime.utcnow().isoformat(), "shadow_no_send", None),
        )
        con.execute(
            "INSERT INTO system_events(event_id, event_type, severity, message) VALUES(?,?,?,?)",
            (f"shadow-{uuid4().hex[:12]}", "shadow_rehearsal", "info", "shadow_no_send"),
        )
        cur = con.execute(
            """INSERT INTO shadow_runs(
                source, v2_news_id, selection_reason, importance, seller_relevance_score, actionability_score,
                read_more_needed, read_more_payload, source_link_present, post_text, helper_cta_planned, status, diagnostics_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source,
                str(getattr(candidate.get("item"), "news_id", "")) or candidate.get("v2_news_id"),
                candidate.get("selection_reason"),
                candidate.get("importance"),
                float(candidate.get("seller_relevance_score", 0) or 0),
                float(candidate.get("actionability_score", 0) or 0),
                1 if post["read_more_needed"] else 0,
                post.get("callback_payload"),
                1 if post.get("source_link_present") else 0,
                post["text"],
                1 if cta.get("helper_cta_planned") else 0,
                "shadow_no_send",
                        json.dumps({**diagnostics, "media_plan": media_plan_to_dict(media_plan)}, ensure_ascii=False),
            ),
        )
        shadow_run_id = cur.lastrowid
        con.execute(
            """INSERT INTO shadow_rendered_posts(
                shadow_run_id, source, v2_news_id, post_text, read_more_needed, read_more_payload, source_link_present,
                helper_cta_planned, status, diagnostics_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                shadow_run_id,
                source,
                str(getattr(candidate.get("item"), "news_id", "")) or candidate.get("v2_news_id"),
                post["text"],
                1 if post["read_more_needed"] else 0,
                post.get("callback_payload"),
                1 if post.get("source_link_present") else 0,
                1 if cta.get("helper_cta_planned") else 0,
                "shadow_no_send",
                json.dumps({"selection_reason": candidate.get("selection_reason"), "media_plan": media_plan_to_dict(media_plan)}, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()
    return {
        "status": "shadow_no_send",
        "shadow_run_id": shadow_run_id,
        "post_built": True,
        "post_text": post["text"],
        "read_more_needed": post["read_more_needed"],
        "read_more_payload": post.get("callback_payload"),
        "source_link_present": post.get("source_link_present"),
        "helper_cta_planned": cta.get("helper_cta_planned", False),
        "v3_db_write": True,
        "media_plan": media_plan_to_dict(media_plan),
        **diagnostics,
    }
