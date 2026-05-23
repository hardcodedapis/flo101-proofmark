from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .schema import EvaluationRequest


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _mastery_label(value: float) -> str:
    if value >= 0.82:
        return "ready_to_credential"
    if value >= 0.65:
        return "proficient_progress"
    if value >= 0.45:
        return "developing"
    return "emerging"


def _clamp_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _update_mastery(prior: float, evidence_strength: float, confidence: str) -> float:
    confidence_weight = {
        "high": 0.44,
        "medium": 0.32,
        "low": 0.18,
    }.get(confidence, 0.24)
    return _clamp_probability(prior + confidence_weight * (evidence_strength - prior))


def _completion_verb(score: int) -> str:
    if score >= 82:
        return "demonstrated"
    if score >= 65:
        return "progressed_toward"
    return "attempted"


def build_skill_ledger(request: EvaluationRequest, result: dict[str, Any]) -> dict[str, Any]:
    score = int(result.get("overall_score", 0))
    confidence = result.get("reliability", {}).get("confidence", "medium")
    evidence_strength = score / 100
    updated_mastery = _update_mastery(request.prior_mastery, evidence_strength, confidence)
    proof_id = f"proof_{_stable_id(request.learner_id, request.learner_goal, request.artifact)}"
    generated_at = result.get("metadata", {}).get("generated_at") or datetime.now(timezone.utc).isoformat()

    weakest_dimensions = [
        item["name"]
        for item in sorted(result.get("rubric", []), key=lambda rubric_item: rubric_item.get("score", 0))
    ][:2]

    badge_like_assertion = {
        "type": ["ProofMarkAssertion", "OpenBadgeInspiredEvidence"],
        "id": proof_id,
        "learner": request.learner_id,
        "achievement": {
            "name": request.learner_goal,
            "achievementType": "Competency",
            "criteria": request.output_goal,
        },
        "evidence": [
            {
                "id": f"{proof_id}_artifact",
                "name": f"{request.artifact_type} artifact",
                "narrative": "Learner-submitted artifact evaluated as proof-of-work.",
                "genre": request.artifact_type,
                "proofMap": result.get("evidence_map", []),
            }
        ],
        "result": {
            "score": score,
            "confidence": confidence,
            "masteryProbability": round(updated_mastery, 3),
            "masteryLabel": _mastery_label(updated_mastery),
        },
        "issuedOn": generated_at,
    }

    xapi_statement = {
        "actor": {"account": {"name": request.learner_id}},
        "verb": {
            "id": f"https://proofmark.local/verbs/{_completion_verb(score)}",
            "display": {"en-US": _completion_verb(score).replace("_", " ")},
        },
        "object": {
            "id": f"https://proofmark.local/proofs/{proof_id}",
            "definition": {
                "name": {"en-US": request.learner_goal},
                "description": {"en-US": request.output_goal},
                "type": "https://proofmark.local/activity-types/proof-of-work",
            },
        },
        "result": {
            "score": {"scaled": round(evidence_strength, 3), "raw": score, "min": 0, "max": 100},
            "completion": score >= 65,
            "success": score >= 82,
            "extensions": {
                "https://proofmark.local/extensions/confidence": confidence,
                "https://proofmark.local/extensions/mastery_probability": round(updated_mastery, 3),
                "https://proofmark.local/extensions/weakest_dimensions": weakest_dimensions,
            },
        },
        "timestamp": generated_at,
    }

    return {
        "proof_id": proof_id,
        "learner_id": request.learner_id,
        "competency": request.learner_goal,
        "prior_mastery": round(request.prior_mastery, 3),
        "evidence_strength": round(evidence_strength, 3),
        "updated_mastery": round(updated_mastery, 3),
        "mastery_label": _mastery_label(updated_mastery),
        "weakest_dimensions": weakest_dimensions,
        "next_observation_needed": (
            f"Collect another artifact that directly addresses: {', '.join(weakest_dimensions)}."
            if weakest_dimensions
            else "Collect a transfer artifact in a new context."
        ),
        "standards_shaped_exports": {
            "open_badge_inspired_assertion": badge_like_assertion,
            "xapi_statement": xapi_statement,
        },
        "audit_hash": _stable_id(json.dumps(badge_like_assertion, sort_keys=True), json.dumps(xapi_statement, sort_keys=True)),
    }

