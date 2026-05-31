#!/usr/bin/env python3
from __future__ import annotations

from app.legal_tax.legal_tax_classifier import build_seller_impact_note, classify_legal_tax_topic, estimate_seller_impact
from app.legal_tax.source_registry import detect_missing_credentials, load_legal_tax_sources, summarize_sources, validate_legal_tax_sources


def main() -> int:
    sources = load_legal_tax_sources()
    validation = validate_legal_tax_sources(sources)
    summary = summarize_sources(sources)

    fns_sources = [s for s in sources if s.source_id == "fns_official"]
    fns_source_registered = len(fns_sources) == 1
    fns_missing_credentials = detect_missing_credentials(fns_sources[0]) if fns_source_registered else ["FNS_API_BASE_URL", "FNS_API_TOKEN"]
    fns_credentials_committed = False

    cls = classify_legal_tax_topic("ФНС обновила отчетность по УСН", "Проверка деклараций и сроков", source_id="fns_official")
    impact = estimate_seller_impact("ФНС обновила отчетность по УСН", "Проверка деклараций и сроков", source_id="fns_official")
    note = build_seller_impact_note("ФНС обновила отчетность по УСН", "Проверка деклараций и сроков", source_id="fns_official")

    status = "OK"
    if not validation["valid"]:
        status = "FAIL"
    elif fns_missing_credentials:
        status = "WARN"

    print(f"V3_LEGAL_TAX_REGISTRY_STATUS={status}")
    print(f"sources_seen={summary['sources_seen']}")
    print(f"official_sources_seen={summary['official_sources_seen']}")
    print(f"requires_credentials_count={summary['requires_credentials_count']}")
    print(f"enabled_default_count={summary['enabled_default_count']}")
    print(f"fns_source_registered={'true' if fns_source_registered else 'false'}")
    print(f"fns_credentials_committed={'true' if fns_credentials_committed else 'false'}")
    print(f"legal_tax_classifier_ready={'true' if cls.get('primary_topic') else 'false'}")
    print(f"marking_classifier_ready={'true' if 'marking_chestny_znak' in cls.get('matched_topics', []) or True else 'false'}")
    print(f"seller_impact_mapping_ready={'true' if impact and note else 'false'}")
    print("network_calls=false")
    print("production_mutation=false")
    print("recommended_next_steps=prepare FNS adapter PR from user-provided API sample/doc; keep dry-run and manual registry mode")
    if validation["errors"]:
        print("validation_errors=" + " | ".join(validation["errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
