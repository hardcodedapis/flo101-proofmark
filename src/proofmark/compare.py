from __future__ import annotations

from typing import Any

from .actions import recommend_for_artifact
from .learning_loop import build_learning_loop
from .schema import InputError, _clean_text
from .schema import validate_payload
from .workflow import evaluate_artifact


def _dimension_lookup(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in result.get("rubric", []) if isinstance(item, dict)}


def compare_revisions(payload: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")

    before_artifact = _clean_text(payload.get("before_artifact") or payload.get("artifact"))
    after_artifact = _clean_text(payload.get("after_artifact"))
    if not before_artifact:
        raise InputError("empty_before_artifact", "Paste the first artifact before comparing revisions.")
    if not after_artifact:
        raise InputError("empty_after_artifact", "Paste the revised artifact before comparing revisions.")
    if before_artifact == after_artifact:
        raise InputError("unchanged_revision", "The revised artifact is identical to the original artifact.")

    shared = {
        "artifact_type": payload.get("artifact_type") or "brief",
        "learner_goal": payload.get("learner_goal"),
        "level": payload.get("level") or "intermediate",
        "output_goal": payload.get("output_goal"),
        "custom_rubric": payload.get("custom_rubric") or [],
        "learner_id": payload.get("learner_id") or "anonymous-learner",
        "prior_mastery": payload.get("prior_mastery", 0.35),
        "days_since_last_review": payload.get("days_since_last_review", 0.0),
        "target_retention": payload.get("target_retention", 0.85),
    }
    before = evaluate_artifact({**shared, "artifact": before_artifact}, provider=provider)
    after = evaluate_artifact({**shared, "artifact": after_artifact}, provider=provider)

    before_by_name = _dimension_lookup(before)
    after_by_name = _dimension_lookup(after)
    dimension_deltas = []
    for name, after_item in after_by_name.items():
        before_item = before_by_name.get(name, {})
        before_score = int(before_item.get("score", 0))
        after_score = int(after_item.get("score", 0))
        delta = after_score - before_score
        dimension_deltas.append(
            {
                "name": name,
                "before_score": before_score,
                "after_score": after_score,
                "delta": delta,
                "status": "improved" if delta > 0 else "regressed" if delta < 0 else "unchanged",
                "current_evidence": after_item.get("evidence", ""),
                "remaining_risk": after_item.get("risk_if_ignored", ""),
            }
        )

    score_delta = int(after["overall_score"]) - int(before["overall_score"])
    improved = [item["name"] for item in dimension_deltas if item["delta"] > 0]
    regressed = [item["name"] for item in dimension_deltas if item["delta"] < 0]
    unchanged_weak = [
        item["name"]
        for item in dimension_deltas
        if item["delta"] == 0 and item["after_score"] <= 3
    ]

    if score_delta >= 15 and not regressed:
        recommendation = "Revision shows meaningful proof improvement."
    elif score_delta > 0:
        recommendation = "Revision improved, but still needs targeted proof before submission."
    elif score_delta == 0:
        recommendation = "Revision did not materially change the proof-of-work signal."
    else:
        recommendation = "Revision regressed the proof-of-work signal and should be reworked."

    next_focus = unchanged_weak[:2] or regressed[:2] or after.get("missing_gaps", [])[:2]
    response = {
        "before": before,
        "after": after,
        "score_delta": score_delta,
        "dimension_deltas": dimension_deltas,
        "improved_dimensions": improved,
        "regressed_dimensions": regressed,
        "unchanged_weak_dimensions": unchanged_weak,
        "recommendation": recommendation,
        "proof_improvement_summary": {
            "before_score": before["overall_score"],
            "after_score": after["overall_score"],
            "delta": score_delta,
            "next_review_focus": next_focus,
        },
    }
    after_request = validate_payload({**shared, "artifact": after_artifact})
    response["learning_loop"] = build_learning_loop(after_request, after, response)
    response["after"]["learning_loop"] = response["learning_loop"]
    response["after"]["next_learning_action"] = recommend_for_artifact(after_request, response["after"])
    response["next_learning_action"] = response["after"]["next_learning_action"]
    return response
