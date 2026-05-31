#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from app.collector.v2_news_adapter import get_news_columns, load_recent_news, load_unpublished_news
from app.models import NewsItem
from app.publisher.publisher import shadow_publish_one
from app.publisher.candidate_normalizer import normalize_v2_row_to_candidate
from app.publisher.selection_policy import dry_run_selection


def _sample_candidates(limit: int) -> list[dict]:
    txt = "Обновление условий для селлеров и комиссий. " * 80
    items = [
        {"id": "shadow-sample-1", "importance": "🟡", "score": 0.81, "seller_relevance_score": 3, "actionability_score": 3, "direct_action": True, "topic_tags": ["marketplace_rules"], "item": NewsItem("sample-1", "Sample seller update", txt, "https://example.com/sample", "sample")},
        {"id": "shadow-sample-2", "importance": "🔵", "score": 0.2, "seller_relevance_score": 1, "actionability_score": 1, "direct_action": False, "topic_tags": ["low_value_background"], "item": NewsItem("sample-2", "Sample low-value", "short", "https://example.com/low", "sample")},
    ]
    return items[:limit]


def _read_v2_candidates(v2_db: Path, scenario: str, limit: int) -> tuple[list[dict], dict]:
    diag = {"v2_db_readable": False, "v2_news_columns": "", "v2_news_rows_seen": 0, "v2_rows_normalized": 0, "v2_adapter_status": "FAIL", "v2_adapter_reason": "db_unreadable"}
    try:
        cols = get_news_columns(v2_db)
        rows = load_recent_news(v2_db, limit) if scenario == "from_v2_recent" else load_unpublished_news(v2_db, limit)
        diag["v2_db_readable"] = True
        diag["v2_news_columns"] = ",".join(cols)
        diag["v2_news_rows_seen"] = len(rows)
        cands = []
        for row in rows:
            cands.append(normalize_v2_row_to_candidate(row))
        diag["v2_rows_normalized"] = len(cands)
        diag["v2_adapter_status"] = "OK" if cands else "WARN"
        diag["v2_adapter_reason"] = "rows_normalized" if cands else "no_rows"
        return cands, diag
    except Exception as exc:
        diag["v2_adapter_reason"] = str(exc)
        return [], diag


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--v2-db", default="/opt/newsbot_v2/news_queue.db")
    p.add_argument("--v2-root", default="/opt/newsbot_v2")
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--scenario", default="sample", choices=["sample", "from_v2_unpublished", "from_v2_recent"])
    args = p.parse_args()

    source = "sample"
    if args.scenario == "sample":
        candidates = _sample_candidates(args.limit)
        diag = {"v2_db_readable": True, "v2_news_columns": "sample", "v2_news_rows_seen": len(candidates), "v2_rows_normalized": len(candidates), "v2_adapter_status": "OK", "v2_adapter_reason": "sample_mode"}
    else:
        source = "v2"
        candidates, diag = _read_v2_candidates(Path(args.v2_db), args.scenario, args.limit)

    sel = dry_run_selection(candidates, published_today=0)
    selected = next((c for c in candidates if c.get("id") == sel.get("selected_candidate_id")), None)

    status = "FAIL"
    shadow = {}
    if selected:
        selected = {**selected, "selection_reason": sel.get("selection_reason")}
        shadow = shadow_publish_one(selected, source=source, helper_cta_enabled=True)
        status = "OK" if shadow.get("v3_db_write") else "WARN"
    elif candidates or (args.scenario != "sample" and diag.get("v2_db_readable")):
        status = "WARN"

    print(f"V3_SHADOW_REHEARSAL_STATUS={status}")
    print(f"source={source}")
    print(f"v2_db_readable={'true' if diag.get('v2_db_readable') else 'false'}")
    print(f"v2_adapter_status={diag.get('v2_adapter_status')}")
    print(f"v2_news_columns={diag.get('v2_news_columns')}")
    print(f"v2_news_rows_seen={diag.get('v2_news_rows_seen')}")
    print(f"v2_rows_normalized={diag.get('v2_rows_normalized')}")
    print(f"items_seen={len(candidates)}")
    print(f"selected_candidate_id={sel.get('selected_candidate_id')}")
    print(f"selection_reason={sel.get('selection_reason')}")
    print(f"selection_quality_gate_applied={str(bool(sel.get('selection_quality_gate_applied'))).lower()}")
    print(f"selection_quality_gate_status={sel.get('selection_quality_gate_status')}")
    print(f"selection_quality_gate_reason={sel.get('selection_quality_gate_reason')}")
    print(f"candidate_seller_relevance_score={sel.get('candidate_seller_relevance_score')}")
    print(f"candidate_actionability_score={sel.get('candidate_actionability_score')}")
    print(f"candidate_topic_tags={sel.get('candidate_topic_tags')}")
    print(f"candidate_direct_action_status={sel.get('candidate_direct_action_status')}")
    print(f"post_built={'true' if shadow.get('post_built') else 'false'}")
    print(f"read_more_needed={shadow.get('read_more_needed')}")
    print(f"read_more_payload={shadow.get('read_more_payload')}")
    print(f"source_link_present={shadow.get('source_link_present')}")
    print(f"helper_cta_planned={shadow.get('helper_cta_planned')}")
    print("max_send=false")
    print(f"v3_db_write={'true' if shadow.get('v3_db_write') else 'false'}")
    print("v2_db_mutation=false")
    print("production_mutation=false")
    media = shadow.get("media_plan", {})
    print(f"image_present={str(bool(media.get('image_present'))).lower()}")
    print(f"image_source={media.get('image_source')}")
    print(f"placeholder_category={media.get('placeholder_category')}")
    print("image_attach_attempted=false")
    print("image_required=false")
    print(f"image_fallback_reason={media.get('fallback_reason') or ""}")
    print(f"shadow_run_id={shadow.get('shadow_run_id')}")
    print(f"v2_adapter_reason={diag.get('v2_adapter_reason')}")
    if status == "FAIL":
        next_steps = "check v2 db path/permissions and news table schema"
    elif status == "WARN" and args.scenario == "from_v2_unpublished":
        next_steps = "no_v2_unpublished_candidates"
    elif status == "WARN" and args.scenario == "from_v2_recent":
        next_steps = "no_v2_recent_candidates"
    else:
        next_steps = "inspect v3 shadow_runs/shadow_rendered_posts"
    print(f"recommended_next_steps={next_steps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
