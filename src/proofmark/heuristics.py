from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from .actions import recommend_for_artifact
from .ledger import build_skill_ledger
from .learning_loop import build_learning_loop
from .rubric import RubricDimension
from .schema import EvaluationRequest


NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

ACTION_WORDS = {
    "build",
    "compare",
    "create",
    "define",
    "evaluate",
    "implement",
    "measure",
    "prioritize",
    "ship",
    "test",
    "validate",
}

EVIDENCE_WORDS = {
    "because",
    "data",
    "evidence",
    "example",
    "experiment",
    "metric",
    "observed",
    "result",
    "tested",
    "validated",
}

TRADEOFF_WORDS = {
    "alternative",
    "constraint",
    "cost",
    "latency",
    "limitation",
    "reliability",
    "risk",
    "tradeoff",
}

NEXT_STEP_WORDS = {
    "acceptance",
    "criteria",
    "follow-up",
    "improve",
    "iterate",
    "next",
    "ship",
    "todo",
}


def _split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]
    if not parts:
        return [text[:240].strip()] if text.strip() else []
    return parts


def _keyword_count(text: str, keywords: set[str] | tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for word in keywords if re.search(rf"\b{re.escape(word)}\b", lowered))


def _goal_overlap(goal: str, artifact: str) -> int:
    goal_words = {
        word.lower()
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", goal)
        if word.lower() not in {"with", "from", "this", "that", "will", "have", "show"}
    }
    artifact_lower = artifact.lower()
    return sum(1 for word in goal_words if word in artifact_lower)


def _score_for_dimension(request: EvaluationRequest, dimension: RubricDimension) -> int:
    text = request.artifact
    lowered = text.lower()
    word_count = request.word_count
    signal_hits = _keyword_count(lowered, dimension.signals)
    number_hits = len(NUMBER_RE.findall(text))
    action_hits = _keyword_count(lowered, ACTION_WORDS)
    evidence_hits = _keyword_count(lowered, EVIDENCE_WORDS)
    tradeoff_hits = _keyword_count(lowered, TRADEOFF_WORDS)
    next_hits = _keyword_count(lowered, NEXT_STEP_WORDS)
    goal_hits = _goal_overlap(request.learner_goal, text)

    score = 2
    if word_count >= 120:
        score += 1
    if word_count >= 350:
        score += 1
    if signal_hits >= 2:
        score += 1

    name = dimension.name.lower()
    if "goal" in name:
        score = 2 + min(2, goal_hits) + (1 if request.output_goal.lower().split()[0] in lowered else 0)
    elif "reasoning" in name:
        score = 1 + min(2, evidence_hits) + (1 if number_hits else 0) + (1 if "because" in lowered or "why" in lowered else 0)
    elif "execution" in name:
        score = 1 + min(2, action_hits) + (1 if re.search(r"\b(step|1\.|2\.|acceptance|checklist)\b", lowered) else 0)
        if request.artifact_type == "code" and ("def " in text or "class " in text or "function " in text):
            score += 1
    elif "tradeoff" in name or "reflection" in name:
        score = 1 + min(3, tradeoff_hits) + (1 if "why" in lowered or "because" in lowered else 0)
    elif "next-step" in name:
        score = 2 + min(2, next_hits) + (1 if "acceptance" in lowered or "criteria" in lowered else 0)
    elif "correctness" in name:
        score = 2 + (1 if "test" in lowered or "assert" in lowered else 0) + (1 if "edge" in lowered or "error" in lowered else 0)
        if request.artifact_type == "code" and ("def " in text or "class " in text or "function " in text):
            score += 1
    elif "maintainability" in name:
        score = 2 + (1 if request.artifact_type == "code" and re.search(r"\b(def|class|function)\b", lowered) else 0)
        score += 1 if _keyword_count(lowered, {"readme", "doc", "type", "module"}) else 0

    return max(1, min(5, int(score)))


def _evidence_snippet(sentences: list[str], dimension: RubricDimension) -> str:
    for sentence in sentences:
        if _keyword_count(sentence.lower(), dimension.signals):
            return sentence[:280]
    return sentences[0][:280] if sentences else "No specific evidence found."


def _feedback_for_score(dimension: RubricDimension, score: int) -> str:
    if score >= 5:
        return f"Strong evidence for {dimension.description.lower()}"
    if score == 4:
        return f"Mostly satisfies this dimension; make the evidence easier to verify."
    if score == 3:
        return f"Partially satisfies this dimension, but the artifact needs more concrete proof."
    return f"Insufficient evidence for this dimension; add explicit examples, checks, or constraints."


def _gap_for_dimension(dimension: RubricDimension) -> str:
    name = dimension.name.lower()
    if "goal" in name:
        return "Tie the artifact back to the learner goal, target user, and expected output."
    if "reasoning" in name:
        return "Add evidence: examples, metrics, test results, or reasoning that supports the claims."
    if "execution" in name:
        return "Convert intent into verifiable execution detail with steps, checks, and acceptance criteria."
    if "tradeoff" in name or "reflection" in name:
        return "Name the main tradeoff or risk and explain why this approach is still reasonable."
    if "next" in name:
        return "State the next improvement step with a clear completion criterion."
    if "correctness" in name:
        return "Include tests, expected behavior, edge cases, or failure handling evidence."
    if "maintainability" in name:
        return "Explain structure and make the implementation easier to review and modify."
    return f"Strengthen the artifact against the '{dimension.name}' rubric dimension."


def _confidence(request: EvaluationRequest, dimension_scores: list[int]) -> str:
    if request.word_count < 40:
        return "low"
    spread = max(dimension_scores) - min(dimension_scores)
    if spread >= 3 or request.warnings:
        return "medium"
    return "high"


def _proof_status(score: int) -> str:
    if score >= 4:
        return "supported"
    if score == 3:
        return "partial"
    return "missing"


def _proof_claim_for_dimension(request: EvaluationRequest, dimension: RubricDimension) -> str:
    name = dimension.name.lower()
    if "goal" in name:
        return f"The artifact addresses the learner goal: {request.learner_goal}"
    if "reasoning" in name:
        return "The artifact supports its claims with reasoning, examples, or measurable evidence."
    if "execution" in name:
        return "The artifact shows concrete execution detail that a reviewer can inspect."
    if "tradeoff" in name or "reflection" in name:
        return "The artifact reflects on constraints, risks, tradeoffs, or alternatives."
    if "next" in name:
        return "The artifact makes the next improvement step clear enough to act on."
    if "correctness" in name:
        return "The code artifact includes correctness evidence, tests, or edge-case handling."
    if "maintainability" in name:
        return "The code artifact is structured so another engineer can understand and change it."
    return f"The artifact demonstrates '{dimension.name}'."


def _verification_prompt_for_dimension(dimension: RubricDimension) -> str:
    name = dimension.name.lower()
    if "goal" in name:
        return "Can a reviewer identify the learner goal and expected output from the artifact alone?"
    if "reasoning" in name:
        return "Which sentence, example, metric, or test result supports the main claim?"
    if "execution" in name:
        return "What concrete work was done, and how could another person verify it?"
    if "tradeoff" in name or "reflection" in name:
        return "What was consciously traded off, and why was that choice reasonable?"
    if "next" in name:
        return "What exact revision would change the weakest score?"
    if "correctness" in name:
        return "Which test or edge case proves the code behaves correctly?"
    if "maintainability" in name:
        return "Can another engineer safely modify this without hidden context?"
    return f"What visible evidence proves '{dimension.name}'?"


def _build_evidence_map(
    request: EvaluationRequest,
    rubric: list[RubricDimension],
    dimensions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_name = {dimension.name: dimension for dimension in rubric}
    evidence_map: list[dict[str, Any]] = []
    for item in dimensions:
        dimension = by_name[item["name"]]
        status = _proof_status(int(item["score"]))
        evidence_map.append(
            {
                "dimension": item["name"],
                "claim": _proof_claim_for_dimension(request, dimension),
                "status": status,
                "evidence": item["evidence"] if status != "missing" else "",
                "missing_proof": "" if status == "supported" else item["risk_if_ignored"],
                "verification_question": _verification_prompt_for_dimension(dimension),
            }
        )
    return evidence_map


def evaluate_with_heuristics(
    request: EvaluationRequest,
    rubric: list[RubricDimension],
    provider_name: str = "local-heuristic",
) -> dict[str, Any]:
    sentences = _split_sentences(request.artifact)
    dimensions = []
    score_values = []

    for dimension in rubric:
        score = _score_for_dimension(request, dimension)
        score_values.append(score)
        dimensions.append(
            {
                "name": dimension.name,
                "score": score,
                "weight": dimension.weight,
                "evidence": _evidence_snippet(sentences, dimension),
                "feedback": _feedback_for_score(dimension, score),
                "risk_if_ignored": _gap_for_dimension(dimension),
            }
        )

    weighted = sum(item["score"] * item["weight"] for item in dimensions)
    overall_percent = int(round((weighted / 5.0) * 100))
    low_dimensions = [item for item in dimensions if item["score"] <= 3]
    lowest = min(dimensions, key=lambda item: (item["score"], -item["weight"]))

    if overall_percent >= 82:
        verdict = "Ready evidence of progress"
    elif overall_percent >= 65:
        verdict = "Promising, needs targeted improvement"
    else:
        verdict = "Not yet sufficient proof-of-work"

    missing_gaps = [item["risk_if_ignored"] for item in low_dimensions]
    if not missing_gaps:
        missing_gaps = ["No major gaps detected; tighten specificity and verification evidence."]

    next_step_title = f"Upgrade '{lowest['name']}' evidence"
    next_step = {
        "title": next_step_title,
        "why": lowest["risk_if_ignored"],
        "instructions": (
            "Revise the artifact by adding one concrete example, one verification check, "
            "and one sentence explaining the tradeoff behind the chosen approach."
        ),
        "acceptance_criteria": [
            "A reviewer can point to evidence for the weakest rubric dimension.",
            "The artifact includes a measurable or observable completion criterion.",
            "The next revision can be evaluated without asking the learner for hidden context.",
        ],
    }

    observed = [
        f"{item['name']}: {item['evidence']}"
        for item in dimensions
        if item["score"] >= 4
    ][:3]
    if not observed:
        observed = ["The artifact is present but does not yet provide strong verifiable evidence."]

    evidence_map = _build_evidence_map(request, rubric, dimensions)

    result = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider_name,
            "artifact_type": request.artifact_type,
            "level": request.level,
            "word_count": request.word_count,
            "fallback_used": False,
        },
        "learner_goal": request.learner_goal,
        "output_goal": request.output_goal,
        "overall_score": overall_percent,
        "verdict": verdict,
        "rubric": dimensions,
        "missing_gaps": missing_gaps,
        "next_best_step": next_step,
        "proof_of_work": {
            "evidence_observed": observed,
            "evidence_missing": missing_gaps,
            "verification_questions": [
                "What specific behavior or output proves this learner can apply the skill?",
                "Which evidence would change the score on the weakest dimension?",
                "Can a reviewer reproduce or inspect the claim from the artifact alone?",
            ],
        },
        "evidence_map": evidence_map,
        "feedback_loop": {
            "feed_up_goal": request.output_goal,
            "feed_back_current_state": (
                f"The artifact currently scores {overall_percent}/100 with the weakest evidence in "
                f"'{lowest['name']}'."
            ),
            "feed_forward_next_action": next_step["instructions"],
        },
        "judge_diagnostics": {
            "bias_checks": [
                "Score visible evidence, not writing polish or confidence.",
                "Do not reward length unless it adds verifiable proof.",
                "Use the same rubric dimensions for every artifact of this type.",
            ],
            "calibration_notes": [
                "Local score is deterministic and intended as a reliability floor.",
                "Human review is still recommended for high-stakes certification decisions.",
            ],
        },
        "reliability": {
            "confidence": _confidence(request, score_values),
            "checks_passed": [
                "Input validation completed",
                "Rubric dimensions scored on a 1-5 scale",
                "Next step selected from the lowest-scoring dimension",
            ],
            "warnings": list(request.warnings),
        },
    }
    result["skill_ledger"] = build_skill_ledger(request, result)
    result["learning_loop"] = build_learning_loop(request, result)
    result["next_learning_action"] = recommend_for_artifact(request, result)
    return result


def estimated_cost_units(result: dict[str, Any]) -> int:
    words = result.get("metadata", {}).get("word_count", 0)
    return int(math.ceil(words / 250))
