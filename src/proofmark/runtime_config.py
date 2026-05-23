from __future__ import annotations

import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ENV = ROOT / ".proofmark_demo.env"
_LOADED_PATHS: set[Path] = set()


def load_runtime_env(path: str | Path | None = None) -> dict[str, Any]:
    """Load optional local demo provider config without committing secrets.

    Existing environment variables win. The intended local file is
    `.proofmark_demo.env`, which is gitignored and should contain only
    low-balance/restricted demo keys for product review.
    """
    configured = os.getenv("PROOFMARK_RUNTIME_ENV_FILE", "").strip()
    target = Path(path or configured or DEFAULT_RUNTIME_ENV).expanduser()
    if not target.is_absolute():
        target = ROOT / target
    target = target.resolve()
    if target in _LOADED_PATHS:
        return {"loaded": True, "path": str(target), "already_loaded": True, "keys": []}
    if not target.is_file():
        return {"loaded": False, "path": str(target), "keys": []}

    loaded_keys: list[str] = []
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_quotes(value)
        loaded_keys.append(key)
    _LOADED_PATHS.add(target)
    return {"loaded": True, "path": str(target), "already_loaded": False, "keys": loaded_keys}


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            quote = char if quote is None else None if quote == char else quote
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
