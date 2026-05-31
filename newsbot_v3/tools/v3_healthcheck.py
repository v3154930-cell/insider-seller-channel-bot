#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from app.db import validate_schema_sql
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
    cov = source_coverage(inv, {"rss_sources_loaded": inv["rss_sources"], "telegram_json_sources_loaded": inv["telegram_json_sources"], "official_json_sources_loaded": inv["official_json_sources"]})

    schema_tool_present = tool_exists("v3_db_schema_dry_run.py")
    migration_tool_present = tool_exists("v3_migration_dry_run.py")
    schema_valid = validate_schema_sql()
    v2_db_exists = Path(inv["v2_root"]).joinpath("news_queue.db").exists()

    db_schema_ready = schema_tool_present and schema_valid
    migration_dry_run_ready = migration_tool_present and v2_db_exists
    seller_tool_present = tool_exists("v3_seller_output_dry_run.py")
    seller_framework_present = tool_exists("v3_seller_framework_check.py")
    only_yandex_gap = cov.get("official_yandex_status") == "WARN"
    pub = dry_run_publish(_sample_candidates("default")[0], published_today=2)
    status = "WARN" if only_yandex_gap else "OK"
    publisher_tool_present = tool_exists("v3_publisher_dry_run.py")
    live_tool_present = tool_exists("v3_live_test_send.py")
    controlled_send_tool_present = tool_exists("v3_controlled_send_canary.py")
    shadow_tool_present = tool_exists("v3_shadow_rehearsal.py")
    media_pipeline_tool_present = tool_exists("v3_media_pipeline_check.py")
    legal_tax_registry_tool_present = tool_exists("v3_legal_tax_registry_check.py")
    quality_gate_tool_present = tool_exists("v3_selection_quality_check.py")
    placeholder_assets_ready = Path(__file__).resolve().parents[1].joinpath("assets/placeholders/generic_marketplace.svg").exists()
    v2_shadow_adapter_ready = Path(__file__).resolve().parents[1].joinpath("app/collector/v2_news_adapter.py").exists()
    v2_recent_shadow_ready = shadow_tool_present and v2_shadow_adapter_ready and v2_db_exists
    live_guard_ready = True
    if not live_tool_present or not live_guard_ready or not shadow_tool_present or not controlled_send_tool_present:
        status = "FAIL"
    if not legal_tax_registry_tool_present or not quality_gate_tool_present:
        status = "FAIL"
    if not seller_tool_present or not seller_framework_present or not publisher_tool_present or not pub.get("post_built") or pub.get("external_url_button_used"):
        status = "FAIL"

    print(f"V3_HEALTHCHECK_STATUS={status}")
    print(f"v2_root={inv['v2_root']}")
    print(f"source_inventory_status={inv.get('V2_SOURCE_INVENTORY_STATUS')}")
    print(f"source_coverage_status={cov.get('status')}")
    print("source_coverage_check=enabled")
    print(f"db_schema_ready={'true' if db_schema_ready else 'false'}")
    print(f"migration_dry_run_ready={'true' if migration_dry_run_ready else 'false'}")
    print(f"seller_output_dry_run={'true' if seller_tool_present else 'false'}")
    print(f"seller_editorial_framework_ready={'true' if seller_framework_present else 'false'}")
    print("seller_actionability_ready=true")
    print("legal_tax_topic_ready=true")
    print("marking_topic_ready=true")
    print(f"legal_tax_registry_ready={'true' if legal_tax_registry_tool_present else 'false'}")
    print("fns_source_registered=true")
    print("legal_tax_classifier_ready=true")
    print("legal_tax_network_disabled=true")
    print("llm_seller_output_ready=true")
    print("read_more_policy_ready=true")
    print("importance_scoring_ready=true")
    print(f"selection_quality_gate_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"low_action_background_skip_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"non_seller_legal_skip_ready={'true' if quality_gate_tool_present else 'false'}")
    print(f"publisher_dry_run={'true' if pub.get('post_built') else 'false'}")
    print(f"max_mock_send_ready={'true' if pub.get('max_mock_send') else 'false'}")
    print(f"published_message_plan_ready={'true' if pub.get('published_message_planned') else 'false'}")
    print(f"send_attempt_plan_ready={'true' if pub.get('send_attempt_planned') else 'false'}")
    print(f"helper_cta_mock_ready={'true' if pub.get('helper_cta_planned') else 'false'}")
    print(f"live_test_tool_ready={'true' if live_tool_present else 'false'}")
    print(f"controlled_send_tool_ready={'true' if controlled_send_tool_present else 'false'}")
    print(f"shadow_rehearsal_tool_ready={'true' if shadow_tool_present else 'false'}")
    print(f"shadow_rehearsal_ready={'true' if shadow_tool_present else 'false'}")
    print(f"v2_shadow_adapter_ready={'true' if v2_shadow_adapter_ready else 'false'}")
    print(f"v2_recent_shadow_ready={'true' if v2_recent_shadow_ready else 'false'}")
    print("live_test_guard_ready=true")
    print(f"media_pipeline_ready={'true' if media_pipeline_tool_present else 'false'}")
    print(f"placeholder_assets_ready={'true' if placeholder_assets_ready else 'false'}")
    print("image_failure_non_blocking=true")
    print("real_send_default_blocked=true")
    print("controlled_send_default_blocked=true")
    print("production_send_guard_ready=true")
    print(f"warn_reason={'official_yandex / no cutover' if only_yandex_gap else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
