from __future__ import annotations

import json

from .rubric import RubricDimension
from .schema import EvaluationRequest


SYSTEM_PROMPT = """You are ProofMark, a strict proof-of-work evaluator for a guided skilling platform.

Evaluate the learner artifact as evidence of applied skill, not as generic writing.
Use the provided rubric and keep scores on a 1-5 integer scale.
Ground every judgment in visible artifact evidence. If evidence is missing, say so.

Evaluation principles:
- Use a form-filling rubric style inspired by G-Eval: score each dimension separately before writing the final verdict.
- Use customized rubric and reference material when provided, following the Prometheus evaluator pattern.
- Mitigate LLM-as-judge bias: do not reward verbosity, confidence, polish, or model-like phrasing unless it proves the rubric dimension.
- Follow formative feedback theory: distinguish feed-up (goal), feedback (current evidence), and feed-forward (next improvement).
- Prefer actionable task/process/self-regulation feedback over praise.

Return valid JSON only. Do not include markdown fences.
"""


def build_user_prompt(
    request: EvaluationRequest,
    rubric: list[RubricDimension],
    baseline: dict,
) -> str:
    rubric_payload = [
        {
            "name": item.name,
            "weight": item.weight,
            "description": item.description,
        }
        for item in rubric
    ]
    expected_shape = {
        "overall_score": "integer 0-100",
        "verdict": "short string",
        "rubric": [
            {
                "name": "string",
                "score": "integer 1-5",
                "weight": "number",
                "evidence": "artifact quote or paraphrase",
                "feedback": "dimension-specific feedback",
                "risk_if_ignored": "why this matters",
            }
        ],
        "missing_gaps": ["strings"],
        "next_best_step": {
            "title": "string",
            "why": "string",
            "instructions": "string",
            "acceptance_criteria": ["strings"],
        },
        "proof_of_work": {
            "evidence_observed": ["strings"],
            "evidence_missing": ["strings"],
            "verification_questions": ["strings"],
        },
        "evidence_map": [
            {
                "dimension": "rubric dimension name",
                "claim": "what the artifact would need to prove",
                "status": "supported|partial|missing",
                "evidence": "visible evidence from the artifact, or empty string",
                "missing_proof": "proof needed to verify the claim, or empty string",
                "verification_question": "question a reviewer can ask to verify the claim",
            }
        ],
        "feedback_loop": {
            "feed_up_goal": "what good work must prove",
            "feed_back_current_state": "what the artifact currently proves",
            "feed_forward_next_action": "the next concrete action",
        },
        "judge_diagnostics": {
            "bias_checks": ["strings"],
            "calibration_notes": ["strings"],
        },
        "reliability": {
            "confidence": "low|medium|high",
            "checks_passed": ["strings"],
            "warnings": ["objects"],
        },
    }
    return "\n\n".join(
        [
            f"Learner goal: {request.learner_goal}",
            f"Learner level: {request.level}",
            f"Learner id: {request.learner_id}",
            f"Prior mastery estimate: {request.prior_mastery}",
            f"Expected output: {request.output_goal}",
            f"Artifact type: {request.artifact_type}",
            "Rubric JSON:",
            json.dumps(rubric_payload, indent=2),
            "Baseline deterministic evaluation to use as a calibration point:",
            json.dumps(baseline, indent=2),
            "Use the baseline only as calibration. You may disagree when the artifact evidence warrants it, but keep the same rubric dimensions and explain gaps from visible evidence.",
            "Required JSON shape:",
            json.dumps(expected_shape, indent=2),
            "Learner artifact:",
            request.artifact,
        ]
    )
