from __future__ import annotations

from datetime import datetime
from typing import Any

from app.publisher.native_ad_filter import detect_native_ad_leadgen_reason
from app.publisher.quality_gate import evaluate_selection_quality_gate


def daily_min_target(now: datetime) -> int:
    return 3 if now.weekday() >= 5 else 10


def _is_strong_yellow(candidate: dict[str, Any]) -> bool:
    return candidate.get("importance") == "🟡" and float(candidate.get("score", 0)) >= 0.7


def _is_relevance_actionable(candidate: dict[str, Any]) -> bool:
    return int(candidate.get("seller_relevance_score", 0)) >= 2 and int(candidate.get("actionability_score", 0)) >= 2


def _pick_strongest(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    if not candidates:
        return None, "no_candidate"
    red = [c for c in candidates if c.get("importance") == "🔴"]
    if red:
        return max(red, key=lambda x: float(x.get("score", 0))), "red_priority"
    yellow = [c for c in candidates if _is_strong_yellow(c)]
    if yellow:
        return max(yellow, key=lambda x: float(x.get("score", 0))), "strong_yellow_priority"
    rel = [c for c in candidates if _is_relevance_actionable(c)]
    if rel:
        return max(rel, key=lambda x: float(x.get("score", 0))), "relevance_actionability_priority"
    return max(candidates, key=lambda x: float(x.get("score", 0))), "best_available_fallback"


def _ranked_candidates(candidates: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    ranked: list[tuple[dict[str, Any], str]] = []
    seen: set[int] = set()

    def add(items: list[dict[str, Any]], reason: str) -> None:
        for item in sorted(items, key=lambda x: float(x.get("score", 0)), reverse=True):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            ranked.append((item, reason))

    add([c for c in candidates if c.get("importance") == "🔴"], "red_priority")
    add([c for c in candidates if _is_strong_yellow(c)], "strong_yellow_priority")
    add([c for c in candidates if _is_relevance_actionable(c)], "relevance_actionability_priority")
    add(candidates, "best_available_fallback")
    return ranked


def _pick_gate_passing(candidates: list[dict[str, Any]], after_min: bool) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    first_failed: tuple[str, dict[str, Any]] | None = None
    for candidate, reason in _ranked_candidates(candidates):
        gate_diag = evaluate_selection_quality_gate(candidate, after_daily_min=after_min)
        if gate_diag.get("selection_quality_gate_status") != "skipped":
            return candidate, reason, gate_diag
        if first_failed is None:
            first_failed = (reason, gate_diag)
    return None, "skipped_low_action_background", (first_failed[1] if first_failed else evaluate_selection_quality_gate(None, after_daily_min=after_min))


def dry_run_selection(candidates: list[dict[str, Any]], published_today: int) -> dict[str, Any]:
    now = datetime.utcnow()
    target = daily_min_target(now)
    after_min = published_today >= target

    native_ad_blocked = 0
    candidate_gate_reasons: dict[str, str] = {}
    filtered_candidates: list[dict[str, Any]] = []
    for c in candidates:
        item = c.get("item")
        item_text = str(getattr(item, "text", "") or "")
        reason = detect_native_ad_leadgen_reason(str(c.get("title") or ""), item_text)
        if reason:
            native_ad_blocked += 1
            if c.get("id"):
                candidate_gate_reasons[str(c.get("id"))] = reason
            continue
        filtered_candidates.append(c)

    direct = [c for c in filtered_candidates if c.get("direct_publish", True)]
    if not direct:
        direct = filtered_candidates

    weak = [c for c in direct if c.get("importance") == "🔵"]
    fallback_pool = [c for c in direct if not (after_min and c.get("importance") == "🔵")]

    if after_min and not fallback_pool and weak:
        selected, reason = None, "skipped_low_value_after_min"
        gate_diag = evaluate_selection_quality_gate(None, after_daily_min=after_min)
    else:
        selected, reason, gate_diag = _pick_gate_passing(fallback_pool if fallback_pool else direct, after_min)

    if not selected and native_ad_blocked > 0 and not filtered_candidates:
        reason = "skipped_native_ad_leadgen"
        gate_diag = evaluate_selection_quality_gate(None, after_daily_min=after_min)

    return {
        "publisher_dry_run": True,
        "time_window_open": 6 <= now.hour <= 23,
        "daily_min_target": target,
        "published_today": published_today,
        "after_daily_min": after_min,
        "selection_reason": reason,
        "fallback_candidates_seen": len(candidates),
        "native_ad_leadgen_blocked": native_ad_blocked,
        "candidate_gate_reasons": candidate_gate_reasons,
        "fallback_candidates_skipped_low_value": len(weak) if after_min else 0,
        "fallback_publishable_candidates": len(fallback_pool),
        "selected_candidate_id": selected.get("id") if selected else None,
        "selected_candidate_score": selected.get("score") if selected else None,
        "selected_importance": selected.get("importance") if selected else None,
        "selection_status": "selected" if selected else "no_candidate",
        **gate_diag,
    }
