from __future__ import annotations

from copy import deepcopy
from typing import Any

from .actions import recommend_for_artifact
from .heuristics import evaluate_with_heuristics
from .ensemble import build_judge_trace
from .ledger import build_skill_ledger
from .learning_loop import build_learning_loop
from .providers import LocalProvider, ProviderError, choose_provider
from .rubric import RubricDimension, build_rubric
from .schema import EvaluationRequest, clamp_score, validate_payload


def _repair_result(
    result: dict[str, Any],
    request: EvaluationRequest,
    rubric: list[RubricDimension],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    repaired = deepcopy(baseline)
    if not isinstance(result, dict):
        return repaired

    for key in (
        "overall_score",
        "verdict",
        "missing_gaps",
        "next_best_step",
        "proof_of_work",
        "evidence_map",
        "feedback_loop",
        "judge_diagnostics",
        "learning_loop",
        "next_learning_action",
        "reliability",
    ):
        if key in result:
            repaired[key] = result[key]

    by_name = {
        str(item.get("name", "")).lower(): item
        for item in result.get("rubric", [])
        if isinstance(item, dict)
    }
    repaired_rubric = []
    for index, dimension in enumerate(rubric):
        fallback = baseline["rubric"][index]
        item = by_name.get(dimension.name.lower(), {})
        repaired_rubric.append(
            {
                "name": dimension.name,
                "score": clamp_score(item.get("score", fallback["score"])),
                "weight": dimension.weight,
                "evidence": str(item.get("evidence") or fallback["evidence"])[:500],
                "feedback": str(item.get("feedback") or fallback["feedback"])[:500],
                "risk_if_ignored": str(item.get("risk_if_ignored") or fallback["risk_if_ignored"])[:500],
            }
        )
    repaired["rubric"] = repaired_rubric

    weighted = sum(item["score"] * item["weight"] for item in repaired_rubric)
    repaired["overall_score"] = max(0, min(100, int(round((weighted / 5.0) * 100))))
    repaired["learner_goal"] = request.learner_goal
    repaired["output_goal"] = request.output_goal
    repaired.setdefault("metadata", {})
    repaired["metadata"].update(
        {
            "artifact_type": request.artifact_type,
            "level": request.level,
            "word_count": request.word_count,
        }
    )

    if not isinstance(repaired.get("reliability"), dict):
        repaired["reliability"] = deepcopy(baseline["reliability"])
    warnings = repaired["reliability"].setdefault("warnings", [])
    if not isinstance(warnings, list):
        repaired["reliability"]["warnings"] = []
    for warning in request.warnings:
        if warning not in repaired["reliability"]["warnings"]:
            repaired["reliability"]["warnings"].append(warning)

    if not isinstance(repaired.get("missing_gaps"), list) or not repaired["missing_gaps"]:
        repaired["missing_gaps"] = baseline["missing_gaps"]
    if not isinstance(repaired.get("next_best_step"), dict):
        repaired["next_best_step"] = baseline["next_best_step"]
    if not isinstance(repaired.get("proof_of_work"), dict):
        repaired["proof_of_work"] = baseline["proof_of_work"]
    if not isinstance(repaired.get("evidence_map"), list):
        repaired["evidence_map"] = baseline["evidence_map"]
    if not isinstance(repaired.get("feedback_loop"), dict):
        repaired["feedback_loop"] = baseline["feedback_loop"]
    if not isinstance(repaired.get("judge_diagnostics"), dict):
        repaired["judge_diagnostics"] = baseline["judge_diagnostics"]
    repaired["skill_ledger"] = build_skill_ledger(request, repaired)
    repaired["learning_loop"] = build_learning_loop(request, repaired)
    if not isinstance(repaired.get("next_learning_action"), dict):
        repaired["next_learning_action"] = recommend_for_artifact(request, repaired)
    return repaired


def evaluate_artifact(
    payload: dict[str, Any],
    provider: str | None = None,
) -> dict[str, Any]:
    request = validate_payload(payload)
    rubric = build_rubric(request)
    baseline = evaluate_with_heuristics(request, rubric)
    selected_provider = choose_provider(provider)

    if isinstance(selected_provider, LocalProvider):
        baseline["judge_trace"] = build_judge_trace(
            baseline,
            baseline,
            request.artifact,
            "local-heuristic",
            status="selected",
        )
        return baseline

    try:
        generated = selected_provider.evaluate(request, rubric, baseline)
        repaired = _repair_result(generated, request, rubric, baseline)
        repaired["metadata"]["provider"] = generated.get("metadata", {}).get("provider", selected_provider.name)
        repaired["metadata"]["fallback_used"] = False
        repaired["judge_trace"] = build_judge_trace(
            repaired,
            baseline,
            request.artifact,
            repaired["metadata"]["provider"],
            status="selected",
        )
        return repaired
    except ProviderError as exc:
        fallback = deepcopy(baseline)
        fallback["reliability"]["warnings"].append(
            {
                "code": "provider_fallback",
                "message": f"AI provider failed, so deterministic local evaluation was used: {exc}",
            }
        )
        fallback["metadata"]["fallback_used"] = True
        fallback["judge_trace"] = build_judge_trace(
            fallback,
            baseline,
            request.artifact,
            "local-heuristic",
            status="fallback",
            fallback_reason=f"primary provider failed: {exc}",
        )
        return fallback
