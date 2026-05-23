from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .schema import InputError


DEFAULT_ELEVENLABS_MODEL = ""
DEFAULT_ELEVENLABS_VOICE_ID = ""
MAX_VOICE_SCRIPT_CHARS = 2600
_DEFAULT_VOICE_CACHE: dict[str, str] = {}
_DEFAULT_MODEL_CACHE: dict[str, str] = {}


def generate_voice_summary(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or payload.get("script") or "").strip()
    if not text:
        raise InputError("missing_voice_text", "Voice generation needs a short explanation script.")
    if len(text) > MAX_VOICE_SCRIPT_CHARS:
        text = text[:MAX_VOICE_SCRIPT_CHARS].rsplit(" ", 1)[0].strip()

    api_key = str(
        payload.get("elevenlabs_api_key")
        or payload.get("api_key")
        or os.getenv("ELEVENLABS_API_KEY", "")
    ).strip()
    if not api_key:
        raise InputError(
            "missing_elevenlabs_key",
            "Add an ElevenLabs API key to generate the spoken explanation.",
        )

    voice_id = str(
        payload.get("voice_id")
        or os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID)
    ).strip()
    if not voice_id:
        voice_id = _default_voice_id(api_key)
    if not voice_id:
        raise InputError("missing_elevenlabs_voice", "No ElevenLabs voice is configured or available on this demo account.")
    model_id = str(
        payload.get("model_id")
        or os.getenv("ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL)
    ).strip()
    if not model_id:
        model_id = _default_model_id(api_key)
    if not model_id:
        raise InputError("missing_elevenlabs_model", "No ElevenLabs text-to-speech model is configured or available on this demo account.")
    output_format = str(payload.get("output_format") or "mp3_44100_128").strip()

    audio = _call_elevenlabs_tts(
        api_key=api_key,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        text=text,
    )

    return {
        "status": "voice_generated",
        "provider": "elevenlabs:text-to-speech",
        "voice_id": voice_id,
        "model_id": model_id,
        "requested_model_id": model_id,
        "fallback_used": False,
        "mime_type": "audio/mpeg",
        "audio_mpeg_base64": base64.b64encode(audio).decode("ascii"),
        "disclaimer": (
            "This demo generates a source-grounded narrated explanation. Full live conversation would add "
            "streaming speech recognition, interruption handling, and an agent session layer."
        ),
    }


def _call_elevenlabs_tts(
    api_key: str,
    voice_id: str,
    model_id: str,
    output_format: str,
    text: str,
) -> bytes:
    encoded_voice = urllib.parse.quote(voice_id, safe="")
    encoded_format = urllib.parse.quote(output_format, safe="")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{encoded_voice}?output_format={encoded_format}"
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.78,
            "style": 0.18,
            "use_speaker_boost": True,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "600"))) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise InputError("elevenlabs_http_error", f"ElevenLabs returned HTTP {exc.code}: {detail[:220]}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise InputError("elevenlabs_network_error", f"Could not reach ElevenLabs: {exc}", 502) from exc


def list_elevenlabs_voices(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _runtime_elevenlabs_key(payload)
    page_size = int(payload.get("page_size") or 30)
    page_size = max(1, min(page_size, 100))
    query = urllib.parse.urlencode({"page_size": page_size})
    data = _call_elevenlabs_json(api_key, f"https://api.elevenlabs.io/v2/voices?{query}")
    voices = data.get("voices", []) if isinstance(data, dict) else []
    if not isinstance(voices, list):
        voices = []
    return {
        "status": "voices_loaded",
        "provider": "elevenlabs:voices",
        "voices": [_normalize_voice(voice) for voice in voices if isinstance(voice, dict)],
    }


def list_elevenlabs_models(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _runtime_elevenlabs_key(payload)
    data = _call_elevenlabs_json(api_key, "https://api.elevenlabs.io/v1/models")
    models = data if isinstance(data, list) else data.get("models", []) if isinstance(data, dict) else []
    if not isinstance(models, list):
        models = []
    normalized = [_normalize_model(model) for model in models if isinstance(model, dict)]
    tts_models = [model for model in normalized if model["can_do_text_to_speech"]]
    return {
        "status": "models_loaded",
        "provider": "elevenlabs:models",
        "models": tts_models or normalized,
        "recommended_model_id": _recommended_model_id(tts_models or normalized),
    }


def _runtime_elevenlabs_key(payload: dict[str, Any]) -> str:
    api_key = str(
        payload.get("elevenlabs_api_key")
        or payload.get("api_key")
        or os.getenv("ELEVENLABS_API_KEY", "")
    ).strip()
    if not api_key:
        raise InputError(
            "missing_elevenlabs_key",
            "Add an ElevenLabs API key before loading voices or generating audio.",
        )
    return api_key


def _call_elevenlabs_json(api_key: str, url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "xi-api-key": api_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "600"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise InputError("elevenlabs_http_error", f"ElevenLabs returned HTTP {exc.code}: {detail[:220]}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise InputError("elevenlabs_network_error", f"Could not reach ElevenLabs: {exc}", 502) from exc
    except json.JSONDecodeError as exc:
        raise InputError("elevenlabs_invalid_json", "ElevenLabs returned a response that was not valid JSON.", 502) from exc


def _normalize_voice(voice: dict[str, Any]) -> dict[str, Any]:
    labels = voice.get("labels") if isinstance(voice.get("labels"), dict) else {}
    return {
        "voice_id": str(voice.get("voice_id") or ""),
        "name": str(voice.get("name") or "Untitled voice"),
        "category": str(voice.get("category") or ""),
        "description": str(voice.get("description") or labels.get("description") or ""),
        "accent": str(labels.get("accent") or ""),
        "age": str(labels.get("age") or ""),
        "gender": str(labels.get("gender") or ""),
        "use_case": str(labels.get("use_case") or ""),
        "preview_url": str(voice.get("preview_url") or ""),
    }


def _normalize_model(model: dict[str, Any]) -> dict[str, Any]:
    languages = model.get("languages") if isinstance(model.get("languages"), list) else []
    return {
        "model_id": str(model.get("model_id") or model.get("id") or ""),
        "name": str(model.get("name") or model.get("model_id") or "Untitled model"),
        "description": str(model.get("description") or ""),
        "can_do_text_to_speech": bool(model.get("can_do_text_to_speech", True)),
        "can_be_finetuned": bool(model.get("can_be_finetuned", False)),
        "languages": [
            str(language.get("name") or language.get("language_id") or "")
            for language in languages
            if isinstance(language, dict)
        ][:8],
    }


def _recommended_model_id(models: list[dict[str, Any]]) -> str:
    model_ids = {model["model_id"] for model in models if model.get("model_id")}
    for candidate in ("eleven_multilingual_v2", "eleven_flash_v2_5"):
        if candidate in model_ids:
            return candidate
    return next(iter(model_ids), "")


def _default_voice_id(api_key: str) -> str:
    if api_key in _DEFAULT_VOICE_CACHE:
        return _DEFAULT_VOICE_CACHE[api_key]
    preferred_name = os.getenv("ELEVENLABS_VOICE_NAME", "").strip().lower()
    try:
        voices = list_elevenlabs_voices({"elevenlabs_api_key": api_key}).get("voices", [])
    except InputError:
        return ""
    selected = ""
    if preferred_name:
        for voice in voices:
            if str(voice.get("name", "")).strip().lower() == preferred_name:
                selected = str(voice.get("voice_id") or "")
                break
    if not selected and voices:
        selected = str(voices[0].get("voice_id") or "")
    _DEFAULT_VOICE_CACHE[api_key] = selected
    return selected


def _default_model_id(api_key: str) -> str:
    if api_key in _DEFAULT_MODEL_CACHE:
        return _DEFAULT_MODEL_CACHE[api_key]
    try:
        selected = str(list_elevenlabs_models({"elevenlabs_api_key": api_key}).get("recommended_model_id") or "")
    except InputError:
        selected = ""
    _DEFAULT_MODEL_CACHE[api_key] = selected
    return selected
