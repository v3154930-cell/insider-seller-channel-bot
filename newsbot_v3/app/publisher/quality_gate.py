from __future__ import annotations

from typing import Any

LOW_VALUE_TOPIC_TAGS = {"low_value_background", "corporate_pr", "generic_non_seller_legal"}
STRONG_RELEVANCE_THRESHOLD = 3
STRONG_ACTIONABILITY_THRESHOLD = 3
MIN_ACCEPTABLE_RELEVANCE_BEFORE_MIN = 2
MIN_ACCEPTABLE_ACTIONABILITY_BEFORE_MIN = 2


def _normalize_topic_tags(candidate: dict[str, Any]) -> list[str]:
    tags = candidate.get("topic_tags") or []
    if isinstance(tags, str):
        return [x.strip() for x in tags.split(",") if x.strip()]
    if isinstance(tags, list):
        return [str(x).strip() for x in tags if str(x).strip()]
    return []


def _is_direct_action(candidate: dict[str, Any]) -> bool:
    value = candidate.get("direct_action")
    if value is None:
        value = candidate.get("direct_publish")
    if value is None:
        return False
    return bool(value)


def evaluate_selection_quality_gate(candidate: dict[str, Any] | None, after_daily_min: bool) -> dict[str, Any]:
    if not candidate:
        return {
            "selection_quality_gate_applied": True,
            "selection_quality_gate_status": "skipped",
            "selection_quality_gate_reason": "no_candidate",
            "candidate_seller_relevance_score": 0,
            "candidate_actionability_score": 0,
            "candidate_topic_tags": "",
            "candidate_direct_action_status": "none",
        }

    seller_relevance = int(candidate.get("seller_relevance_score", 0) or 0)
    actionability = int(candidate.get("actionability_score", 0) or 0)
    topic_tags = _normalize_topic_tags(candidate)
    topic_tags_set = set(topic_tags)
    direct_action = _is_direct_action(candidate)

    low_value_tagged = bool(topic_tags_set & LOW_VALUE_TOPIC_TAGS)
    strong_enough = seller_relevance >= STRONG_RELEVANCE_THRESHOLD and actionability >= STRONG_ACTIONABILITY_THRESHOLD
    acceptable_before_min = seller_relevance >= MIN_ACCEPTABLE_RELEVANCE_BEFORE_MIN and actionability >= MIN_ACCEPTABLE_ACTIONABILITY_BEFORE_MIN

    gate_status = "passed"
    gate_reason = "passed"

    if low_value_tagged and not strong_enough:
        gate_status = "skipped"
        gate_reason = "low_value_background_topic"
    elif after_daily_min and (not direct_action) and (seller_relevance < STRONG_RELEVANCE_THRESHOLD or actionability < STRONG_ACTIONABILITY_THRESHOLD):
        gate_status = "skipped"
        gate_reason = "after_min_no_direct_action_low_scores"
    elif (not after_daily_min) and (not direct_action) and (not acceptable_before_min):
        gate_status = "skipped"
        gate_reason = "before_min_low_relevance_threshold"

    return {
        "selection_quality_gate_applied": True,
        "selection_quality_gate_status": gate_status,
        "selection_quality_gate_reason": gate_reason,
        "candidate_seller_relevance_score": seller_relevance,
        "candidate_actionability_score": actionability,
        "candidate_topic_tags": ",".join(topic_tags),
        "candidate_direct_action_status": "direct_action" if direct_action else "no_direct_action",
    }
