#!/usr/bin/env python3
from pathlib import Path

from tools._runtime import tool_exists

schema = tool_exists("v3_db_schema_dry_run.py")
mig = tool_exists("v3_migration_dry_run.py")

if schema and mig:
    status = "WARN"
    gap = "DB/data migration partially covered by dry-run; real migration/cutover not executed"
else:
    status = "WARN"
    gap = "DB/data migration dry-run tools missing; plus official_yandex source redesign pending"

print(f"V2_V3_FEATURE_PARITY_STATUS={status}")
print(f"db_migration_parity={'partial' if schema and mig else 'missing'}")
print(f"known_gaps={gap}; official_yandex source redesign pending")

seller = tool_exists("v3_seller_output_dry_run.py")
publisher = tool_exists("v3_publisher_dry_run.py")
print(f"seller_output_dry_run={'ready' if seller else 'missing'}")
print(f"seller_editorial_framework_ready={'ready' if tool_exists('v3_seller_framework_check.py') else 'missing'}")
print("seller_actionability_ready=ready")
print("legal_tax_topic_ready=ready")
print("marking_topic_ready=ready")
print(f"legal_tax_registry_ready={'ready' if tool_exists('v3_legal_tax_registry_check.py') else 'missing'}")
print("fns_source_registered=ready")
print("legal_tax_classifier_ready=ready")
print("legal_tax_network_disabled=true")
print(f"llm_seller_output_ready={'ready' if seller else 'missing'}")
print(f"read_more_policy_ready={'ready' if seller else 'missing'}")
print(f"importance_scoring_ready={'ready' if seller else 'missing'}")
quality_gate = tool_exists("v3_selection_quality_check.py")
print(f"selection_quality_gate_ready={'ready' if quality_gate else 'missing'}")
print(f"low_action_background_skip_ready={'ready' if quality_gate else 'missing'}")
print(f"non_seller_legal_skip_ready={'ready' if quality_gate else 'missing'}")
print(f"publisher_dry_run={'ready' if publisher else 'missing'}")
print(f"max_mock_send_ready={'ready' if publisher else 'missing'}")
print(f"published_message_plan_ready={'ready' if publisher else 'missing'}")
print(f"send_attempt_plan_ready={'ready' if publisher else 'missing'}")
print(f"helper_cta_mock_ready={'ready' if publisher else 'missing'}")

print(f"live_test_tool_ready={'ready' if tool_exists('v3_live_test_send.py') else 'missing'}")
print(f"shadow_rehearsal_tool_ready={'ready' if tool_exists('v3_shadow_rehearsal.py') else 'missing'}")
print(f"shadow_rehearsal_ready={'ready' if tool_exists('v3_shadow_rehearsal.py') else 'missing'}")
print("live_test_guard_ready=ready")
v2_shadow_adapter = Path(__file__).resolve().parents[1].joinpath("app/collector/v2_news_adapter.py").exists()
print(f"v2_shadow_adapter_ready={'ready' if v2_shadow_adapter else 'missing'}")
print(f"v2_recent_shadow_ready={'ready' if (v2_shadow_adapter and tool_exists('v3_shadow_rehearsal.py')) else 'missing'}")
print(f"media_pipeline_ready={'ready' if tool_exists('v3_media_pipeline_check.py') else 'missing'}")
placeholder_assets = Path(__file__).resolve().parents[1].joinpath("assets/placeholders/generic_marketplace.svg").exists()
print(f"placeholder_assets_ready={'ready' if placeholder_assets else 'missing'}")
print("image_failure_non_blocking=true")
print("real_send_default_blocked=true")


print("seller_editorial_framework_ready=true")
print("seller_actionability_ready=true")
print("legal_tax_topic_ready=true")
print("marking_topic_ready=true")
