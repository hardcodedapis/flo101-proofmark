from __future__ import annotations

from dataclasses import dataclass

from .schema import EvaluationRequest


@dataclass(frozen=True)
class RubricDimension:
    name: str
    weight: float
    description: str
    signals: tuple[str, ...]


DEFAULT_RUBRIC: tuple[RubricDimension, ...] = (
    RubricDimension(
        name="Goal fit",
        weight=0.22,
        description="The artifact directly addresses the learner goal and expected output.",
        signals=("goal", "objective", "user", "problem", "audience", "outcome"),
    ),
    RubricDimension(
        name="Reasoning and evidence",
        weight=0.24,
        description="Claims are supported with reasoning, examples, constraints, or measurable evidence.",
        signals=("because", "evidence", "example", "data", "metric", "tested", "why"),
    ),
    RubricDimension(
        name="Execution detail",
        weight=0.22,
        description="The work includes concrete steps, implementation detail, and enough specificity to verify.",
        signals=("step", "implemented", "test", "check", "acceptance", "deploy", "measure"),
    ),
    RubricDimension(
        name="Reflection and tradeoffs",
        weight=0.16,
        description="The artifact identifies risks, limitations, alternatives, or tradeoffs.",
        signals=("tradeoff", "risk", "limitation", "constraint", "failure", "alternative", "cost"),
    ),
    RubricDimension(
        name="Next-step readiness",
        weight=0.16,
        description="The artifact makes the next improvement step obvious and actionable.",
        signals=("next", "improve", "iterate", "todo", "criteria", "follow-up", "ship"),
    ),
)


CODE_RUBRIC_OVERLAY: tuple[RubricDimension, ...] = (
    RubricDimension(
        name="Correctness and tests",
        weight=0.24,
        description="The code appears correct, testable, and accompanied by validation evidence.",
        signals=("test", "assert", "edge", "error", "input", "output", "exception"),
    ),
    RubricDimension(
        name="Maintainability",
        weight=0.16,
        description="The implementation is understandable, scoped, and easy to modify.",
        signals=("function", "class", "readme", "doc", "type", "small", "module"),
    ),
)


def build_rubric(request: EvaluationRequest) -> list[RubricDimension]:
    if request.custom_rubric:
        weight = 1.0 / len(request.custom_rubric)
        return [
            RubricDimension(
                name=name,
                weight=weight,
                description=f"Custom reviewer dimension: {name}.",
                signals=tuple(word.lower() for word in name.split() if len(word) > 3),
            )
            for name in request.custom_rubric
        ]

    if request.artifact_type == "code":
        return [
            DEFAULT_RUBRIC[0],
            CODE_RUBRIC_OVERLAY[0],
            DEFAULT_RUBRIC[2],
            DEFAULT_RUBRIC[3],
            CODE_RUBRIC_OVERLAY[1],
        ]

    return list(DEFAULT_RUBRIC)

