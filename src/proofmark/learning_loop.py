from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .schema import EvaluationRequest


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _retention_probability(days_since_review: float, stability_days: float) -> float:
    stability = max(stability_days, 0.25)
    return 2 ** (-max(days_since_review, 0.0) / stability)


def _days_until_target(stability_days: float, target_retention: float) -> int:
    target = _clamp(target_retention, 0.55, 0.97)
    days = -max(stability_days, 0.25) * math.log(target, 2)
    return max(1, min(45, round(days)))


def _risk_label(retention: float, weakest_score: int, regressed: bool) -> str:
    if regressed or retention < 0.62 or weakest_score <= 2:
        return "high"
    if retention < 0.78 or weakest_score == 3:
        return "medium"
    return "low"


def _adaptive_task(focus_dimensions: list[str], retention_risk: str) -> str:
    focus = ", ".join(focus_dimensions[:2]) if focus_dimensions else "transfer to a new context"
    if retention_risk == "high":
        return f"Rebuild the artifact section for {focus} from scratch, then add one verification check."
    if retention_risk == "medium":
        return f"Revise the artifact by strengthening {focus} with concrete evidence and one tradeoff."
    return f"Apply the same skill to a slightly different scenario and preserve evidence for {focus}."


def build_learning_loop(
    request: EvaluationRequest,
    result: dict[str, Any],
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rubric = result.get("rubric", [])
    scores = [int(item.get("score", 1)) for item in rubric] or [1]
    weakest_score = min(scores)
    weakest_dimensions = [
        item.get("name", "unknown")
        for item in sorted(rubric, key=lambda rubric_item: rubric_item.get("score", 0))
    ][:2]
    confidence = result.get("reliability", {}).get("confidence", "medium")
    confidence_bonus = {"high": 0.24, "medium": 0.12, "low": -0.08}.get(confidence, 0.0)
    mastery = float(result.get("skill_ledger", {}).get("updated_mastery", request.prior_mastery))
    score_strength = int(result.get("overall_score", 0)) / 100

    score_delta = 0
    regressed = False
    improved_dimensions: list[str] = []
    if comparison:
        score_delta = int(comparison.get("score_delta", 0))
        regressed = bool(comparison.get("regressed_dimensions"))
        improved_dimensions = list(comparison.get("improved_dimensions", []))

    improvement_bonus = _clamp(score_delta / 100, -0.25, 0.28)
    stability_days = 1.2 + (mastery * 7.5) + (score_strength * 4.0) + (len(improved_dimensions) * 0.45)
    stability_days += confidence_bonus * 3.0 + improvement_bonus * 8.0
    if weakest_score <= 2:
        stability_days *= 0.58
    if regressed:
        stability_days *= 0.5
    stability_days = _clamp(stability_days, 0.5, 30.0)

    retention_now = _retention_probability(request.days_since_last_review, stability_days)
    retention_risk = _risk_label(retention_now, weakest_score, regressed)
    review_days = _days_until_target(stability_days, request.target_retention)
    if retention_risk == "high":
        review_days = min(review_days, 2)
    elif retention_risk == "medium":
        review_days = min(review_days, 5)

    now = datetime.now(timezone.utc)
    next_review_at = now + timedelta(days=review_days)
    focus_dimensions = weakest_dimensions
    why_now = (
        f"Predicted retention is {retention_now:.2f} after {request.days_since_last_review:g} days. "
        f"Weakest dimension score is {weakest_score}/5."
    )
    if comparison:
        why_now += f" Revision score delta is {score_delta:+d}."

    return {
        "model": "personalized_half_life_inspired_scheduler",
        "retention_risk": retention_risk,
        "target_retention": request.target_retention,
        "predicted_retention_now": round(retention_now, 3),
        "personalized_stability_days": round(stability_days, 2),
        "next_review_in_days": review_days,
        "next_review_at": next_review_at.date().isoformat(),
        "focus_dimensions": focus_dimensions,
        "adaptive_revision_task": _adaptive_task(focus_dimensions, retention_risk),
        "why_now": why_now,
        "next_rubric_adjustment": (
            "Require transfer to a new context."
            if retention_risk == "low"
            else f"Require explicit evidence for {', '.join(focus_dimensions)}."
        ),
        "state_update": {
            "previous_mastery": round(request.prior_mastery, 3),
            "updated_mastery": round(mastery, 3),
            "score_delta": score_delta,
            "regressed": regressed,
            "improved_dimensions": improved_dimensions,
        },
        "research_basis": [
            "Ebbinghaus-style exponential forgetting",
            "Duolingo half-life regression",
            "FSRS stability/retrievability intuition",
            "Bayesian knowledge tracing mastery update",
        ],
    }

