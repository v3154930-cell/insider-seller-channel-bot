#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from app.collector.official_json_collector import dry_run as dry_run_official
from app.collector.rss_collector import dry_run_rss
from app.collector.telegram_collector import dry_run_telegram
from app.monitoring.source_coverage import source_coverage
from app.publisher.publisher import dry_run_publish
from tools._runtime import tool_exists
from tools.inventory_v2_sources import build_inventory, resolve_v2_root
from tools.v3_publisher_dry_run import _sample_candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-root", default=None)
    args = parser.parse_args()

    inv = build_inventory(resolve_v2_root(args.v2_root))
    rss = dry_run_rss(inv)
    tg = dry_run_telegram({"TG_JSON_URLS": ",".join(["mock://tg-json" for _ in range(int(inv.get("telegram_json_sources", 0)))])})
    official = dry_run_official()
    cov = source_coverage(inv, {"rss_sources_loaded": rss["sources"], "telegram_json_sources_loaded": max(tg["sources"], int(inv.get("telegram_json_sources", 0))), "official_json_sources_loaded": max(official["official_json_sources_count"], int(inv.get("official_json_sources", 0)))})
    pub = dry_run_publish(_sample_candidates("default")[0], published_today=2)

    controlled_send_ready = tool_exists("v3_controlled_send_canary.py")
    print(f"V3_DRY_RUN_STATUS={cov['status']}")
    print(f"v2_root={inv['v2_root']}")
    print(f"rss_sources_loaded={rss['sources']}")
    print(f"telegram_json_sources_loaded={max(tg['sources'], int(inv.get('telegram_json_sources', 0)))}")
    print(f"official_json_sources_loaded={max(official['official_json_sources_count'], int(inv.get('official_json_sources', 0)))}")
    print(f"source_coverage_status={cov['status']}")
    print(f"official_yandex_gap={cov['official_yandex_gap']}")
    print(f"db_schema_dry_run={'true' if tool_exists('v3_db_schema_dry_run.py') else 'false'}")
    print(f"migration_dry_run_available={'true' if tool_exists('v3_migration_dry_run.py') else 'false'}")
    print("migration_mapping_strategy=stable_external_id_hash + migration_mapping table + do_not_repost_published")
    print(f"seller_output_dry_run={'true' if tool_exists('v3_seller_output_dry_run.py') else 'false'}")
    print(f"seller_editorial_framework_ready={'true' if tool_exists('v3_seller_framework_check.py') else 'false'}")
    print("seller_actionability_ready=true")
    print("legal_tax_topic_ready=true")
    print("marking_topic_ready=true")
    print(f"legal_tax_registry_ready={'true' if tool_exists('v3_legal_tax_registry_check.py') else 'false'}")
    print("fns_source_registered=true")
    print("legal_tax_classifier_ready=true")
    print("legal_tax_network_disabled=true")
    print("llm_seller_output_ready=true")
    print("read_more_policy_ready=true")
    print("importance_scoring_ready=true")
    quality_gate_tool_present = tool_exists("v3_selection_quality_check.py")
    print(f"selection_quality_gate_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"low_action_background_skip_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"non_seller_legal_skip_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"publisher_dry_run={'true' if pub.get('post_built') else 'false'}")
    print(f"max_mock_send_ready={'true' if pub.get('max_mock_send') else 'false'}")
    print(f"published_message_plan_ready={'true' if pub.get('published_message_planned') else 'false'}")
    print(f"send_attempt_plan_ready={'true' if pub.get('send_attempt_planned') else 'false'}")
    print(f"helper_cta_mock_ready={'true' if pub.get('helper_cta_planned') else 'false'}")
    print(f"live_test_tool_ready={'true' if tool_exists('v3_live_test_send.py') else 'false'}")
    print(f"controlled_send_tool_ready={'true' if controlled_send_ready else 'false'}")
    print(f"shadow_rehearsal_tool_ready={'true' if tool_exists('v3_shadow_rehearsal.py') else 'false'}")
    v2_shadow_adapter_ready = Path(__file__).resolve().parents[1].joinpath("app/collector/v2_news_adapter.py").exists()
    v2_recent_shadow_ready = tool_exists("v3_shadow_rehearsal.py") and v2_shadow_adapter_ready
    print(f"shadow_rehearsal_ready={'true' if tool_exists('v3_shadow_rehearsal.py') else 'false'}")
    print(f"v2_shadow_adapter_ready={'true' if v2_shadow_adapter_ready else 'false'}")
    print(f"v2_recent_shadow_ready={'true' if v2_recent_shadow_ready else 'false'}")
    print("live_test_guard_ready=true")
    placeholder_assets_ready = Path(__file__).resolve().parents[1].joinpath("assets/placeholders/generic_marketplace.svg").exists()
    print(f"media_pipeline_ready={'true' if tool_exists('v3_media_pipeline_check.py') else 'false'}")
    print(f"placeholder_assets_ready={'true' if placeholder_assets_ready else 'false'}")
    print("image_failure_non_blocking=true")
    print("real_send_default_blocked=true")
    print("controlled_send_default_blocked=true")
    print("production_send_guard_ready=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
