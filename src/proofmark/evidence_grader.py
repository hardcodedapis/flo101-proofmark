from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


REASONING_WORDS = {
    "because",
    "therefore",
    "so",
    "means",
    "causes",
    "compare",
    "different",
    "rule",
    "formula",
    "source",
    "evidence",
    "trap",
    "unit",
    "sign",
    "arrow",
    "label",
    "diagram",
}

SERVER_RUBRIC_VERSION = "track-b-evidence-rubric-v1"
SERVER_RUBRIC = [
    {"dimension": "concept_coverage", "weight": 0.36, "description": "Uses required concept and source terms."},
    {"dimension": "reasoning", "weight": 0.22, "description": "Explains why the answer follows."},
    {"dimension": "completeness", "weight": 0.16, "description": "Gives enough detail to evaluate the response."},
    {"dimension": "transfer", "weight": 0.10, "description": "Applies the idea to a changed example or case."},
    {"dimension": "interaction_evidence", "weight": 0.16, "description": "Uses selected choices or drawing features when present."},
]


def grade_learner_event(event: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    """Server-side scoring for browser evidence.

    This is intentionally simple and inspectable. It does not claim to be a full
    LLM grader; it prevents the adaptive loop from trusting client-supplied
    scores and turns raw interaction evidence into conservative learner signals.
    """
    cleaned = deepcopy(event)
    concepts = _concepts(cleaned, graph)
    prompt = _text(_nested(cleaned, "activity", "prompt_variant"))
    answer = _text(_nested(cleaned, "response_quality", "raw_response") or _nested(cleaned, "response", "raw_response"))
    interaction = cleaned.get("interaction") if isinstance(cleaned.get("interaction"), dict) else {}
    activity_type = _text(_nested(cleaned, "activity", "activity_type")).lower()
    mode = _text(_nested(cleaned, "activity", "mode")).lower()

    score, evidence = _score_event(activity_type, mode, prompt, answer, interaction, concepts, graph)
    correctness = "correct" if score >= 0.72 else "partial" if score >= 0.42 else "incorrect"
    selected_mode = "mixed_practice" if correctness == "correct" else "worked_example" if correctness == "partial" else "visual_contrast"
    misconception = _misconception_from_evidence(correctness, concepts, answer, evidence, interaction)

    cleaned["server_scored"] = True
    cleaned["response_quality"] = {
        **(cleaned.get("response_quality") if isinstance(cleaned.get("response_quality"), dict) else {}),
        "raw_response": answer,
        "score": score,
        "partial_credit": score if correctness == "partial" else 0,
        "correctness": correctness,
        "answer_completeness": evidence["completeness"],
        "precision": evidence["precision"],
        "uses_required_terms": evidence["concept_coverage"] >= 0.5,
        "server_scoring_basis": evidence["basis"],
        "server_rubric_version": SERVER_RUBRIC_VERSION,
        "server_rubric": SERVER_RUBRIC,
        "rubric_evidence": evidence["rubric_evidence"],
    }
    cleaned["reasoning_signals"] = {
        **(cleaned.get("reasoning_signals") if isinstance(cleaned.get("reasoning_signals"), dict) else {}),
        "error_type": "" if correctness == "correct" else "partial_relation" if correctness == "partial" else "concept_substitution",
        "misconception": misconception,
        "missing_prerequisite": "" if correctness != "incorrect" else "source evidence or concept distinction",
        "reasoning_depth": evidence["reasoning"],
        "step_order_quality": evidence["reasoning"],
        "causal_link_quality": max(0.1, score - 0.08),
        "transfer_quality": evidence["transfer"],
    }
    modality = cleaned.get("modality_signals") if isinstance(cleaned.get("modality_signals"), dict) else {}
    is_visual = mode == "visual" or activity_type in {"visual_map", "draw_question"}
    cleaned["modality_signals"] = {
        **modality,
        "text_comprehension": score if not is_visual else modality.get("text_comprehension", 0.5),
        "visual_interpretation": score if is_visual else modality.get("visual_interpretation", 0.5),
        "diagram_to_formula_transfer": evidence["diagram_transfer"] if is_visual else modality.get("diagram_to_formula_transfer", 0.45),
        "typed_explanation": score if mode == "typed" else modality.get("typed_explanation", 0.5),
        "symbolic_reasoning": evidence["symbolic"],
    }
    cleaned["intervention_trace"] = {
        **(cleaned.get("intervention_trace") if isinstance(cleaned.get("intervention_trace"), dict) else {}),
        "selected_next_mode": selected_mode,
        "selection_reason": f"server graded checkpoint as {correctness}",
        "did_improve_after_hint": correctness != "incorrect",
    }
    cleaned["memory_state"] = {
        **(cleaned.get("memory_state") if isinstance(cleaned.get("memory_state"), dict) else {}),
        "retrieval_attempts": max(1, int(_number(_nested(cleaned, "memory_state", "retrieval_attempts"), 1))),
        "retrieval_success": correctness == "correct",
        "encoding_strength": score,
        "estimated_half_life_days": max(1, round(1 + score * 7)),
        "next_review_in_days": 1 if score < 0.45 else 2 if score < 0.7 else 5,
    }
    return cleaned


def _score_event(
    activity_type: str,
    mode: str,
    prompt: str,
    answer: str,
    interaction: dict[str, Any],
    concepts: list[str],
    graph: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    if activity_type == "mcq":
        return _score_mcq(interaction, concepts)

    source_terms = _source_terms(graph, concepts)
    answer_tokens = set(_tokens(answer))
    concept_tokens = set(token for concept in concepts for token in _tokens(concept))
    required_terms = concept_tokens | source_terms
    concept_coverage = _coverage(answer_tokens, required_terms)
    reasoning = min(1.0, len(answer_tokens & REASONING_WORDS) / 4)
    completeness = min(1.0, len(answer_tokens) / 32)
    transfer = 1.0 if any(word in answer_tokens for word in {"new", "different", "changed", "example", "case"}) else max(0.2, reasoning * 0.7)
    symbolic = 1.0 if re.search(r"[=+\-*/^]|\\frac|theta|lambda|delta|sigma", answer) else max(0.25, concept_coverage)
    diagram_transfer = 0.5

    if activity_type in {"visual_map", "draw_question"} or mode == "visual":
        selected = _list(interaction.get("selected_features"))
        expected = _list(interaction.get("expected_features"))
        selected_coverage = len(set(selected) & set(expected)) / max(1, len(expected))
        diagram_words = {"label", "arrow", "ray", "axis", "node", "edge", "focus", "image", "formula", "trap", "source"}
        diagram_transfer = max(selected_coverage, min(1.0, len(answer_tokens & diagram_words) / 4))
        score = 0.12 + 0.32 * selected_coverage + 0.24 * concept_coverage + 0.18 * diagram_transfer + 0.14 * completeness
        basis = f"visual evidence: selected_features={len(selected)}, expected_features={len(expected)}, concept_coverage={concept_coverage:.2f}"
        interaction_evidence = selected_coverage
    else:
        score = 0.16 + 0.36 * concept_coverage + 0.22 * reasoning + 0.16 * completeness + 0.10 * transfer
        basis = f"typed evidence: concept_coverage={concept_coverage:.2f}, reasoning={reasoning:.2f}, completeness={completeness:.2f}"
        interaction_evidence = 0.5 if answer_tokens else 0.0

    matched_terms = sorted(answer_tokens & required_terms)[:12]
    missing_terms = sorted(required_terms - answer_tokens)[:12]

    return round(max(0.05, min(0.95, score)), 2), {
        "basis": basis,
        "concept_coverage": round(concept_coverage, 2),
        "reasoning": round(reasoning, 2),
        "completeness": round(completeness, 2),
        "precision": round((concept_coverage + reasoning) / 2, 2),
        "transfer": round(transfer, 2),
        "symbolic": round(symbolic, 2),
        "diagram_transfer": round(diagram_transfer, 2),
        "interaction_evidence": round(interaction_evidence, 2),
        "rubric_evidence": {
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "reasoning_markers": sorted(answer_tokens & REASONING_WORDS),
            "answer_token_count": len(answer_tokens),
            "interaction_evidence": round(interaction_evidence, 2),
        },
    }


def _score_mcq(interaction: dict[str, Any], concepts: list[str]) -> tuple[float, dict[str, Any]]:
    selected = _text(interaction.get("selected_choice_text")).lower()
    correct = "separate" in selected and ("source" in selected or "cite" in selected)
    wrong = any(marker in selected for marker in ["interchangeable", "skip reasoning", "memorize only"])
    score = 0.86 if correct else 0.18 if wrong else 0.5
    return score, {
        "basis": f"mcq selected_choice_text graded on server for {concepts[0] if concepts else 'target concept'}",
        "concept_coverage": 0.8 if correct else 0.2,
        "reasoning": 0.75 if correct else 0.2,
        "completeness": 1.0,
        "precision": 0.8 if correct else 0.2,
        "transfer": 0.45 if correct else 0.15,
        "symbolic": 0.5,
        "diagram_transfer": 0.5,
        "interaction_evidence": 1.0,
        "rubric_evidence": {
            "selected_choice_text": selected,
            "matched_terms": _tokens(selected)[:12],
            "missing_terms": [],
            "reasoning_markers": [],
            "answer_token_count": len(_tokens(selected)),
            "interaction_evidence": 1.0,
        },
    }


def _misconception_from_evidence(
    correctness: str,
    concepts: list[str],
    answer: str,
    evidence: dict[str, Any],
    interaction: dict[str, Any],
) -> str:
    if correctness == "correct":
        return ""
    target = concepts[0] if concepts else "target concept"
    answer_lower = answer.lower()
    if not answer_lower:
        return f"missing answer evidence for {target}"
    expected = _list(interaction.get("expected_features"))
    selected = _list(interaction.get("selected_features"))
    missed_features = [feature for feature in expected if feature not in selected]
    if missed_features:
        return f"drawing omitted {missed_features[0]} while explaining {target}"
    if evidence.get("concept_coverage", 0) < 0.35:
        return f"answer omits required source terms for {target}"
    if evidence.get("reasoning", 0) < 0.35:
        return f"answer names {target} but does not explain the reasoning link"
    if any(marker in answer_lower for marker in ["same thing", "interchangeable", "just memorize", "only formula"]):
        return f"confuses {target} with a surface rule instead of the source-backed distinction"
    return f"needs source-grounded repair for {target}"


def _concepts(event: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    context = event.get("learning_context", {}) if isinstance(event.get("learning_context"), dict) else {}
    values = context.get("concepts") or event.get("concepts") or []
    if isinstance(values, str):
        values = [values]
    concepts = [str(value).strip() for value in values if str(value).strip()]
    if concepts:
        return concepts[:4]
    return [concept.get("name", "") for concept in graph.get("concepts", [])[:3] if concept.get("name")]


def _source_terms(graph: dict[str, Any], concepts: list[str]) -> set[str]:
    terms: set[str] = set()
    concept_lowers = [concept.lower() for concept in concepts]
    for chunk in graph.get("chunks", [])[:12]:
        text = str(chunk.get("text", ""))
        if concept_lowers and not any(concept in text.lower() for concept in concept_lowers):
            continue
        terms.update(_tokens(text)[:18])
    return {term for term in terms if len(term) > 3}


def _coverage(answer_tokens: set[str], required_terms: set[str]) -> float:
    if not required_terms:
        return 0.35 if answer_tokens else 0.0
    return min(1.0, len(answer_tokens & required_terms) / max(3, min(10, len(required_terms))))


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", value)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return []


def _nested(event: dict[str, Any], *keys: str) -> Any:
    value: Any = event
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
