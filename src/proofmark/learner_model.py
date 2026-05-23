from __future__ import annotations

from collections import defaultdict
import re
from statistics import mean
from typing import Any


ANCHOR_PROFILES: dict[str, dict[str, Any]] = {
    "high_support": {
        "label": "High-support learner",
        "description": "Needs prerequisite repair, low cognitive load, short segments, scaffolded hints, and earlier review.",
        "default_modes": ["worked_example", "visual_cue", "hint_ladder", "short_quiz"],
        "pace": "short_steps",
        "challenge_level": "guided",
    },
    "balanced": {
        "label": "Balanced learner",
        "description": "Can handle mixed explanation and practice with moderate scaffolding and teach-back checks.",
        "default_modes": ["structured_notes", "micro_quiz", "teach_back", "mixed_practice"],
        "pace": "standard",
        "challenge_level": "moderate",
    },
    "advanced": {
        "label": "Advanced learner",
        "description": "Benefits from compressed explanations, ambiguity, transfer challenges, and lower repetition.",
        "default_modes": ["compressed_notes", "transfer_case", "roleplay", "hard_variant"],
        "pace": "fast",
        "challenge_level": "transfer",
    },
}

DEFAULT_SKILLS = {
    "visual_interpretation": 0.5,
    "text_comprehension": 0.5,
    "typed_explanation": 0.5,
    "spoken_explanation": 0.5,
    "symbolic_reasoning": 0.5,
    "numerical_execution": 0.5,
    "multi_step_reasoning": 0.5,
    "concept_discrimination": 0.5,
    "transfer": 0.5,
    "confidence_calibration": 0.5,
    "hint_independence": 0.5,
    "persistence": 0.5,
    "retention_stability": 0.5,
}

TOPIC_STOP_TOKENS = {
    "and",
    "answer",
    "concept",
    "for",
    "from",
    "explain",
    "formula",
    "into",
    "learn",
    "learning",
    "objective",
    "per",
    "point",
    "question",
    "reasoning",
    "solve",
    "source",
    "teach",
    "theorem",
    "the",
    "understand",
    "with",
}


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(low, min(high, number))


def _nested(event: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = event
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _normalize(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in values.values())
    if total <= 0:
        return {key: round(1 / len(values), 3) for key in values}
    return {key: round(max(0.0, value) / total, 3) for key, value in values.items()}


def _event_score(event: dict[str, Any]) -> float:
    score = _nested(event, "response_quality", "score", default=None)
    if score is None:
        score = _nested(event, "response", "score", default=None)
    if score is None:
        correctness = str(_nested(event, "response_quality", "correctness", default="")).lower()
        if correctness == "correct":
            score = 1.0
        elif correctness == "partial":
            score = 0.55
        elif correctness == "incorrect":
            score = 0.15
        else:
            score = 0.5
    return _clamp(score)


def _confidence(event: dict[str, Any]) -> float:
    confidence = _nested(event, "metacognition", "self_reported_confidence", default=None)
    if confidence is None:
        confidence = _nested(event, "response", "confidence_self_reported", default=None)
    if confidence is None:
        confidence = event.get("confidence")
    return _clamp(0.5 if confidence is None else confidence)


def _concepts_from_event(event: dict[str, Any]) -> list[str]:
    context = event.get("learning_context", {}) if isinstance(event.get("learning_context"), dict) else {}
    concepts = context.get("concepts") or event.get("concepts") or []
    if isinstance(concepts, str):
        concepts = [concepts]
    return [str(concept).strip() for concept in concepts if str(concept).strip()]


def _text_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", value.lower())
        if token not in TOPIC_STOP_TOKENS
    }


def _event_topic_text(event: dict[str, Any]) -> str:
    context = event.get("learning_context", {}) if isinstance(event.get("learning_context"), dict) else {}
    activity = event.get("activity", {}) if isinstance(event.get("activity"), dict) else {}
    response = event.get("response_quality", {}) if isinstance(event.get("response_quality"), dict) else {}
    return " ".join(
        str(value or "")
        for value in [
            context.get("objective"),
            context.get("domain"),
            context.get("topic"),
            " ".join(_concepts_from_event(event)),
            activity.get("prompt_variant"),
            response.get("raw_response"),
        ]
    ).lower()


def _event_matches_graph(event: dict[str, Any], graph: dict[str, Any] | None) -> bool:
    if not isinstance(graph, dict):
        return True
    concepts = [str(item.get("name", "")).strip().lower() for item in graph.get("concepts", []) if isinstance(item, dict)]
    concepts = [concept for concept in concepts if concept]
    if not concepts:
        return True

    event_concepts = [concept.lower() for concept in _concepts_from_event(event)]
    event_text = _event_topic_text(event)
    graph_terms = set().union(*(_text_tokens(concept) for concept in concepts))
    objective_terms = _text_tokens(str(graph.get("learning_objective", "")))
    event_terms = set().union(*(_text_tokens(concept) for concept in event_concepts))
    event_terms |= _text_tokens(event_text)

    if event_concepts:
        for event_concept in event_concepts:
            if any(event_concept == concept or event_concept in concept or concept in event_concept for concept in concepts):
                return True
        event_concept_terms = set().union(*(_text_tokens(concept) for concept in event_concepts))
        return bool(event_concept_terms & graph_terms)

    if any(concept in event_text for concept in concepts):
        return True

    return bool((graph_terms | objective_terms) & event_terms)


def filter_events_for_graph(raw_events: list[Any], graph: dict[str, Any] | None) -> tuple[list[dict[str, Any]], int]:
    filtered: list[dict[str, Any]] = []
    ignored = 0
    for event in raw_events:
        if not isinstance(event, dict):
            ignored += 1
            continue
        if _event_matches_graph(event, graph):
            filtered.append(event)
        else:
            ignored += 1
    return filtered, ignored


def _filter_events_for_graph(raw_events: list[Any], graph: dict[str, Any] | None) -> tuple[list[dict[str, Any]], int]:
    return filter_events_for_graph(raw_events, graph)


def _skill_values_from_event(event: dict[str, Any]) -> dict[str, float]:
    modality = event.get("modality_signals", {}) if isinstance(event.get("modality_signals"), dict) else {}
    reasoning = event.get("reasoning_signals", {}) if isinstance(event.get("reasoning_signals"), dict) else {}
    hint = event.get("hint_behavior", {}) if isinstance(event.get("hint_behavior"), dict) else {}
    affect = event.get("affective_behavior", {}) if isinstance(event.get("affective_behavior"), dict) else {}
    voice = event.get("voice_signals", {}) if isinstance(event.get("voice_signals"), dict) else {}
    memory = event.get("memory_state", {}) if isinstance(event.get("memory_state"), dict) else {}
    visual = event.get("visual_interaction", {}) if isinstance(event.get("visual_interaction"), dict) else {}
    score = _event_score(event)
    confidence = _confidence(event)

    hint_count = _clamp(hint.get("hint_count", 0), 0, 5)
    hint_independence = 1.0 - min(1.0, hint_count / 4)
    if hint.get("max_hint_level") in {"full_solution", "heavy_scaffold"}:
        hint_independence *= 0.55

    calibration = 1.0 - abs(confidence - score)
    spoken = voice.get("conceptual_clarity")
    if spoken is None:
        spoken = voice.get("answer_structure")
    if spoken is None and voice.get("available") is False:
        spoken = None

    values = {
        "visual_interpretation": modality.get("visual_interpretation", visual.get("spatial_relation_score", score)),
        "text_comprehension": modality.get("text_comprehension", score),
        "typed_explanation": modality.get("typed_explanation", reasoning.get("causal_link_quality", score)),
        "spoken_explanation": spoken,
        "symbolic_reasoning": modality.get("symbolic_reasoning", score),
        "numerical_execution": modality.get("numerical_execution", score),
        "multi_step_reasoning": reasoning.get("step_order_quality", score),
        "concept_discrimination": 1.0 - _clamp(1 if reasoning.get("error_type") == "concept_substitution" else 0),
        "transfer": reasoning.get("transfer_quality", score),
        "confidence_calibration": calibration,
        "hint_independence": hint_independence,
        "persistence": affect.get("persistence", 0.55),
        "retention_stability": memory.get("encoding_strength", memory.get("estimated_half_life_days", score) if score <= 1 else 0.5),
    }
    return {key: _clamp(value) for key, value in values.items() if value is not None}


def build_telemetry_schema() -> dict[str, Any]:
    return {
        "identity": ["event_id", "session_id", "learner_id", "timestamp"],
        "learning_context": ["objective", "domain", "topic", "concepts", "prerequisites", "exam_context", "difficulty", "bloom_level"],
        "activity": ["stage", "mode", "activity_type", "prompt_variant", "input_media", "expected_output", "support_level"],
        "response_quality": ["raw_response", "score", "partial_credit", "correctness", "answer_completeness", "precision", "uses_required_terms"],
        "reasoning_signals": ["error_type", "misconception", "missing_prerequisite", "reasoning_depth", "step_order_quality", "causal_link_quality", "transfer_quality"],
        "metacognition": ["self_reported_confidence", "confidence_accuracy_gap", "calibration_label", "changed_answer_after_reflection", "reflection_quality"],
        "temporal_behavior": ["time_to_first_action_seconds", "total_response_time_seconds", "idle_time_seconds", "time_after_hint_seconds", "revision_count"],
        "hint_behavior": ["hint_requested", "hint_count", "hint_types", "max_hint_level", "improvement_after_hint", "hint_dependence"],
        "modality_signals": ["text_comprehension", "visual_interpretation", "diagram_to_formula_transfer", "spoken_explanation", "typed_explanation", "symbolic_reasoning"],
        "voice_signals": ["fluency", "pace_words_per_minute", "pause_density", "filler_density", "answer_structure", "composure", "correction_uptake"],
        "visual_interaction": ["selected_nodes", "correct_edges_identified", "incorrect_edges_identified", "spatial_relation_score", "map_navigation_pattern"],
        "affective_behavior": ["frustration_proxy", "persistence", "dropoff_risk", "help_seeking_style", "challenge_tolerance"],
        "intervention_trace": ["before_activity", "current_activity", "candidate_next_modes", "selected_next_mode", "selection_reason", "did_improve_after_hint"],
        "memory_state": ["first_seen_at", "exposures", "retrieval_attempts", "retrieval_success", "encoding_strength", "estimated_half_life_days", "next_review_in_days"],
    }


def sample_evidence_events() -> list[dict[str, Any]]:
    return [
        {
            "identity": {"event_id": "evt-visual-001", "session_id": "demo-session", "learner_id": "demo-learner"},
            "learning_context": {
                "objective": "understand electric potential and solve transfer problems",
                "domain": "Physics",
                "topic": "Electrostatics",
                "concepts": ["electric potential", "electric field", "work per unit charge"],
                "difficulty": 0.48,
                "bloom_level": "understand",
            },
            "activity": {"stage": "concept_map_probe", "mode": "visual", "activity_type": "edge_selection"},
            "response_quality": {"score": 0.58, "correctness": "partial"},
            "reasoning_signals": {
                "error_type": "partial_relation",
                "misconception": "treats potential as a vector",
                "step_order_quality": 0.45,
                "causal_link_quality": 0.4,
                "transfer_quality": 0.25,
            },
            "metacognition": {"self_reported_confidence": 0.72},
            "temporal_behavior": {"total_response_time_seconds": 72, "idle_time_seconds": 18},
            "hint_behavior": {"hint_count": 1, "max_hint_level": "contrast_hint", "improvement_after_hint": 0.14},
            "modality_signals": {"visual_interpretation": 0.66, "text_comprehension": 0.48, "typed_explanation": 0.42},
            "affective_behavior": {"persistence": 0.68, "dropoff_risk": 0.22},
            "intervention_trace": {"selected_next_mode": "visual_contrast", "did_improve_after_hint": True},
            "memory_state": {"encoding_strength": 0.42, "retrieval_success": False},
        },
        {
            "identity": {"event_id": "evt-typed-002", "session_id": "demo-session", "learner_id": "demo-learner"},
            "learning_context": {
                "objective": "understand electric potential and solve transfer problems",
                "domain": "Physics",
                "topic": "Electrostatics",
                "concepts": ["electric potential", "potential energy"],
                "difficulty": 0.56,
                "bloom_level": "apply",
            },
            "activity": {"stage": "worked_example_checkpoint", "mode": "typed_explanation", "activity_type": "explain_next_step"},
            "response_quality": {"score": 0.32, "correctness": "incorrect", "raw_response": "potential is force per charge"},
            "reasoning_signals": {
                "error_type": "concept_substitution",
                "misconception": "confuses potential with electric field",
                "missing_prerequisite": "work per unit charge",
                "step_order_quality": 0.25,
                "causal_link_quality": 0.15,
                "transfer_quality": 0.12,
            },
            "metacognition": {"self_reported_confidence": 0.82},
            "temporal_behavior": {"total_response_time_seconds": 64, "idle_time_seconds": 18, "revision_count": 2},
            "hint_behavior": {"hint_count": 2, "max_hint_level": "step_hint", "improvement_after_hint": 0.04},
            "modality_signals": {"typed_explanation": 0.28, "symbolic_reasoning": 0.31, "visual_interpretation": 0.58},
            "affective_behavior": {"persistence": 0.62, "dropoff_risk": 0.28},
            "intervention_trace": {"selected_next_mode": "visual_contrast", "did_improve_after_hint": False},
            "memory_state": {"encoding_strength": 0.31, "retrieval_success": False},
        },
    ]


def infer_learner_profile(payload: dict[str, Any], graph: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_events = payload.get("learner_events") or payload.get("evidence_events") or []
    if not isinstance(raw_events, list):
        raw_events = []
    raw_events, ignored_event_count = _filter_events_for_graph(raw_events, graph)

    supplied_profile = payload.get("learner_profile") if isinstance(payload.get("learner_profile"), dict) else {}
    if not raw_events and not supplied_profile:
        return {
            "profile_available": False,
            "source": "cold_start_prior",
            "anchor_mix": {"high_support": 0.34, "balanced": 0.43, "advanced": 0.23},
            "dominant_anchor": "balanced",
            "confidence": "low",
            "concept_mastery": {},
            "skill_dimensions": DEFAULT_SKILLS,
            "intervention_effectiveness": {},
            "strongest_signals": [],
            "weakest_signals": [],
            "current_misconceptions": [],
            "event_count": 0,
            "ignored_event_count": ignored_event_count,
            "guidance": "No learner evidence was supplied. Generate the first bundle from content structure, then infer personalization from embedded checks.",
            "telemetry_schema": build_telemetry_schema(),
        }

    concept_scores: dict[str, list[float]] = defaultdict(list)
    skill_scores: dict[str, list[float]] = defaultdict(list)
    interventions: dict[str, list[float]] = defaultdict(list)
    misconceptions: list[str] = []
    event_scores: list[float] = []
    confidences: list[float] = []
    hint_counts: list[float] = []

    for event in raw_events:
        if not isinstance(event, dict):
            continue
        score = _event_score(event)
        confidence = _confidence(event)
        event_scores.append(score)
        confidences.append(confidence)
        hint_counts.append(_clamp(_nested(event, "hint_behavior", "hint_count", default=0), 0, 5))
        for concept in _concepts_from_event(event):
            concept_scores[concept].append(score)
        for key, value in _skill_values_from_event(event).items():
            skill_scores[key].append(value)
        misconception = _nested(event, "reasoning_signals", "misconception", default="")
        if misconception and misconception not in misconceptions:
            misconceptions.append(str(misconception))
        selected_mode = _nested(event, "intervention_trace", "selected_next_mode", default="")
        if selected_mode:
            improved = _nested(event, "intervention_trace", "did_improve_after_hint", default=None)
            improvement = _nested(event, "hint_behavior", "improvement_after_hint", default=0)
            interventions[str(selected_mode)].append(_clamp(0.55 + (0.2 if improved else -0.05) + float(improvement or 0)))

    skill_dimensions = dict(DEFAULT_SKILLS)
    for key, values in skill_scores.items():
        skill_dimensions[key] = round(mean(values), 3)

    concept_mastery = {
        concept: round(mean(values), 3)
        for concept, values in sorted(concept_scores.items(), key=lambda item: mean(item[1]))
    }

    avg_score = mean(event_scores) if event_scores else _clamp(supplied_profile.get("baseline_score", 0.5))
    avg_hint = mean(hint_counts) if hint_counts else 1.0
    avg_conf_gap = mean(abs(score - confidence) for score, confidence in zip(event_scores, confidences)) if event_scores else 0.25
    transfer = skill_dimensions.get("transfer", 0.5)
    hint_independence = skill_dimensions.get("hint_independence", 0.5)

    anchor_raw = {
        "high_support": (1 - avg_score) * 0.55 + min(1.0, avg_hint / 3) * 0.25 + avg_conf_gap * 0.2,
        "balanced": 0.35 + (1 - abs(avg_score - 0.58)) * 0.25 + (1 - avg_conf_gap) * 0.15,
        "advanced": avg_score * 0.45 + transfer * 0.3 + hint_independence * 0.25,
    }
    if supplied_profile.get("anchor_mix") and isinstance(supplied_profile["anchor_mix"], dict):
        for anchor, value in supplied_profile["anchor_mix"].items():
            if anchor in anchor_raw:
                anchor_raw[anchor] = (anchor_raw[anchor] + _clamp(value)) / 2

    anchor_mix = _normalize(anchor_raw)
    dominant_anchor = max(anchor_mix, key=anchor_mix.get)
    sorted_skills = sorted(skill_dimensions.items(), key=lambda item: item[1])

    return {
        "profile_available": bool(raw_events or supplied_profile),
        "source": "optional_feed_and_embedded_evidence" if raw_events else "optional_profile_seed",
        "anchor_mix": anchor_mix,
        "dominant_anchor": dominant_anchor,
        "confidence": "high" if len(raw_events) >= 5 else "medium" if raw_events else "low",
        "concept_mastery": concept_mastery,
        "skill_dimensions": skill_dimensions,
        "intervention_effectiveness": {
            mode: round(mean(values), 3)
            for mode, values in sorted(interventions.items(), key=lambda item: mean(item[1]), reverse=True)
        },
        "strongest_signals": [name for name, _value in sorted_skills[-4:]][::-1],
        "weakest_signals": [name for name, _value in sorted_skills[:4]],
        "current_misconceptions": misconceptions[:5],
        "event_count": len(raw_events),
        "ignored_event_count": ignored_event_count,
        "guidance": _guidance_for_anchor(dominant_anchor),
        "telemetry_schema": build_telemetry_schema(),
    }


def _guidance_for_anchor(anchor: str) -> str:
    if anchor == "high_support":
        return "Use prerequisite repair, shorter segments, worked examples, visual contrasts, and early review checks."
    if anchor == "advanced":
        return "Use compressed source notes, transfer cases, roleplay ambiguity, and later review unless retrieval fails."
    return "Use balanced source notes, mixed checks, teach-back prompts, and moderate review spacing."


def compress_for_llm(
    objective: str,
    learner_profile: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "instruction": "Generate the next learning plan from engine analytics and retrieved source chunks. Do not invent unsupported facts. Do not label the learner as a fixed visual/audio/text type.",
        "learning_objective": objective,
        "learner_state_summary": {
            "profile_available": learner_profile.get("profile_available", False),
            "dominant_anchor": learner_profile.get("dominant_anchor"),
            "anchor_mix": learner_profile.get("anchor_mix", {}),
            "strongest_signals": learner_profile.get("strongest_signals", []),
            "weakest_signals": learner_profile.get("weakest_signals", []),
            "current_misconceptions": learner_profile.get("current_misconceptions", []),
            "concept_mastery": learner_profile.get("concept_mastery", {}),
            "intervention_effectiveness": learner_profile.get("intervention_effectiveness", {}),
            "confidence": learner_profile.get("confidence", "low"),
        },
        "retrieved_source_chunks": [
            {
                "id": chunk["id"],
                "source_title": chunk["source_title"],
                "location": f"{chunk.get('start', '')}-{chunk.get('end', '')}".strip("-"),
                "concepts": chunk.get("concepts", []),
                "text": chunk.get("text", "")[:650],
                "selected_because": chunk.get("selected_because", ""),
            }
            for chunk in retrieved_chunks[:8]
        ],
        "constraints": constraints or {},
        "required_output_schema": [
            "next_learning_plan",
            "personalized_notes",
            "mind_map_changes",
            "video_or_source_sections",
            "roleplay_or_voice_task",
            "hint_ladder",
            "micro_assessment",
            "concept_diagrams",
            "flowcharts",
            "adaptive_quiz_plan",
            "reteaching_plan",
            "forgetting_curve_notes",
            "what_evidence_to_collect_next",
        ],
    }
