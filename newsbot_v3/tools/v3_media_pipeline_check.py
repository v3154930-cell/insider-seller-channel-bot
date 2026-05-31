#!/usr/bin/env python3
from __future__ import annotations

from app.models import NewsItem
from app.publisher.media import MediaPlan, resolve_image_for_post, validate_media_plan


def main() -> int:
    fixtures = [
        ("external", NewsItem("1", "External image", "text", "https://example.com", "src"), {"image_source": "external"}),
        ("wb_no_image", NewsItem("2", "WB commission update", "commission updated", "https://example.com", "WB"), {"placeholder_category_any": {"wb", "generic_marketplace"}}),
        ("legal_tax", NewsItem("3", "Налоговые изменения", "НДС и налог", "https://example.com", "gov"), {"placeholder_category": "legal_tax"}),
        ("marking", NewsItem("4", "Маркировка Честный знак", "маркировка", "https://example.com", "gov"), {"placeholder_category": "marking_chestny_znak"}),
        ("logistics", NewsItem("5", "Logistics update", "доставка и склад", "https://example.com", "log"), {"placeholder_category": "logistics"}),
        ("unknown", NewsItem("6", "Misc update", "neutral", "https://example.com", "misc"), {"placeholder_category": "generic_marketplace"}),
    ]

    setattr(fixtures[0][1], "image_url", "https://example.com/a.jpg")
    passed = 0
    external_ok = placeholder_ok = legal_ok = marking_ok = non_blocking = True
    for name, item, expected in fixtures:
        plan = resolve_image_for_post(item)
        valid, errs = validate_media_plan(plan)
        ok = valid and not errs
        if "image_source" in expected:
            ok = ok and plan.image_source == expected["image_source"]
            external_ok = external_ok and (plan.image_source == "external")
        if "placeholder_category" in expected:
            ok = ok and plan.placeholder_category == expected["placeholder_category"]
        if "placeholder_category_any" in expected:
            ok = ok and plan.placeholder_category in expected["placeholder_category_any"]
        if name in {"wb_no_image", "legal_tax", "marking", "logistics", "unknown"}:
            placeholder_ok = placeholder_ok and (plan.image_source in {"placeholder", "none"})
        if name == "legal_tax":
            legal_ok = legal_ok and plan.placeholder_category == "legal_tax"
        if name == "marking":
            marking_ok = marking_ok and plan.placeholder_category == "marking_chestny_znak"
        if ok:
            passed += 1

    missing = MediaPlan(False, "none", None, None, "generic_marketplace", False, False, "placeholder_missing", "{}")
    valid_missing, _ = validate_media_plan(missing)
    non_blocking = non_blocking and valid_missing and (missing.image_required is False)

    status = "OK" if passed == len(fixtures) and non_blocking else "FAIL"
    print(f"V3_MEDIA_PIPELINE_STATUS={status}")
    print(f"fixtures_seen={len(fixtures)+1}")
    print(f"fixtures_passed={passed + (1 if non_blocking else 0)}")
    print(f"external_image_ok={'true' if external_ok else 'false'}")
    print(f"placeholder_ok={'true' if placeholder_ok else 'false'}")
    print(f"legal_tax_placeholder_ok={'true' if legal_ok else 'false'}")
    print(f"marking_placeholder_ok={'true' if marking_ok else 'false'}")
    print(f"image_failure_non_blocking={'true' if non_blocking else 'false'}")
    print("production_mutation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
