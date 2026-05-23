from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .heuristics import evaluate_with_heuristics
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .rubric import RubricDimension
from .schema import EvaluationRequest


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
        body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.body = body


class LocalProvider:
    name = "local-heuristic"

    def evaluate(
        self,
        request: EvaluationRequest,
        rubric: list[RubricDimension],
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return evaluate_with_heuristics(request, rubric, self.name)


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = float(os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "600"))
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "high").strip()
        self.max_output_tokens = int(os.getenv("PROOFMARK_MAX_OUTPUT_TOKENS", "6000"))

    def evaluate(
        self,
        request: EvaluationRequest,
        rubric: list[RubricDimension],
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")
        if not self.model:
            raise ProviderError("OPENAI_MODEL is not set.")
        if baseline is None:
            baseline = evaluate_with_heuristics(request, rubric)

        body = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": build_user_prompt(request, rubric, baseline),
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "proofmark_evaluation",
                    "strict": True,
                    "schema": EVALUATION_JSON_SCHEMA,
                }
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/responses",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Provider HTTP {exc.code}: {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"Provider network error: {exc}") from exc

        try:
            payload = json.loads(raw)
            content = _extract_response_text(payload)
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("Provider returned malformed JSON.") from exc

        result.setdefault("metadata", {})
        result["metadata"]["provider"] = f"{self.name}:{self.model}:{self.reasoning_effort}"
        result["metadata"]["fallback_used"] = False
        return result


def choose_provider(name: str | None) -> LocalProvider | OpenAICompatibleProvider:
    selected = (name or os.getenv("PROOFMARK_PROVIDER") or "auto").strip().lower()
    if selected == "local":
        return LocalProvider()
    if selected in {"openai", "auto"}:
        return OpenAICompatibleProvider()
    return LocalProvider()


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                return content["text"]
            if isinstance(content.get("output_text"), str):
                return content["output_text"]

    if "choices" in payload:
        return payload["choices"][0]["message"]["content"]

    raise KeyError("No output text found in provider response.")


EVALUATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overall_score": {"type": "integer"},
        "verdict": {"type": "string"},
        "rubric": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "integer"},
                    "weight": {"type": "number"},
                    "evidence": {"type": "string"},
                    "feedback": {"type": "string"},
                    "risk_if_ignored": {"type": "string"},
                },
                "required": ["name", "score", "weight", "evidence", "feedback", "risk_if_ignored"],
            },
        },
        "missing_gaps": {"type": "array", "items": {"type": "string"}},
        "next_best_step": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "why": {"type": "string"},
                "instructions": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "why", "instructions", "acceptance_criteria"],
        },
        "proof_of_work": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "evidence_observed": {"type": "array", "items": {"type": "string"}},
                "evidence_missing": {"type": "array", "items": {"type": "string"}},
                "verification_questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["evidence_observed", "evidence_missing", "verification_questions"],
        },
        "evidence_map": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "dimension": {"type": "string"},
                    "claim": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                    "missing_proof": {"type": "string"},
                    "verification_question": {"type": "string"},
                },
                "required": [
                    "dimension",
                    "claim",
                    "status",
                    "evidence",
                    "missing_proof",
                    "verification_question",
                ],
            },
        },
        "feedback_loop": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "feed_up_goal": {"type": "string"},
                "feed_back_current_state": {"type": "string"},
                "feed_forward_next_action": {"type": "string"},
            },
            "required": ["feed_up_goal", "feed_back_current_state", "feed_forward_next_action"],
        },
        "judge_diagnostics": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "bias_checks": {"type": "array", "items": {"type": "string"}},
                "calibration_notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["bias_checks", "calibration_notes"],
        },
        "reliability": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "confidence": {"type": "string"},
                "checks_passed": {"type": "array", "items": {"type": "string"}},
                "warnings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                        "required": ["code", "message"],
                    },
                },
            },
            "required": ["confidence", "checks_passed", "warnings"],
        },
    },
    "required": [
        "overall_score",
        "verdict",
        "rubric",
        "missing_gaps",
        "next_best_step",
        "proof_of_work",
        "evidence_map",
        "feedback_loop",
        "judge_diagnostics",
        "reliability",
    ],
}
