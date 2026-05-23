from __future__ import annotations

from collections import Counter
from typing import Any


def _clean_items(items: list[Any], limit: int = 5) -> list[str]:
    cleaned = []
    seen = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        cleaned.append(value)
        seen.add(value)
        if len(cleaned) == limit:
            break
    return cleaned


def _label(mode: str) -> str:
    return mode.replace("_", " ").title()


def _action(
    mode: str,
    target_concepts: list[str],
    why: str,
    prompt: str,
    success_criteria: list[str],
    fallback: str,
    review_days: int,
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "recommended_mode": mode,
        "label": _label(mode),
        "target_concepts": _clean_items(target_concepts),
        "why": why,
        "prompt": prompt,
        "success_criteria": _clean_items(success_criteria, limit=6),
        "fallback_if_failed": fallback,
        "review_due_in_days": max(1, int(review_days)),
        "routing_confidence": confidence,
    }


def recommend_for_artifact(request: Any, result: dict[str, Any]) -> dict[str, Any]:
    rubric = [item for item in result.get("rubric", []) if isinstance(item, dict)]
    ordered = sorted(rubric, key=lambda item: (int(item.get("score", 0)), -float(item.get("weight", 0))))
    weakest = ordered[0] if ordered else {"name": "proof quality", "score": 1}
    weak_dimensions = [item.get("name", "unknown") for item in ordered if int(item.get("score", 0)) <= 3]
    target_concepts = weak_dimensions[:4] or [weakest.get("name", "proof quality")]
    overall = int(result.get("overall_score", 0))
    next_step = result.get("next_best_step", {}) if isinstance(result.get("next_best_step"), dict) else {}
    learning_loop = result.get("learning_loop", {}) if isinstance(result.get("learning_loop"), dict) else {}
    review_days = int(learning_loop.get("next_review_in_days", 3) or 3)
    confidence = result.get("reliability", {}).get("confidence", "medium")

    if overall < 50 or int(weakest.get("score", 1)) <= 2:
        mode = "guided_rebuild"
        why = f"The weakest proof signal is {weakest.get('name', 'unknown')}; the artifact needs structured rebuilding before another broad review."
        prompt = (
            f"Rebuild the section for {target_concepts[0]} from scratch. State the claim, add concrete evidence, "
            "then add one check a reviewer can use to verify it."
        )
        fallback = "decompose_into_examples"
    elif weak_dimensions:
        mode = "targeted_revision"
        why = f"The artifact is viable, but {', '.join(target_concepts[:2])} still limits proof quality."
        prompt = next_step.get("instructions") or "Revise the weakest dimension with one example, one check, and one explicit tradeoff."
        fallback = "guided_rebuild"
    else:
        mode = "transfer_challenge"
        why = "The current artifact is strong enough to test whether the skill transfers to a different context."
        prompt = "Apply the same skill to a new scenario and preserve evidence for the same rubric dimensions."
        fallback = "targeted_revision"

    return _action(
        mode,
        target_concepts,
        why,
        prompt,
        next_step.get("acceptance_criteria")
        or [
            "The target claim is explicit.",
            "Visible evidence supports the claim.",
            "A reviewer can verify the improvement without hidden context.",
        ],
        fallback,
        review_days,
        str(confidence),
    )


def recommend_for_pcm(analysis: dict[str, Any]) -> dict[str, Any]:
    question_results = [
        item for item in analysis.get("question_results", [])
        if isinstance(item, dict)
    ]
    weak = [item for item in question_results if float(item.get("score", 0)) < 0.72]
    strong = [item for item in question_results if float(item.get("score", 0)) >= 0.72]
    overall = int(analysis.get("overall_score", 0))
    review_plan = analysis.get("review_plan", {}) if isinstance(analysis.get("review_plan"), dict) else {}
    review_days = int(review_plan.get("next_retake_in_days", 3) or 3)
    priority_gaps = analysis.get("jee_readiness", {}).get("priority_gaps", [])

    weak_concepts = [
        f"{item.get('subject', 'Subject')} / {item.get('chapter', 'Chapter')} / {item.get('subtopic', 'Concept')}"
        for item in weak
    ]
    target_concepts = _clean_items(list(priority_gaps) + weak_concepts, limit=5)
    if not target_concepts:
        target_concepts = [
            f"{item.get('subject', 'Subject')} / {item.get('chapter', 'Chapter')} / {item.get('subtopic', 'Concept')}"
            for item in strong[:3]
        ] or ["mixed PCM transfer"]

    weak_subjects = Counter(str(item.get("subject", "unknown")) for item in weak)
    weak_subject_count = len([subject for subject, count in weak_subjects.items() if count])
    written = [item for item in question_results if item.get("type") == "written"]
    mcq = [item for item in question_results if item.get("type") == "mcq"]
    written_avg = sum(float(item.get("score", 0)) for item in written) / max(len(written), 1)
    mcq_avg = sum(float(item.get("score", 0)) for item in mcq) / max(len(mcq), 1)

    if overall < 45:
        mode = "tutor_drill"
        why = "The diagnostic shows broad weak evidence, so the learner needs guided concept repair before another mixed test."
        prompt = f"Teach the prerequisite idea for {target_concepts[0]}, then ask two short checks and one fresh variant."
        fallback = "micro_retest"
        criteria = [
            "Learner states the rule or definition without hints.",
            "Learner solves a same-concept variant.",
            "Learner explains why the wrong option or missing idea was wrong.",
        ]
    elif written_avg + 0.18 < mcq_avg:
        mode = "teach_back"
        why = "Selected-answer performance is stronger than written explanation, so the next action should test explanation quality."
        prompt = f"Explain {target_concepts[0]} aloud or in writing, then apply it to a new example without seeing the answer."
        fallback = "tutor_drill"
        criteria = [
            "Explanation uses the key concept vocabulary.",
            "Reasoning includes the cause or formula, not just the final answer.",
            "A fresh variant is answered without copying the original question.",
        ]
    elif weak_subject_count >= 2:
        mode = "scenario_practice"
        why = "Weakness spans multiple subjects or domains, so the learner needs transfer practice rather than isolated recall."
        prompt = "Generate a mixed PCM case that combines the top weak concepts and requires step-by-step reasoning."
        fallback = "tutor_drill"
        criteria = [
            "Learner identifies which subject each step belongs to.",
            "Learner connects at least two concepts in one solution path.",
            "Learner explains the final answer and the rejected alternatives.",
        ]
    elif weak:
        mode = "micro_retest"
        why = "The weakness is concentrated enough for a short adaptive retest with fresh variants and limited repeats."
        prompt = f"Create a short retest around {target_concepts[0]} with one repeated error audit and two fresh variants."
        fallback = "teach_back"
        criteria = [
            "Repeated missed item is corrected with reasoning.",
            "Fresh same-concept variant is solved.",
            "Next retention review is scheduled.",
        ]
    else:
        mode = "transfer_challenge"
        why = "The attempt shows strong proof, so the next step should test transfer and retention rather than more of the same."
        prompt = "Create a harder mixed PCM challenge using retained concepts in a new context."
        fallback = "micro_retest"
        criteria = [
            "Learner solves a new-context problem.",
            "Learner explains why the same concept applies.",
            "Retention check is scheduled before predicted decay.",
        ]

    return _action(
        mode,
        target_concepts,
        why,
        prompt,
        criteria,
        fallback,
        review_days,
        "high" if question_results else "low",
    )
