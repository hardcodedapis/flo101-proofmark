from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SECRET_KEYS = {
    "api_key",
    "openai_api_key",
    "pinecone_api_key",
    "elevenlabs_api_key",
    "google_api_key",
    "gemini_api_key",
    "authorization",
    "token",
}


def resolve_session_id(payload: dict[str, Any], base_payload: dict[str, Any], new_event: dict[str, Any] | None) -> str:
    identity = new_event.get("identity", {}) if isinstance(new_event, dict) and isinstance(new_event.get("identity"), dict) else {}
    candidates = [
        payload.get("session_id"),
        identity.get("session_id"),
        base_payload.get("session_id"),
        base_payload.get("learner_id"),
        "browser-demo-session",
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return _safe_id(value)
    return "browser-demo-session"


def load_session_state(session_id: str) -> dict[str, Any]:
    session_id = _safe_id(session_id)
    conn = _connect()
    try:
        _init_db(conn)
        session_row = conn.execute(
            "SELECT version, base_payload_digest, updated_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        events = [
            json.loads(row["event_json"])
            for row in conn.execute(
                "SELECT event_json FROM events WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            ).fetchall()
        ]
        audit_log = [
            json.loads(row["audit_json"])
            for row in conn.execute(
                "SELECT audit_json FROM audit_log WHERE session_id = ? ORDER BY version",
                (session_id,),
            ).fetchall()
        ]
    finally:
        conn.close()
    return {
        "session_id": session_id,
        "version": int(session_row["version"]) if session_row else 0,
        "base_payload_digest": session_row["base_payload_digest"] if session_row else "",
        "updated_at": session_row["updated_at"] if session_row else "",
        "events": events,
        "event_ids": [event_identity(event) for event in events],
        "audit_log": audit_log,
    }


def dedupe_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event_identity(event)
        if event_id in seen:
            duplicate_ids.append(event_id)
            continue
        seen.add(event_id)
        deduped.append(event)
    return deduped, duplicate_ids


def event_identity(event: dict[str, Any]) -> str:
    identity = event.get("identity") if isinstance(event.get("identity"), dict) else {}
    event_id = str(identity.get("event_id") or "").strip()
    if event_id:
        return _safe_id(event_id)
    digest = hashlib.sha256(json.dumps(_redact(event), sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"event-{digest[:16]}"


def save_session_state(
    *,
    session_id: str,
    base_payload: dict[str, Any],
    events: list[dict[str, Any]],
    latest_event: dict[str, Any] | None,
    roadmap: dict[str, Any],
    learner_profile: dict[str, Any],
    duplicate_event_ids: list[str],
) -> dict[str, Any]:
    state = load_session_state(session_id)
    version = int(state.get("version") or 0) + 1
    audit_record = {
        "version": version,
        "timestamp": _now_iso(),
        "base_payload_digest": _payload_digest(base_payload),
        "latest_event_id": event_identity(latest_event) if isinstance(latest_event, dict) else "",
        "latest_server_score": _nested(latest_event or {}, "response_quality", "score"),
        "dominant_anchor": learner_profile.get("dominant_anchor", "balanced"),
        "next_mode": roadmap.get("next_mode", "collect_more_evidence"),
        "target_concepts": roadmap.get("target_concepts", []),
        "event_count": len(events),
        "duplicate_event_ids": duplicate_event_ids,
    }
    conn = _connect()
    try:
        _init_db(conn)
        with conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, version, updated_at, base_payload_digest)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    version = excluded.version,
                    updated_at = excluded.updated_at,
                    base_payload_digest = excluded.base_payload_digest
                """,
                (session_id, version, audit_record["timestamp"], audit_record["base_payload_digest"]),
            )
            conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
            conn.executemany(
                """
                INSERT INTO events(session_id, event_id, event_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        event_identity(event),
                        json.dumps(_redact(event), sort_keys=True, default=str),
                        audit_record["timestamp"],
                    )
                    for event in events
                ],
            )
            conn.execute(
                """
                INSERT INTO audit_log(session_id, version, audit_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    version,
                    json.dumps(audit_record, sort_keys=True, default=str),
                    audit_record["timestamp"],
                ),
            )
            conn.execute(
                "DELETE FROM audit_log WHERE session_id = ? AND version NOT IN "
                "(SELECT version FROM audit_log WHERE session_id = ? ORDER BY version DESC LIMIT 20)",
                (session_id, session_id),
            )
    finally:
        conn.close()
    return {
        "session_id": session_id,
        "version": version,
        "persisted": True,
        "event_count": len(events),
        "duplicate_event_ids": duplicate_event_ids,
        "audit_record": audit_record,
        "path": str(_db_path()),
    }


def _state_dir() -> Path:
    configured = os.getenv("PROOFMARK_STATE_DIR", "").strip()
    return Path(configured) if configured else ROOT / ".proofmark_state"


def _db_path() -> Path:
    return _state_dir() / "proofmark.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            base_payload_digest TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            session_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (session_id, event_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            session_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            audit_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (session_id, version),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
        """
    )


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())[:96].strip("-")
    return cleaned or "session"


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(_redact(payload), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SECRET_KEYS or lowered.endswith("_key") or "secret" in lowered:
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = _redact(item)
        return cleaned
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return deepcopy(value)


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current if current is not None else ""


def _now_iso() -> str:
    return datetime.fromtimestamp(time.time(), timezone.utc).isoformat()
