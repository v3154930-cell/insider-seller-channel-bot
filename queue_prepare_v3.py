#!/usr/bin/env python3
import json
import os
import shlex
import sqlite3
import subprocess
from datetime import datetime

DB_PATH = os.getenv("NEWSBOT_DB_PATH", "/opt/newsbot_v2/news_queue.db")
CANARY_CMD_TEMPLATE = os.getenv(
    "NEWSBOT_V3_CANARY_CMD_TEMPLATE",
    "PYTHONPATH=/opt/newsbot_v2/newsbot_v3:/opt/newsbot_v2 /opt/newsbot_v2/venv/bin/python newsbot_v3/tools/v3_controlled_send_canary.py --v2-id {id}",
)


def parse_kv_output(text):
    out = {}
    for line in str(text or "").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def run_canary_for_id(v2_id):
    cmd = CANARY_CMD_TEMPLATE.format(id=str(v2_id))
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    parsed = parse_kv_output(combined)
    parsed["_exit_code"] = proc.returncode
    parsed["_raw_output"] = combined.strip()
    return parsed


def canary_is_eligible(diag):
    status = str(diag.get("V3_CONTROLLED_SEND_STATUS") or "")
    selected = str(diag.get("selected_candidate_id") or "")
    eligible_count = int(str(diag.get("v2_publish_candidates_eligible") or "0") or "0")
    return status == "DRY_RUN" and selected not in ("", "None", "null") and eligible_count > 0


def demotion_for_canary(diag):
    reason = str(diag.get("canary_editorial_gate_reason") or "")
    send_status = str(diag.get("send_status") or "")
    selection_reason = str(diag.get("selection_reason") or "")
    merged = " ".join([reason, send_status, selection_reason]).lower()

    if "native_ad_leadgen" in merged:
        return "ignore", "native_ad_leadgen"
    if "duplicate" in merged or "already_published" in merged or "v2_already_published" in merged:
        return "ignore", "duplicate_or_canonical_published"
    if "low_score" in merged or "no_unpublished_v2_publish_candidate" in merged:
        return "digest", "low_score_or_nonactionable"
    if "digest" in merged:
        return "digest", "digest_candidate"
    return "digest", "noneligible_by_canary"


def run_preflight(conn):
    rows = conn.execute(
        """SELECT id FROM news WHERE COALESCE(is_published,0)=0 AND seller_decision='publish' ORDER BY id ASC"""
    ).fetchall()
    pending_ids = [int(r[0]) for r in rows]

    eligible_before = 0
    demoted_ids = []
    demotion_reasons = {}
    check_errors = {}

    conn.execute("BEGIN")
    try:
        for news_id in pending_ids:
            try:
                diag = run_canary_for_id(news_id)
                if int(diag.get("_exit_code", 1)) != 0:
                    check_errors[str(news_id)] = f"canary_exit_nonzero:{diag.get('_exit_code')}"
                    continue
                if canary_is_eligible(diag):
                    eligible_before += 1
                    continue
                target_decision, reason = demotion_for_canary(diag)
                before = conn.total_changes
                conn.execute(
                    "UPDATE news SET seller_decision=? WHERE id=? AND seller_decision='publish' AND COALESCE(is_published,0)=0",
                    (target_decision, news_id),
                )
                if conn.total_changes > before:
                    demoted_ids.append(news_id)
                    demotion_reasons[str(news_id)] = reason
            except Exception as e:
                check_errors[str(news_id)] = f"canary_check_failed:{e}"
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    raw_after = int(
        conn.execute("SELECT COUNT(*) FROM news WHERE COALESCE(is_published,0)=0 AND seller_decision='publish'").fetchone()[0]
    )

    eligible_after = 0
    remaining = conn.execute(
        "SELECT id FROM news WHERE COALESCE(is_published,0)=0 AND seller_decision='publish' ORDER BY id ASC"
    ).fetchall()
    for r in remaining:
        news_id = int(r[0])
        try:
            diag = run_canary_for_id(news_id)
            if int(diag.get("_exit_code", 1)) != 0:
                check_errors.setdefault(str(news_id), f"canary_exit_nonzero:{diag.get('_exit_code')}")
                continue
            if canary_is_eligible(diag):
                eligible_after += 1
        except Exception as e:
            check_errors.setdefault(str(news_id), f"canary_check_failed:{e}")

    return {
        "raw_pending_publish_count_before": len(pending_ids),
        "canary_checked_pending_ids": pending_ids,
        "v3_eligible_pending_publish_count_before": eligible_before,
        "demoted_noneligible_publish_count": len(demoted_ids),
        "demoted_ids": demoted_ids,
        "demotion_reasons": demotion_reasons,
        "raw_pending_publish_count_after": raw_after,
        "v3_eligible_pending_publish_count_after": eligible_after,
        "check_errors": check_errors,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    out = run_preflight(conn)
    out["db_path"] = DB_PATH
    out["ts"] = datetime.now().isoformat(timespec="seconds")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
