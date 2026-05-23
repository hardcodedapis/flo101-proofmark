from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
import os
import sys
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .chemistry import initial_pcm_test, submit_pcm_attempt
from .compare import compare_revisions
from .roadmap import adapt_track_b_plan, build_track_b_plan, sample_track_b_payload
from .runtime_config import load_runtime_env
from .schema import InputError
from .voice import generate_voice_summary, list_elevenlabs_models, list_elevenlabs_voices
from .workflow import evaluate_artifact


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
DEFAULT_MAX_POST_BODY_BYTES = 24 * 1024 * 1024
RATE_LIMIT_RECORDS: dict[str, deque[float]] = defaultdict(deque)


def _configured_api_token() -> str:
    return os.getenv("PROOFMARK_API_TOKEN", "").strip()


def _request_token(headers: Any) -> str:
    auth = str(headers.get("Authorization", "")).strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return str(headers.get("X-Proofmark-Token", "")).strip()


def _client_authorized(headers: Any) -> bool:
    expected = _configured_api_token()
    return not expected or _request_token(headers) == expected


def _rate_limit_config() -> tuple[int, int]:
    limit = int(os.getenv("PROOFMARK_RATE_LIMIT_PER_MINUTE", "120"))
    window = int(os.getenv("PROOFMARK_RATE_LIMIT_WINDOW_SECONDS", "60"))
    return max(1, limit), max(1, window)


def _rate_limit_decision(records: deque[float], now: float, limit: int, window_seconds: int) -> tuple[bool, int]:
    while records and now - records[0] > window_seconds:
        records.popleft()
    if len(records) >= limit:
        retry_after = max(1, int(window_seconds - (now - records[0])))
        return False, retry_after
    records.append(now)
    return True, 0


def _max_post_body_bytes() -> int:
    try:
        configured = int(os.getenv("PROOFMARK_MAX_POST_BODY_BYTES", str(DEFAULT_MAX_POST_BODY_BYTES)))
    except ValueError:
        configured = DEFAULT_MAX_POST_BODY_BYTES
    return max(1_000_000, configured)


def internal_error_payload(request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": "internal_server_error",
            "message": "Local backend failed while processing this request. See server logs with the returned request id.",
            "request_id": request_id,
        }
    }


class ProofMarkHandler(BaseHTTPRequestHandler):
    server_version = "ProofMark/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        request_id = getattr(self, "request_id", uuid.uuid4().hex[:16])
        data = json.dumps(payload, indent=2).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Request-Id", request_id)
            self.end_headers()
            self.wfile.write(data)
        except BrokenPipeError:
            return
        finally:
            self._log_structured(status, len(data), request_id)

    def _log_structured(self, status: int, response_bytes: int, request_id: str) -> None:
        started_at = getattr(self, "_started_at", time.time())
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id,
            "method": getattr(self, "command", ""),
            "path": self.path.split("?", 1)[0],
            "status": status,
            "duration_ms": round((time.time() - started_at) * 1000, 2),
            "response_bytes": response_bytes,
            "client": self.client_address[0] if self.client_address else "",
        }
        sys.stderr.write(json.dumps(record, sort_keys=True) + "\n")

    def _log_exception(self, exc: Exception) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": getattr(self, "request_id", ""),
            "method": getattr(self, "command", ""),
            "path": self.path.split("?", 1)[0],
            "error_class": exc.__class__.__name__,
            "error_message": str(exc),
        }
        sys.stderr.write(json.dumps(record, sort_keys=True) + "\n")

    def _send_file(self, path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_file() or WEB_ROOT not in resolved.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(resolved.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        if resolved.suffix in {".html", ".css", ".js"}:
            self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._started_at = time.time()
        self.request_id = uuid.uuid4().hex[:16]
        clean_request_path = self.path.split("?", 1)[0]
        if clean_request_path == "/health":
            self._send_json({"ok": True, "service": "proofmark"})
            return
        if clean_request_path == "/api/track-b/sample":
            self._send_json(sample_track_b_payload(include_evidence=True))
            return
        if clean_request_path == "/api/track-b/sample-cold":
            self._send_json(sample_track_b_payload(include_evidence=False))
            return
        if clean_request_path == "/api/track-b/sample-physics":
            self._send_json(sample_track_b_payload(include_evidence=False, topic="ray_optics"))
            return
        if clean_request_path == "/api/track-b/sample-chemistry":
            self._send_json(sample_track_b_payload(include_evidence=False, topic="chemistry"))
            return
        if clean_request_path in {"/api/chemistry/test", "/api/pcm/test"}:
            self._send_json(initial_pcm_test())
            return
        if clean_request_path == "/" or clean_request_path == "/index.html":
            self._send_file(WEB_ROOT / "index.html")
            return
        clean_path = clean_request_path.lstrip("/")
        self._send_file(WEB_ROOT / clean_path)

    def do_POST(self) -> None:
        self._started_at = time.time()
        self.request_id = uuid.uuid4().hex[:16]
        if self.path not in {
            "/api/evaluate",
            "/api/compare",
            "/api/chemistry/submit",
            "/api/pcm/submit",
            "/api/track-b/adapt",
            "/api/track-b/generate",
            "/api/track-b/voice-summary",
            "/api/track-b/elevenlabs-voices",
            "/api/track-b/elevenlabs-models",
        }:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not _client_authorized(self.headers):
            self._send_json({"error": {"code": "unauthorized", "message": "Valid API token required."}}, 401)
            return
        rate_limit, window_seconds = _rate_limit_config()
        rate_key = f"{self.client_address[0] if self.client_address else 'unknown'}:{self.path}"
        allowed, retry_after = _rate_limit_decision(RATE_LIMIT_RECORDS[rate_key], time.time(), rate_limit, window_seconds)
        if not allowed:
            self._send_json(
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Retry after the reported number of seconds.",
                        "retry_after_seconds": retry_after,
                    }
                },
                429,
            )
            return
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(
                    {"error": {"code": "invalid_content_length", "message": "Content-Length must be an integer."}},
                    400,
                )
                return
            if length < 0:
                self._send_json(
                    {"error": {"code": "invalid_content_length", "message": "Content-Length cannot be negative."}},
                    400,
                )
                return
            max_body_bytes = _max_post_body_bytes()
            if length > max_body_bytes:
                self._send_json(
                    {
                        "error": {
                            "code": "request_too_large",
                            "message": f"Request body must be at most {max_body_bytes:,} bytes.",
                        }
                    },
                    413,
                )
                return
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if self.path == "/api/track-b/generate":
                result = build_track_b_plan(payload)
            elif self.path == "/api/track-b/adapt":
                result = adapt_track_b_plan(payload)
            elif self.path == "/api/track-b/voice-summary":
                result = generate_voice_summary(payload)
            elif self.path == "/api/track-b/elevenlabs-voices":
                result = list_elevenlabs_voices(payload)
            elif self.path == "/api/track-b/elevenlabs-models":
                result = list_elevenlabs_models(payload)
            elif self.path in {"/api/chemistry/submit", "/api/pcm/submit"}:
                result = submit_pcm_attempt(payload)
            elif self.path == "/api/compare":
                result = compare_revisions(payload, provider=payload.get("provider"))
            else:
                result = evaluate_artifact(payload, provider=payload.get("provider"))
        except json.JSONDecodeError:
            self._send_json({"error": {"code": "invalid_json", "message": "Request body must be valid JSON."}}, 400)
            return
        except InputError as exc:
            self._send_json(exc.to_dict(), exc.status)
            return
        except Exception as exc:
            self._log_exception(exc)
            self._send_json(internal_error_payload(self.request_id), 500)
            return
        self._send_json(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ProofMark local web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    runtime_env = load_runtime_env()
    if runtime_env.get("loaded"):
        print(f"Loaded local demo runtime config from {runtime_env['path']}")
    server = ThreadingHTTPServer((args.host, args.port), ProofMarkHandler)
    print(f"ProofMark running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ProofMark.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
