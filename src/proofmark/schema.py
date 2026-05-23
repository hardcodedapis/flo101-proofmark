from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_ARTIFACT_TYPES = {
    "brief",
    "draft",
    "code",
    "case-study",
    "reflection",
    "other",
}

MAX_ARTIFACT_CHARS = 16_000
HARD_MAX_ARTIFACT_CHARS = 80_000


class InputError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }


@dataclass
class EvaluationRequest:
    learner_goal: str
    artifact: str
    artifact_type: str
    level: str
    output_goal: str
    learner_id: str = "anonymous-learner"
    prior_mastery: float = 0.35
    days_since_last_review: float = 0.0
    target_retention: float = 0.85
    custom_rubric: list[str] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len([word for word in self.artifact.split() if word.strip()])


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def validate_payload(payload: dict[str, Any]) -> EvaluationRequest:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")

    artifact = _clean_text(payload.get("artifact"))
    if not artifact:
        raise InputError(
            "empty_artifact",
            "Paste a learner artifact before requesting an evaluation.",
        )

    if len(artifact) > HARD_MAX_ARTIFACT_CHARS:
        raise InputError(
            "artifact_too_large",
            f"Artifact is too large. Keep submissions under {HARD_MAX_ARTIFACT_CHARS:,} characters.",
        )

    warnings: list[dict[str, str]] = []
    if len(artifact) > MAX_ARTIFACT_CHARS:
        artifact = artifact[:MAX_ARTIFACT_CHARS]
        warnings.append(
            {
                "code": "artifact_truncated",
                "message": f"Artifact was truncated to {MAX_ARTIFACT_CHARS:,} characters for evaluation.",
            }
        )

    artifact_type = _clean_text(payload.get("artifact_type") or "brief").lower()
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        supported = ", ".join(sorted(SUPPORTED_ARTIFACT_TYPES))
        raise InputError(
            "unsupported_artifact_type",
            f"Unsupported artifact type '{artifact_type}'. Choose one of: {supported}.",
        )

    learner_goal = _clean_text(payload.get("learner_goal"))
    if not learner_goal:
        learner_goal = "Show progress toward the learner's stated objective."
        warnings.append(
            {
                "code": "missing_goal",
                "message": "No learner goal was provided, so a generic mastery goal was used.",
            }
        )

    level = _clean_text(payload.get("level") or "intermediate")
    output_goal = _clean_text(payload.get("output_goal") or "Improve this artifact enough to show credible proof-of-work.")
    learner_id = _clean_text(payload.get("learner_id") or "anonymous-learner")

    try:
        prior_mastery = float(payload.get("prior_mastery", 0.35))
    except (TypeError, ValueError):
        prior_mastery = 0.35
        warnings.append(
            {
                "code": "invalid_prior_mastery",
                "message": "Prior mastery was invalid, so the default prior of 0.35 was used.",
            }
        )
    prior_mastery = max(0.01, min(0.99, prior_mastery))

    try:
        days_since_last_review = float(payload.get("days_since_last_review", 0.0))
    except (TypeError, ValueError):
        days_since_last_review = 0.0
        warnings.append(
            {
                "code": "invalid_days_since_last_review",
                "message": "Days since last review was invalid, so 0 was used.",
            }
        )
    days_since_last_review = max(0.0, min(365.0, days_since_last_review))

    try:
        target_retention = float(payload.get("target_retention", 0.85))
    except (TypeError, ValueError):
        target_retention = 0.85
        warnings.append(
            {
                "code": "invalid_target_retention",
                "message": "Target retention was invalid, so 0.85 was used.",
            }
        )
    target_retention = max(0.55, min(0.97, target_retention))

    custom_rubric_raw = payload.get("custom_rubric") or []
    custom_rubric: list[str] = []
    if isinstance(custom_rubric_raw, list):
        for item in custom_rubric_raw[:7]:
            text = _clean_text(item)
            if text:
                custom_rubric.append(text[:80])
    elif isinstance(custom_rubric_raw, str):
        custom_rubric = [
            part.strip()[:80]
            for part in custom_rubric_raw.splitlines()
            if part.strip()
        ][:7]

    if custom_rubric_raw and not custom_rubric:
        warnings.append(
            {
                "code": "invalid_custom_rubric",
                "message": "Custom rubric input was ignored because no usable dimensions were found.",
            }
        )

    if len(artifact.split()) < 40:
        warnings.append(
            {
                "code": "short_artifact",
                "message": "The artifact is short, so score confidence is lower and feedback may ask for more evidence.",
            }
        )

    return EvaluationRequest(
        learner_goal=learner_goal,
        artifact=artifact,
        artifact_type=artifact_type,
        level=level,
        output_goal=output_goal,
        learner_id=learner_id,
        prior_mastery=prior_mastery,
        days_since_last_review=days_since_last_review,
        target_retention=target_retention,
        custom_rubric=custom_rubric,
        warnings=warnings,
    )


def clamp_score(value: Any) -> int:
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        number = 3
    return max(1, min(5, int(number)))
