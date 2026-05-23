from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
from pathlib import Path
from typing import Any, Callable

from .providers import ProviderError


RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def cached_json(provider: str, model: str, request_body: dict[str, Any], call: Callable[[], Any]) -> tuple[Any, bool]:
    if os.getenv("PROOFMARK_DISABLE_PROVIDER_CACHE", "").lower() in {"1", "true", "yes"}:
        return call(), False
    path = _cache_path(provider, model, request_body)
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - float(cached.get("created_at", 0)) <= _cache_ttl_seconds():
                return cached["response"], True
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    response = call()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"created_at": time.time(), "provider": provider, "model": model, "response": response}),
            encoding="utf-8",
        )
    except OSError:
        pass
    return response, False


def parse_provider_json_object(content: str) -> dict[str, Any]:
    """Parse a provider JSON object from common model-output wrappers.

    Provider APIs sometimes return valid JSON inside Markdown fences, with short
    leading text, or with harmless trailing commas. This accepts those cases but
    still rejects output that does not contain a JSON object.
    """
    parsed = parse_provider_json(content)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        return parsed[0]
    raise json.JSONDecodeError("Provider output must contain a JSON object.", str(content or ""), 0)


def parse_provider_json(content: str) -> Any:
    text = str(content or "").strip()
    errors: list[json.JSONDecodeError] = []
    for candidate in _json_candidates(text):
        try:
            return _decode_json_candidate(candidate)
        except json.JSONDecodeError as exc:
            errors.append(exc)
    if errors:
        raise errors[-1]
    raise json.JSONDecodeError("No JSON found in provider output.", text, 0)


def _json_candidates(text: str) -> list[str]:
    candidates = []
    if text:
        candidates.append(text)
    for match in re.finditer(r"```(?:json|JSON)?\s*(.*?)```", text, flags=re.DOTALL):
        body = match.group(1).strip()
        if body:
            candidates.append(body)
    for opener, closer in [("{", "}"), ("[", "]")]:
        try:
            candidates.append(_first_balanced_json(text, opener, closer))
        except json.JSONDecodeError:
            pass
    result = []
    seen = set()
    for candidate in candidates:
        cleaned = candidate.strip().lstrip("\ufeff")
        if cleaned and cleaned not in seen:
            result.append(cleaned)
            seen.add(cleaned)
    return result


def _decode_json_candidate(candidate: str) -> Any:
    cleaned = _repair_common_json(candidate)
    decoder = json.JSONDecoder(strict=False)
    parsed, index = decoder.raw_decode(cleaned)
    trailing = cleaned[index:].strip()
    if trailing and not trailing.startswith(("```", "</json>")):
        # raw_decode already permits trailing prose; the balanced-object
        # candidate handles that case more precisely.
        raise json.JSONDecodeError("Extra data after JSON value.", cleaned, index)
    return parsed


def _repair_common_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json|JSON)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned


def _first_balanced_json(text: str, opener: str, closer: str) -> str:
    start = text.find(opener)
    if start < 0:
        raise json.JSONDecodeError("No JSON value found.", text, 0)
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise json.JSONDecodeError("Unclosed JSON value.", text, start)


def with_provider_retries(label: str, call: Callable[[], Any]) -> Any:
    attempts = max(1, int(os.getenv("PROOFMARK_PROVIDER_RETRIES", "2")))
    last_error: ProviderError | None = None
    for attempt in range(attempts):
        try:
            return call()
        except ProviderError as exc:
            last_error = exc
            if not _should_retry(exc) or attempt == attempts - 1:
                break
            time.sleep(_retry_delay_seconds(exc, attempt))
    raise last_error or ProviderError(f"{label} failed.")


def provider_error_from_http(prefix: str, exc: urllib.error.HTTPError, detail: str) -> ProviderError:
    retry_after = None
    try:
        retry_after_value = exc.headers.get("Retry-After") if exc.headers else None
        retry_after = float(retry_after_value) if retry_after_value else None
    except (TypeError, ValueError):
        retry_after = None
    message = f"{prefix} HTTP {exc.code}: {detail[:300]}"
    if exc.code == 429:
        message += " The provider rate-limited or quota-limited this full-context request."
    return ProviderError(message, status_code=exc.code, retry_after=retry_after, body=detail)


def _should_retry(exc: ProviderError) -> bool:
    return exc.status_code in RETRYABLE_HTTP_STATUS


def _retry_delay_seconds(exc: ProviderError, attempt: int) -> float:
    if exc.retry_after is not None:
        return min(float(os.getenv("PROOFMARK_PROVIDER_MAX_RETRY_SECONDS", "12")), max(0.0, exc.retry_after))
    base = float(os.getenv("PROOFMARK_PROVIDER_RETRY_BASE_SECONDS", "1.5"))
    delay = base * (2**attempt)
    return min(float(os.getenv("PROOFMARK_PROVIDER_MAX_RETRY_SECONDS", "12")), delay)


def _cache_path(provider: str, model: str, request_body: dict[str, Any]) -> Path:
    cache_root = Path(os.getenv("PROOFMARK_PROVIDER_CACHE_DIR", Path.home() / ".cache" / "proofmark" / "provider-cache"))
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "body": request_body,
            "version": "provider-cache-v1",
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return cache_root / provider / f"{digest}.json"


def _cache_ttl_seconds() -> float:
    return float(os.getenv("PROOFMARK_PROVIDER_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60)))
