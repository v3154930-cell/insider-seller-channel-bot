#!/usr/bin/env python3
from __future__ import annotations

from app.models import NewsItem
from app.publisher.candidate_normalizer import is_v2_row_already_published
from app.publisher.selection_policy import dry_run_selection
from tools.v3_controlled_send_canary import _is_v2_publish_candidate


def _candidate(cid: str, title: str, importance: str, score: float, rel: int, act: int, direct: bool, tags: list[str]) -> dict:
    return {
        "id": cid,
        "importance": importance,
        "score": score,
        "seller_relevance_score": rel,
        "actionability_score": act,
        "direct_action": direct,
        "topic_tags": tags,
        "item": NewsItem(cid, title, title + " text", "https://example.com/" + cid, "fixture"),
    }


def main() -> int:
    fixtures = [
        ("wb_commission", _candidate("1", "WB commission change", "🔴", 0.95, 3, 3, True, ["marketplace_rules"]), True),
        ("ozon_logistics", _candidate("2", "Ozon logistics/returns", "🔴", 0.93, 3, 3, True, ["marketplace_rules"]), True),
        ("marking_deadline", _candidate("3", "Честный знак deadline", "🔴", 0.92, 3, 3, True, ["marking", "deadline"]), True),
        ("tax_obligation", _candidate("4", "Tax/FNS seller obligation", "🟡", 0.8, 3, 2, True, ["tax", "documents"]), True),
        ("payout_delay", _candidate("5", "Marketplace payout delay", "🔴", 0.88, 3, 2, True, ["marketplace", "sellers"]), True),
        ("corporate_stake", _candidate("6", "Corporate stake deal", "🟡", 0.76, 1, 1, False, ["corporate_pr"]), False),
        ("deviantart_fine", _candidate("7", "DeviantArt fine", "🟡", 0.74, 1, 1, False, ["generic_non_seller_legal"]), False),
        ("generic_pr", _candidate("8", "Generic interview", "🟡", 0.7, 1, 1, False, ["low_value_background"]), False),
    ]

    seen = len(fixtures)
    passed = 0
    low_action_background_skipped = True
    non_seller_legal_skipped = True
    seller_direct_action_selected = True
    no_fake_best_available_fallback = True

    for name, cand, should_select in fixtures:
        res = dry_run_selection([cand], published_today=10)
        selected = bool(res.get("selected_candidate_id"))
        if selected == should_select:
            passed += 1
        if name in {"corporate_stake", "generic_pr", "deviantart_fine"}:
            low_action_background_skipped = low_action_background_skipped and (not selected) and res.get("selection_reason") == "skipped_low_action_background"
        if name == "deviantart_fine":
            non_seller_legal_skipped = non_seller_legal_skipped and (not selected)
        if should_select and cand.get("direct_action"):
            seller_direct_action_selected = seller_direct_action_selected and selected
        if not should_select:
            no_fake_best_available_fallback = no_fake_best_available_fallback and res.get("selection_reason") != "best_available_fallback"

    status = "OK" if passed == seen else "FAIL"
    print(f"V3_SELECTION_QUALITY_STATUS={status}")
    print(f"fixtures_seen={seen}")
    print(f"fixtures_passed={passed}")
    print(f"low_action_background_skipped={'true' if low_action_background_skipped else 'false'}")
    print(f"non_seller_legal_skipped={'true' if non_seller_legal_skipped else 'false'}")
    print(f"seller_direct_action_selected={'true' if seller_direct_action_selected else 'false'}")
    print(f"no_fake_best_available_fallback={'true' if no_fake_best_available_fallback else 'false'}")
    regression_v2_published = {
        "id": "v2-89245",
        "v2_news_id": "89245",
        "title": "Shopper’s: продавцы Wildberries пожаловались в ФАС...",
        "text": "fixture",
        "is_published": 1,
        "max_message_id": "mid.ffffbd75e1d55258019e64e843636590",
        "seller_relevance_score": 4,
        "actionability_score": 4,
    }
    published_fixture_skipped = is_v2_row_already_published(regression_v2_published)
    print(f"fixture_89245_selection_reason={'skipped_already_published_v2' if published_fixture_skipped else 'unexpected_not_skipped'}")
    print(f"fixture_89245_selected={'false' if published_fixture_skipped else 'true'}")
    controlled_canary_v2_fixtures = [
        ("89294", {"seller_decision": "digest", "seller_relevance_score": 1, "actionability_score": 1, "link": "https://example.com/89294", "is_published": 0, "max_message_id": ""}, False),
        ("89380", {"seller_decision": "digest", "seller_relevance_score": 2, "actionability_score": 2, "link": "https://example.com/89380", "is_published": 0, "max_message_id": ""}, False),
        ("89460", {"seller_decision": "digest", "seller_relevance_score": 1, "actionability_score": 1, "link": "https://example.com/89460", "is_published": 0, "max_message_id": ""}, False),
        ("89245", {"seller_decision": "publish", "seller_relevance_score": 4, "actionability_score": 4, "link": "https://example.com/89245", "is_published": 1, "max_message_id": "mid.exists"}, False),
        ("good_publish", {"seller_decision": "publish", "seller_relevance_score": 4, "actionability_score": 4, "link": "https://example.com/good", "is_published": 0, "max_message_id": ""}, True),
    ]
    for fixture_id, row, expected in controlled_canary_v2_fixtures:
        actual = _is_v2_publish_candidate(row)
        print(f"controlled_canary_fixture_{fixture_id}={'pass' if actual == expected else 'fail'}")
    print("production_mutation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
