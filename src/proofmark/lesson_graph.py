from __future__ import annotations

import math
from typing import Any


def build_lesson_graph(
    graph: dict[str, Any],
    bundle: dict[str, Any],
    dynamic_case: dict[str, Any],
    learner_profile: dict[str, Any],
    source_analysis: dict[str, Any],
    roadmap: dict[str, Any],
    model_generation: dict[str, Any],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = constraints if isinstance(constraints, dict) else {}
    assets = model_generation.get("assets", {}) if isinstance(model_generation, dict) else {}
    insights = source_analysis.get("source_insights", []) if isinstance(source_analysis, dict) else []
    timeline = source_analysis.get("video_timeline", []) if isinstance(source_analysis, dict) else []
    video_learning_plan = source_analysis.get("video_learning_plan", {}) if isinstance(source_analysis, dict) else {}
    student_video_lesson = source_analysis.get("student_video_lesson", {}) if isinstance(source_analysis, dict) else {}
    visual_cues = source_analysis.get("visual_learning_cues", []) if isinstance(source_analysis, dict) else []
    concept_diagrams = source_analysis.get("concept_diagrams", []) if isinstance(source_analysis, dict) else []
    flowcharts = source_analysis.get("flowcharts", []) if isinstance(source_analysis, dict) else []
    adaptive_quiz_blueprint = (
        source_analysis.get("adaptive_quiz_blueprint", []) if isinstance(source_analysis, dict) else []
    )
    reteaching_plan = source_analysis.get("reteaching_plan", []) if isinstance(source_analysis, dict) else []

    pages = [
        _media_page(graph, bundle, insights, timeline, video_learning_plan, student_video_lesson, assets),
        _source_notes_page(graph, bundle, insights, assets),
        _checkpoint_page(bundle, source_analysis, learner_profile),
        _visual_page(graph, bundle, visual_cues, concept_diagrams, flowcharts, assets),
        _practice_page(bundle, source_analysis, roadmap, learner_profile, adaptive_quiz_blueprint, reteaching_plan),
        _case_page(dynamic_case, learner_profile),
        _revision_page(roadmap, learner_profile, reteaching_plan, adaptive_quiz_blueprint),
    ]
    return {
        "status": "source_analyzed_lesson_graph",
        "planner_provider": source_analysis.get("provider", "local"),
        "planner_status": source_analysis.get("status", "deterministic_fallback"),
        "learning_objective": graph.get("learning_objective", ""),
        "time_budget_minutes": int(constraints.get("time_budget_minutes", 30) or 30),
        "cold_start_personalization": (
            "research_priors_until_evidence"
            if not learner_profile.get("profile_available")
            else "profile_aware"
        ),
        "page_order": [page["id"] for page in pages],
        "pages": pages,
        "adaptive_rule": (
            "After each page, checkpoint evidence updates the learner model. RAG supplies source grounding, "
            "then the LLM generates the next notes, visual repair, practice mix, or revision check."
        ),
        "rag_role": "Ground source facts, source sections, examples, questions, and generated learning assets.",
        "learner_model_role": "Select difficulty, support level, modality intervention, spacing, and evidence to collect next.",
        "content_design_rules": [
            "Segment one idea per section.",
            "Signal definitions, traps, formulas, and checks with clear labels.",
            "Remove PDF artifacts, navigation text, and retrieval noise from learner pages.",
            "Place a low-stakes retrieval check after every short lesson segment.",
            "Use worked-example prompts that ask why a step follows.",
        ],
    }


def _media_page(
    graph: dict[str, Any],
    bundle: dict[str, Any],
    insights: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    video_learning_plan: dict[str, Any],
    student_video_lesson: dict[str, Any],
    assets: dict[str, Any],
) -> dict[str, Any]:
    source_cards = [_source_card(insight) for insight in insights]
    if not source_cards:
        source_cards = [
            {
                "source_id": source.get("id", ""),
                "title": source.get("title", "Source"),
                "type": source.get("type", "source"),
                "url": source.get("url", ""),
                "media_role": source.get("type", "source"),
                "summary": str(source.get("text", ""))[:260],
                "concepts": [],
                "sections": [],
                "bullets": [],
            }
            for source in graph.get("sources", [])[:4]
        ]

    notes = _notes_below(bundle, assets)
    return {
        "id": "source_media_lesson",
        "type": "media_lesson",
        "title": "Video breakdown and source overview",
        "intent": "Extract the important ideas from supplied videos, PDFs, URLs, and notes before asking the learner to test.",
        "source_cards": source_cards,
        "video_timeline": timeline,
        "video_learning_plan": video_learning_plan,
        "student_video_lesson": _merge_student_video_lesson(student_video_lesson, assets.get("student_study_pack", {})),
        "notes_below": notes,
        "memory_cards": _memory_cards(graph, assets),
        "completion_check": {
            "prompt": (
                student_video_lesson.get("tiny_check", {}).get("prompt")
                if isinstance(student_video_lesson.get("tiny_check"), dict)
                else "Explain the main idea in two lines before moving on."
            ),
            "evidence_collected": ["source_grounding", "confidence", "time_to_first_action", "confusing_section"],
        },
    }


def _source_notes_page(
    graph: dict[str, Any],
    bundle: dict[str, Any],
    insights: list[dict[str, Any]],
    assets: dict[str, Any],
) -> dict[str, Any]:
    non_video_sources = [
        _source_card(insight)
        for insight in insights
        if insight.get("media_role") not in {"video", "transcript"}
    ]
    if not non_video_sources:
        non_video_sources = [
            {
                "source_id": source.get("id", ""),
                "title": source.get("title", "Source"),
                "type": source.get("type", "source"),
                "url": source.get("url", ""),
                "media_role": source.get("type", "source"),
                "summary": _source_summary(source),
                "concepts": [],
                "sections": [],
                "bullets": [],
            }
            for source in graph.get("sources", [])[:4]
            if not source.get("url") or "youtu" not in str(source.get("url", "")).lower()
        ]
    return {
        "id": "source_notes",
        "type": "source_notes",
        "title": "Read the source notes",
        "intent": "Convert PDFs, docs, URLs, and pasted notes into clean sections before asking the learner to practice.",
        "source_cards": non_video_sources,
        "notes_below": _notes_below(bundle, assets),
        "memory_cards": _memory_cards(graph, assets),
        "readability_rules": [
            "one concept per block",
            "definition before formula",
            "trap before practice",
            "short recall check after reading",
        ],
        "completion_check": {
            "prompt": "Write one definition, one trap, and one source-backed example.",
            "evidence_collected": ["text_comprehension", "source_grounding", "precision", "confidence"],
        },
    }


def _merge_student_video_lesson(
    lesson: dict[str, Any],
    model_pack: dict[str, Any],
) -> dict[str, Any]:
    lesson = lesson if isinstance(lesson, dict) else {}
    model_pack = model_pack if isinstance(model_pack, dict) else {}
    merged = dict(lesson)
    if model_pack.get("one_minute_summary") and not merged.get("one_minute_summary"):
        merged["one_minute_summary"] = model_pack["one_minute_summary"]
    if model_pack.get("key_facts") and not merged.get("key_facts"):
        merged["key_facts"] = [
            {"fact": item, "why_it_matters": "Use this in the next practice question."}
            for item in model_pack.get("key_facts", [])[:6]
        ]
    if model_pack.get("formula_cards") and not merged.get("formula_cards"):
        merged["formula_cards"] = model_pack.get("formula_cards", [])[:5]
    if model_pack.get("things_to_remember") and not merged.get("things_to_remember"):
        merged["things_to_remember"] = model_pack.get("things_to_remember", [])[:6]
    if model_pack.get("tips_and_tricks") and not merged.get("tips_and_tricks"):
        merged["tips_and_tricks"] = model_pack.get("tips_and_tricks", [])[:6]
    if model_pack.get("shortcuts") and not merged.get("shortcuts"):
        merged["shortcuts"] = model_pack.get("shortcuts", [])[:6]
    if model_pack.get("mind_map_branches") and not merged.get("mindmap"):
        merged["mindmap"] = {
            "center": lesson.get("mindmap", {}).get("center", "main idea")
            if isinstance(lesson.get("mindmap"), dict)
            else "main idea",
            "branches": [
                {"label": str(item).split("->", 1)[0].strip(), "points": [str(item).split("->", 1)[-1].strip()]}
                for item in model_pack.get("mind_map_branches", [])[:6]
            ],
        }
    if model_pack.get("diagram_ideas") and not merged.get("diagram_prompts"):
        merged["diagram_prompts"] = [
            {"title": "Diagram idea", "description": item, "steps": []}
            for item in model_pack.get("diagram_ideas", [])[:4]
        ]
    if model_pack.get("voice_over_script") and not merged.get("audio_overview_script"):
        merged["audio_overview_script"] = model_pack.get("voice_over_script", "")
    return merged


def _checkpoint_page(
    bundle: dict[str, Any],
    source_analysis: dict[str, Any],
    learner_profile: dict[str, Any],
) -> dict[str, Any]:
    questions = source_analysis.get("questions_to_ask") or bundle.get("checkpoint_questions", [])
    existing_ids = set()
    normalized = []
    for index, question in enumerate(questions[:6], start=1):
        if not isinstance(question, dict):
            continue
        qid = str(question.get("id") or f"checkpoint-{index}")
        if qid in existing_ids:
            qid = f"{qid}-{index}"
        existing_ids.add(qid)
        normalized.append(
            {
                "id": qid,
                "type": question.get("type", "typed_explanation"),
                "prompt": question.get("prompt", ""),
                "captures": question.get("captures", ["correctness", "confidence", "reasoning"]),
                "after_answer_rule": _after_answer_rule(question, learner_profile),
            }
        )
    return {
        "id": "notes_checkpoint",
        "type": "checkpoint",
        "title": "Checkpoint after the first lesson",
        "intent": "Learning and evidence collection happen together. This page estimates what to show next.",
        "questions": normalized,
        "evidence_schema_focus": [
            "correctness",
            "confidence_calibration",
            "hint_count",
            "response_time",
            "source_grounding",
            "visual_interpretation",
            "typed_explanation",
            "spoken_explanation",
        ],
    }


def _visual_page(
    graph: dict[str, Any],
    bundle: dict[str, Any],
    visual_cues: list[dict[str, Any]],
    concept_diagrams: list[dict[str, Any]],
    flowcharts: list[dict[str, Any]],
    assets: dict[str, Any],
) -> dict[str, Any]:
    nodes = bundle.get("concept_map", {}).get("nodes", [])
    flow_steps = []
    sequence = bundle.get("embedded_evidence_sequence", [])
    for index, stage in enumerate(sequence[:5], start=1):
        flow_steps.append(
            {
                "step": index,
                "label": str(stage.get("stage", "step")).replace("_", " "),
                "body": stage.get("learner_action", ""),
                "evidence": stage.get("signals_collected", []),
                "adaptive_use": stage.get("adaptive_use", ""),
            }
        )
    for change in assets.get("mind_map_changes", [])[:2]:
        flow_steps.append(
            {
                "step": len(flow_steps) + 1,
                "label": "model map change",
                "body": change,
                "evidence": ["LLM generated after RAG and learner state"],
                "adaptive_use": "Use if the learner fails the checkpoint.",
            }
        )
    return {
        "id": "visual_repair",
        "type": "visual_repair",
        "title": "Mind map and flowchart repair",
        "intent": "Turn the first checkpoint into visual cues, concept contrasts, and a cleaner reasoning path.",
        "mind_map_nodes": [
            {
                "id": node.get("id", ""),
                "label": node.get("label", ""),
                "difficulty": node.get("difficulty", 0.5),
                "bloom_level": node.get("bloom_level", "understand"),
                "prerequisites": node.get("prerequisites", []),
                "common_confusions": node.get("common_confusions", []),
            }
            for node in nodes
        ],
        "flow_steps": flow_steps,
        "visual_cues": visual_cues,
        "concept_diagrams": concept_diagrams or assets.get("concept_diagrams", []),
        "flowcharts": flowcharts or assets.get("flowcharts", []),
        "diagram_prompt": _diagram_prompt(graph),
    }


def _practice_page(
    bundle: dict[str, Any],
    source_analysis: dict[str, Any],
    roadmap: dict[str, Any],
    learner_profile: dict[str, Any],
    adaptive_quiz_blueprint: list[dict[str, Any]],
    reteaching_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    questions = source_analysis.get("questions_to_ask") or bundle.get("checkpoint_questions", [])
    if learner_profile.get("profile_available"):
        mix_rule = "Use more fresh variants for strong concepts and repair-repeat variants for weak concepts."
    else:
        mix_rule = "Use a balanced first-pass mix, then update after checkpoint evidence."
    retest_quiz_plan = _retest_quiz_plan(questions, adaptive_quiz_blueprint, learner_profile)
    return {
        "id": "practice_mix",
        "type": "practice",
        "title": "Mixed quiz and written practice",
        "intent": "Practice should not repeat mechanically. It should mix old traps with new variants.",
        "questions": questions[:5],
        "mix_rule": mix_rule,
        "adaptive_quiz_blueprint": adaptive_quiz_blueprint,
        "retest_quiz_plan": retest_quiz_plan,
        "reteach_before_retry": _prioritized_reteaching(reteaching_plan, learner_profile)[:3],
        "next_methods": roadmap.get("next_learning_methods") or roadmap.get("first_pass_sequence", []),
        "adaptive_retest_policy": {
            "wrong_or_low_confidence": "40-60 percent repeat-style variants plus fresh concept-equivalent questions.",
            "right_and_confident": "Mostly fresh transfer variants, with a small stability check.",
            "hint_dependent": "Repeat the concept through a different representation before harder practice.",
        },
    }


def _case_page(dynamic_case: dict[str, Any], learner_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "final_dynamic_case",
        "type": "dynamic_case",
        "title": dynamic_case.get("title", "Final dynamic case"),
        "scenario": dynamic_case.get("scenario", ""),
        "constraints": dynamic_case.get("constraints", []),
        "required_output": dynamic_case.get("required_output", {}),
        "rubric": dynamic_case.get("rubric", []),
        "active_variant": dynamic_case.get("personalized_variants", {}).get(
            "active_variant",
            learner_profile.get("dominant_anchor", "balanced"),
        ),
        "updates_learner_model_with": [
            "transfer",
            "integration",
            "source grounding",
            "confidence calibration",
            "retention seed",
        ],
    }


def _revision_page(
    roadmap: dict[str, Any],
    learner_profile: dict[str, Any],
    reteaching_plan: list[dict[str, Any]],
    adaptive_quiz_blueprint: list[dict[str, Any]],
) -> dict[str, Any]:
    review_schedule = roadmap.get("review_schedule", [])
    forgetting_curve = _forgetting_curve(review_schedule, learner_profile)
    prioritized_reteaching = _prioritized_reteaching(reteaching_plan, learner_profile)
    return {
        "id": "revision_loop",
        "type": "revision",
        "title": "Personalized revision loop",
        "intent": "Use forgetting-curve timing plus learner-specific evidence instead of a static calendar.",
        "review_schedule": review_schedule,
        "forgetting_curve": forgetting_curve,
        "next_retake": _next_retake(review_schedule, forgetting_curve),
        "reteaching_plan": prioritized_reteaching,
        "adaptive_quiz_blueprint": adaptive_quiz_blueprint,
        "profile_anchor": learner_profile.get("dominant_anchor", "balanced"),
        "learner_signals": {
            "weakest": learner_profile.get("weakest_signals", []),
            "strongest": learner_profile.get("strongest_signals", []),
            "misconceptions": learner_profile.get("current_misconceptions", []),
        },
        "after_review_rule": (
            "Every retest compares against the previous attempt, updates concept mastery and retention stability, "
            "then asks the model for the next grounded bundle. Missed concepts route through reteaching before the next quiz variant."
        ),
    }


def _retest_quiz_plan(
    questions: list[dict[str, Any]],
    adaptive_quiz_blueprint: list[dict[str, Any]],
    learner_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    concepts = [row.get("concept", "") for row in adaptive_quiz_blueprint if row.get("concept")]
    mastery = learner_profile.get("concept_mastery", {}) if isinstance(learner_profile.get("concept_mastery"), dict) else {}
    if mastery:
        concepts = [concept for concept, _score in sorted(mastery.items(), key=lambda item: item[1])] + concepts
    concepts = _unique_text(concepts)[:4] or ["core concept"]
    base_question = next((question for question in questions if isinstance(question, dict)), {})
    profile_available = bool(learner_profile.get("profile_available"))
    plan = []
    for index, concept in enumerate(concepts, start=1):
        score = float(mastery.get(concept, 0.42 if not profile_available else 0.5))
        repeat_share = 0.6 if score < 0.45 else 0.5 if score < 0.68 else 0.4
        fresh_share = round(1 - repeat_share, 2)
        if score < 0.45:
            trigger = "missed or fragile concept"
            reason = "Repair first, then retest with a changed surface form."
        elif score < 0.68:
            trigger = "partial mastery"
            reason = "Use one familiar trap plus fresh transfer."
        else:
            trigger = "stability check"
            reason = "Mostly fresh variants; retain one light repeat to verify memory."
        plan.append(
            {
                "id": f"retest-{index}-repeat",
                "concept": concept,
                "variant_type": "repeat_style",
                "mix": f"{round(repeat_share * 100)}% repeat-style / {round(fresh_share * 100)}% fresh",
                "prompt": f"Retry {concept} with changed wording, numbers, or representation.",
                "reason": reason,
                "trigger": trigger,
                "source_prompt": base_question.get("prompt", ""),
            }
        )
        plan.append(
            {
                "id": f"retest-{index}-fresh",
                "concept": concept,
                "variant_type": "fresh_variant",
                "mix": f"{round(repeat_share * 100)}% repeat-style / {round(fresh_share * 100)}% fresh",
                "prompt": f"Solve a new {concept} question that tests the same idea without copying the old surface.",
                "reason": "Checks whether the learner learned the concept, not the answer pattern.",
                "trigger": "after reteach or after a correct answer",
                "source_prompt": "",
            }
        )
        if len(plan) >= 6:
            break
    return plan


def _forgetting_curve(review_schedule: list[dict[str, Any]], learner_profile: dict[str, Any]) -> list[dict[str, Any]]:
    anchor = learner_profile.get("dominant_anchor", "balanced")
    skills = learner_profile.get("skill_dimensions", {}) if isinstance(learner_profile.get("skill_dimensions"), dict) else {}
    retention_skill = float(skills.get("retention_stability", 0.5))
    rows = []
    for row in review_schedule[:5]:
        mastery = float(row.get("mastery_estimate", 0.42))
        review_day = int(row.get("review_in_days", 1) or 1)
        stability = _stability_days(mastery, retention_skill, anchor)
        start_retention = min(0.97, max(0.58, 0.56 + mastery * 0.42))
        day_points = sorted({0, 1, 2, 3, 5, 7, 11, 15, review_day, min(21, review_day * 2)})
        points = []
        for day in day_points:
            retention = start_retention * math.pow(2, -max(day, 0) / stability)
            points.append(
                {
                    "day": day,
                    "retention": round(max(0.08, min(0.99, retention)), 3),
                }
            )
        predicted = next((point["retention"] for point in points if point["day"] == review_day), points[0]["retention"])
        rows.append(
            {
                "concept": row.get("concept", "target concept"),
                "mastery_estimate": round(mastery, 2),
                "personalized_stability_days": round(stability, 2),
                "review_in_days": review_day,
                "review_date": row.get("review_date", ""),
                "predicted_retention_at_review": round(predicted, 3),
                "risk": _retention_risk(predicted, mastery),
                "points": points,
                "retest_mix": "repair-heavy" if mastery < 0.45 else "balanced repeat/fresh" if mastery < 0.68 else "fresh-transfer-heavy",
            }
        )
    return rows


def _stability_days(mastery: float, retention_skill: float, anchor: str) -> float:
    stability = 1.2 + mastery * 7.0 + retention_skill * 3.0
    if anchor == "advanced" and mastery >= 0.68:
        stability += 2.5
    if anchor == "high_support" or mastery < 0.45:
        stability *= 0.72
    return max(0.75, min(18.0, stability))


def _retention_risk(predicted_retention: float, mastery: float) -> str:
    if predicted_retention < 0.55 or mastery < 0.42:
        return "high"
    if predicted_retention < 0.72 or mastery < 0.68:
        return "medium"
    return "low"


def _prioritized_reteaching(
    reteaching_plan: list[dict[str, Any]],
    learner_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    mastery = learner_profile.get("concept_mastery", {}) if isinstance(learner_profile.get("concept_mastery"), dict) else {}
    misconceptions = learner_profile.get("current_misconceptions", [])
    weak = learner_profile.get("weakest_signals", [])
    rows = []
    for item in reteaching_plan:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "target concept"))
        score = float(mastery.get(concept, 0.42 if not learner_profile.get("profile_available") else 0.55))
        priority = "high" if score < 0.45 or misconceptions else "medium" if score < 0.68 or weak else "low"
        rows.append(
            {
                **item,
                "priority": priority,
                "mastery_estimate": round(score, 2),
                "learner_evidence": {
                    "weak_signals": weak[:3],
                    "misconceptions": misconceptions[:2],
                },
            }
        )
    if rows:
        order = {"high": 0, "medium": 1, "low": 2}
        return sorted(rows, key=lambda row: (order.get(row["priority"], 3), row.get("mastery_estimate", 1)))
    return [
        {
            "concept": "first weak concept",
            "trigger": "first missed checkpoint or low confidence",
            "mode": "worked_example",
            "explanation": "Show one worked example, ask for a self-explanation, then generate a fresh variant.",
            "next_check": "One typed explanation plus one MCQ with confidence.",
            "priority": "medium",
            "mastery_estimate": 0.5,
            "learner_evidence": {"weak_signals": weak[:3], "misconceptions": misconceptions[:2]},
        }
    ]


def _next_retake(review_schedule: list[dict[str, Any]], forgetting_curve: list[dict[str, Any]]) -> dict[str, Any]:
    if not review_schedule:
        return {}
    curve_by_concept = {row.get("concept"): row for row in forgetting_curve}
    next_row = min(review_schedule, key=lambda row: int(row.get("review_in_days", 999) or 999))
    curve = curve_by_concept.get(next_row.get("concept"), {})
    return {
        "concept": next_row.get("concept", ""),
        "review_in_days": next_row.get("review_in_days", 1),
        "review_date": next_row.get("review_date", ""),
        "risk": curve.get("risk", "medium"),
        "action": "Reteach the weakest concept, then generate a mixed retest with repeat-style and fresh variants.",
    }


def _unique_text(values: list[str]) -> list[str]:
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _source_card(insight: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": insight.get("source_id", ""),
        "title": insight.get("title", "Source"),
        "type": insight.get("type", "source"),
        "url": insight.get("url", ""),
        "media_role": insight.get("media_role", insight.get("type", "source")),
        "summary": insight.get("why_chosen", ""),
        "concepts": insight.get("concepts", []),
        "sections": insight.get("sections", []),
        "bullets": insight.get("bullets", []),
        "visual_cues": insight.get("visual_cues", []),
    }


def _source_summary(source: dict[str, Any]) -> str:
    text = str(source.get("text", "")).strip()
    if not text or text == source.get("url"):
        if source.get("url"):
            return "Open this source as a reference while reading the generated notes."
        return "Use this supplied note as the source for the lesson section."
    return text[:260]


def _notes_below(bundle: dict[str, Any], assets: dict[str, Any]) -> list[dict[str, Any]]:
    notes = []
    for section in bundle.get("guided_notes", {}).get("sections", []):
        if section.get("anchors"):
            body = " ".join(
                f"{anchor.get('concept')}: {anchor.get('definition_or_rule')}"
                for anchor in section.get("anchors", [])
            )
        else:
            body = section.get("body", "")
        notes.append({"title": section.get("title", "Note"), "body": body, "source": "curated_bundle"})
    for index, note in enumerate(assets.get("personalized_notes", [])[:3], start=1):
        notes.append({"title": f"Generated note {index}", "body": note, "source": "model_generation"})
    return notes


def _memory_cards(graph: dict[str, Any], assets: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for concept in graph.get("concepts", [])[:5]:
        cards.append(
            {
                "type": "concept",
                "title": concept.get("name", ""),
                "body": _memory_body(concept),
            }
        )
    for item in assets.get("hint_ladder", [])[:3]:
        cards.append({"type": "hint", "title": item, "body": "Use this only after the learner attempts the checkpoint."})
    return cards[:8]


def _memory_body(concept: dict[str, Any]) -> str:
    prereq = ", ".join(concept.get("prerequisites", [])[:2])
    trap = ", ".join(concept.get("common_confusions", [])[:2])
    parts = []
    if prereq:
        parts.append(f"Prerequisite: {prereq}.")
    if trap:
        parts.append(f"Trap: do not confuse with {trap}.")
    return " ".join(parts) or "Explain it, represent it, then apply it in a new problem."


def _diagram_prompt(graph: dict[str, Any]) -> str:
    concepts = [concept.get("name", "") for concept in graph.get("concepts", [])[:4] if concept.get("name")]
    if not concepts:
        return "Draw definition -> representation -> application -> check."
    return "Draw " + " -> ".join(concepts) + " and mark the common trap separately."


def _after_answer_rule(question: dict[str, Any], learner_profile: dict[str, Any]) -> str:
    qtype = question.get("type", "")
    if qtype == "visual_map":
        return "If edges are wrong, send the learner to visual repair before practice."
    if qtype == "typed_explanation":
        return "If reasoning is vague, generate a source-anchored note and ask for a rewrite."
    if qtype == "voice_or_roleplay":
        return "Use voice as a confidence/composure signal, not as a fixed learning-style label."
    if learner_profile.get("profile_available"):
        return "Update mastery, confidence calibration, and intervention effectiveness."
    return "Use the answer as cold-start evidence for the first learner model update."
