#!/usr/bin/env python3
from __future__ import annotations

import argparse

from app.models import NewsItem
from app.publisher.publisher import dry_run_publish


def _sample_candidates(scenario: str) -> tuple[list[dict], int]:
    long_text = "Большое обновление регламентов и комиссий. " * 120
    blue = {"id": "c-blue", "importance": "🔵", "score": 0.2, "seller_relevance_score": 1, "actionability_score": 1, "direct_action": False, "topic_tags": ["low_value_background"], "item": NewsItem("101", "Фоновая новость", "Короткая заметка", "https://example.com/blue", "Blog")}
    strong = {"id": "c-strong", "importance": "🟡", "score": 0.82, "seller_relevance_score": 3, "actionability_score": 3, "direct_action": True, "topic_tags": ["marketplace_rules"], "item": NewsItem("102", "Крупное обновление WB", long_text, "https://example.com/strong", "WB")}
    red = {"id": "c-red", "importance": "🔴", "score": 0.95, "seller_relevance_score": 3, "actionability_score": 2, "direct_action": True, "topic_tags": ["marketplace_rules"], "item": NewsItem("103", "Критичное обновление", long_text, "https://example.com/red", "Ozon")}
    if scenario == "after_min_first_blue_then_strong":
        return [blue, strong], 10
    if scenario == "only_blue_after_min":
        return [blue], 10
    if scenario == "before_min_only_blue":
        return [blue], 1
    return [blue, strong, red], 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--v2-db", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--scenario", default="default", choices=["default", "after_min_first_blue_then_strong", "only_blue_after_min", "before_min_only_blue"])
    args = p.parse_args()

    candidates, published_today = _sample_candidates(args.scenario)
    candidates = candidates[: args.limit]
    result = dry_run_publish(candidates, published_today=published_today, helper_cta_enabled=True)

    status = "OK" if (result.get("post_built") or result.get("send_status") == "skipped_no_candidate") else "FAIL"
    print(f"V3_PUBLISHER_DRY_RUN_STATUS={status}")
    print(f"items_seen={len(candidates)}")
    print(f"candidates_seen={result.get('fallback_candidates_seen', 0)}")
    for k in ["daily_min_target", "published_today", "after_daily_min", "fallback_candidates_seen", "fallback_candidates_skipped_low_value", "fallback_publishable_candidates", "selected_candidate_id", "selection_reason", "send_status", "post_built", "read_more_needed", "read_more_button_present", "source_link_present", "max_send_method", "max_message_id", "send_attempt_planned", "published_message_planned", "helper_cta_planned", "helper_cta_send_status", "fullarticle_callback_payload", "fullarticle_payload_valid"]:
        print(f"{k}={result.get(k)}")
    print(f"max_mock_send={'true' if result.get('max_mock_send') else 'false'}")
    print("db_update_planned=false")
    print("production_mutation=false")
    media = result.get("media_plan", {})
    print(f"image_present={str(bool(media.get('image_present'))).lower()}")
    print(f"image_source={media.get('image_source')}")
    print(f"placeholder_category={media.get('placeholder_category')}")
    print("image_attach_attempted=false")
    print("image_required=false")
    print(f"image_fallback_reason={media.get('fallback_reason') or ""}")
    print("external_url_button_forbidden=true")
    print("recommended_next_steps=keep dry-run; enable real send only after explicit cutover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
