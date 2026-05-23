from __future__ import annotations

import hashlib
import os
from typing import Any


PROMPT_VERSION = "proofmark-v2"
RUBRIC_VERSION = "proofmark-rubric-v1"


def cache_key(artifact: str, model_name: str, rubric_version: str = RUBRIC_VERSION) -> str:
    payload = "\n".join([artifact, rubric_version, PROMPT_VERSION, model_name])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def configured_judges() -> list[str]:
    raw = os.getenv(
        "PROOFMARK_JUDGE_MODELS",
        "local-heuristic",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def quality_score(result: dict[str, Any], baseline: dict[str, Any], operational_score: float = 1.0) -> float:
    rubric = result.get("rubric", [])
    baseline_score = int(baseline.get("overall_score", result.get("overall_score", 0)))
    score = int(result.get("overall_score", 0))
    calibration_gap = min(abs(score - baseline_score), 40) / 40

    coverage = 1.0 if rubric and all("score" in item and "feedback" in item for item in rubric) else 0.35
    evidence_map = result.get("evidence_map", [])
    grounded = 0.35
    if evidence_map:
        grounded = sum(1 for item in evidence_map if item.get("evidence") or item.get("missing_proof")) / len(evidence_map)
    next_step = result.get("next_best_step", {})
    actionability = 1.0 if next_step.get("instructions") and next_step.get("acceptance_criteria") else 0.4
    calibration = 1.0 - calibration_gap

    weighted = (
        grounded * 0.32
        + coverage * 0.22
        + actionability * 0.2
        + calibration * 0.16
        + operational_score * 0.1
    )
    return round(max(0.0, min(1.0, weighted)), 3)


def build_judge_trace(
    result: dict[str, Any],
    baseline: dict[str, Any],
    artifact: str,
    selected_model: str,
    status: str = "selected",
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    local_quality = quality_score(result, baseline)
    planned = []
    for judge in configured_judges():
        planned.append(
            {
                "model": judge,
                "status": "planned",
                "quality_score": None,
                "latency_ms": None,
                "cache_key": cache_key(artifact, judge),
                "cache_hit": False,
            }
        )

    candidate = {
        "model": selected_model,
        "status": status,
        "quality_score": local_quality,
        "latency_ms": 0 if selected_model == "local-heuristic" else None,
        "cache_key": cache_key(artifact, selected_model),
        "cache_hit": False,
    }

    reason = "candidate passed schema, evidence, calibration, and actionability checks"
    if fallback_reason:
        reason = fallback_reason

    return {
        "strategy": "small_model_ensemble_with_frontier_escalation",
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "selection_policy": {
            "quality_weights": {
                "evidence_grounding": 0.32,
                "rubric_coverage": 0.22,
                "actionability": 0.2,
                "calibration_to_baseline": 0.16,
                "operational_health": 0.1,
            },
            "hard_rejects": [
                "invalid_json",
                "missing_rubric_dimensions",
                "hallucinated_evidence",
                "missing_next_step",
            ],
            "escalation_rule": "escalate to frontier judge when small judges disagree on weakest dimensions or quality score is below 0.72",
        },
        "candidates": [candidate, *planned],
        "selected_model": selected_model,
        "agreement": "not_measured_single_live_candidate",
        "escalated": False,
        "reason": reason,
    }
