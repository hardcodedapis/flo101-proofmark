from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .provider_runtime import cached_json, parse_provider_json_object, provider_error_from_http, with_provider_retries
from .providers import ProviderError


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


GEMINI_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "common_trap": {"type": "string"},
                },
                "required": ["name", "why_it_matters", "common_trap"],
            },
        },
        "key_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["fact", "why_it_matters"],
            },
        },
        "formulas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "latex": {"type": "string"},
                    "meaning": {"type": "string"},
                    "when_to_use": {"type": "string"},
                },
                "required": ["label", "latex", "meaning", "when_to_use"],
            },
        },
        "timestamp_guide": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "title": {"type": "string"},
                    "what_happens": {"type": "string"},
                    "watch_for": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source_id", "start", "end", "title", "what_happens", "watch_for"],
            },
        },
        "common_mistakes": {"type": "array", "items": {"type": "string"}},
        "source_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "title": {"type": "string"},
                    "media_role": {"type": "string"},
                    "why_useful": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source_id", "title", "media_role", "why_useful", "bullets"],
            },
        },
    },
    "required": [
        "summary",
        "key_concepts",
        "key_facts",
        "formulas",
        "timestamp_guide",
        "common_mistakes",
        "source_notes",
    ],
}


SOURCE_ANALYSIS_PROMPT = """
You are the compact source/video extraction layer for a Track B learning product.

Input is a learning objective, content manifest, selected RAG chunks, and optional public video URLs.
Return JSON only. Do not mention API keys. Do not invent facts outside the sources.

Extract only source-backed material. Do not generate the full lesson, quiz, adaptive plan,
diagram specification, flowchart, reteaching plan, or student video lesson. The local
backend will turn this compact extraction into those product surfaces.

Rules:
- Keep output compact and student-facing.
- Remove PDF artifacts, navigation text, boilerplate, captions noise, and source noise.
- Prefer exact source-backed facts over generic educational advice.
- For timestamps, include only useful video parts. If a timestamp is unknown, use empty strings.
- Max 6 key_concepts, 8 key_facts, 6 formulas, 8 timestamp_guide items, 8 common_mistakes.
- Do not return page_sequence, questions_to_ask, concept_diagrams, flowcharts,
  adaptive_quiz_blueprint, reteaching_plan, video_learning_plan, or student_video_lesson.

Schema shape:
{
  "summary": "string",
  "key_concepts": [
    {
      "name": "string",
      "why_it_matters": "string",
      "common_trap": "string"
    }
  ],
  "key_facts": [
    {"fact": "string", "why_it_matters": "string"}
  ],
  "formulas": [
    {"label": "string", "latex": "string", "meaning": "string", "when_to_use": "string"}
  ],
  "timestamp_guide": [
    {
      "source_id": "string",
      "start": "string",
      "end": "string",
      "title": "string",
      "what_happens": "string",
      "watch_for": ["string"]
    }
  ],
  "common_mistakes": ["string"],
  "source_notes": [
    {
      "source_id": "string",
      "title": "string",
      "media_role": "video|pdf|notes|worksheet|web|transcript|other",
      "why_useful": "string",
      "bullets": ["string"]
    }
  ]
}
"""


def analyze_sources(
    payload: dict[str, Any],
    graph: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    constraints = payload.get("constraints", {}) if isinstance(payload.get("constraints"), dict) else {}
    enabled = bool(
        payload.get("analyze_sources_with_gemini")
        or constraints.get("analyze_sources_with_gemini")
        or os.getenv("PROOFLOOP_ANALYZE_SOURCES_WITH_GEMINI", "").lower() in {"1", "true", "yes"}
    )
    model = str(
        payload.get("gemini_model")
        or constraints.get("gemini_model")
        or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    ).strip()
    api_key = str(
        payload.get("gemini_api_key")
        or payload.get("google_api_key")
        or constraints.get("gemini_api_key")
        or constraints.get("google_api_key")
        or os.getenv("GEMINI_API_KEY", "")
        or os.getenv("GOOGLE_API_KEY", "")
    ).strip()

    fallback = _fallback_source_analysis(graph, retrieved_chunks)
    if not enabled:
        fallback["reason"] = (
            "Gemini source analysis is disabled. The local planner produced the same response shape from parsed sources and RAG chunks."
        )
        fallback["model_requested"] = model
        return fallback
    if not api_key:
        fallback["reason"] = (
            "Gemini source analysis was requested, but no Gemini/Google API key was supplied. The local planner produced the same response shape."
        )
        fallback["model_requested"] = model
        return fallback
    if not model:
        fallback["reason"] = (
            "Gemini source analysis was requested with a runtime key, but no Gemini model id was selected. Enter a model id or set GEMINI_MODEL."
        )
        fallback["model_requested"] = ""
        return fallback

    try:
        call_result = _call_gemini_source_analysis(graph, retrieved_chunks, api_key=api_key, model=model)
        if isinstance(call_result, tuple):
            result, from_cache = call_result
        else:
            result, from_cache = call_result, False
    except ProviderError as exc:
        fallback["reason"] = f"Gemini source analysis failed; local planner used instead. {_redact(str(exc), api_key)}"
        fallback["model_requested"] = model
        fallback["provider_error"] = {
            "provider": f"gemini:{model}",
            "status_code": exc.status_code,
            "retry_after": exc.retry_after,
            "message": _redact(str(exc), api_key),
        }
        return fallback

    normalized = _normalize_model_result(result, graph, retrieved_chunks)
    normalized.update(
        {
            "status": "model_generated",
            "provider": f"gemini:{model}",
            "model_requested": model,
            "from_cache": from_cache,
            "reason": (
                "Gemini source analysis was reused from cache."
                if from_cache
                else "Gemini analyzed the source manifest, RAG chunks, and public video URL parts where available."
            ),
        }
    )
    return normalized


def _call_gemini_source_analysis(
    graph: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    api_key: str,
    model: str,
) -> tuple[dict[str, Any], bool]:
    timeout = float(os.getenv("PROOFMARK_GEMINI_TIMEOUT", os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "45")))
    try:
        max_output_tokens = int(os.getenv("PROOFMARK_GEMINI_MAX_OUTPUT_TOKENS", "4096"))
    except ValueError:
        max_output_tokens = 4096
    try:
        thinking_budget = int(os.getenv("PROOFMARK_GEMINI_THINKING_BUDGET", "0"))
    except ValueError:
        thinking_budget = 0
    thinking_level = os.getenv("PROOFMARK_GEMINI_THINKING_LEVEL", "minimal").strip().lower()
    prompt = _build_gemini_prompt(graph, retrieved_chunks)
    parts: list[dict[str, Any]] = [{"text": prompt}]
    parts.extend(_gemini_video_parts(graph))
    generation_config: dict[str, Any] = {
        "temperature": 0.2,
        "responseMimeType": "application/json",
        "responseSchema": GEMINI_SOURCE_SCHEMA,
        "maxOutputTokens": max(1024, max_output_tokens),
    }
    if model.startswith("gemini-3"):
        generation_config["thinkingConfig"] = {
            "thinkingLevel": thinking_level if thinking_level in {"minimal", "low", "medium", "high"} else "minimal"
        }
    elif "2.5" in model:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
    }

    def call_provider() -> dict[str, Any]:
        def attempt() -> dict[str, Any]:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise provider_error_from_http("Gemini", exc, detail) from exc
            except TimeoutError as exc:
                raise ProviderError(
                    f"Gemini timed out after {timeout:.0f}s. "
                    "The video/source analysis call was attempted, but the local source planner continued the build.",
                    status_code=504,
                ) from exc
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                status_code = 504 if isinstance(reason, TimeoutError) else None
                timeout_note = f" after {timeout:.0f}s" if isinstance(reason, TimeoutError) else ""
                raise ProviderError(f"Gemini network error{timeout_note}: {exc}", status_code=status_code) from exc

            try:
                payload = json.loads(raw)
                text = _extract_gemini_text(payload)
                return parse_provider_json_object(text)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise ProviderError("Gemini response did not match the compact source-analysis schema.") from exc

        return with_provider_retries("Gemini source analysis", attempt)

    return cached_json("gemini-source-analysis", model, body, call_provider)


def _build_gemini_prompt(graph: dict[str, Any], retrieved_chunks: list[dict[str, Any]]) -> str:
    manifest = {
        "learning_objective": graph.get("learning_objective", ""),
        "sources": [
            {
                "id": source.get("id", ""),
                "title": source.get("title", ""),
                "type": source.get("type", ""),
                "url": source.get("url", ""),
                "has_segments": bool(source.get("segments")),
                "text_preview": str(source.get("text", ""))[:350],
            }
            for source in graph.get("sources", [])[:6]
        ],
        "retrieved_chunks": [
            {
                "id": chunk.get("id", ""),
                "source_id": chunk.get("source_id", ""),
                "source_title": chunk.get("source_title", ""),
                "source_type": chunk.get("source_type", ""),
                "location": _location(chunk),
                "concepts": chunk.get("concepts", []),
                "text": str(chunk.get("text", ""))[:500],
                "selected_because": chunk.get("selected_because", ""),
            }
            for chunk in retrieved_chunks[:5]
        ],
        "concepts": [
            {
                "name": concept.get("name", ""),
                "difficulty": concept.get("difficulty", 0.5),
                "bloom_level": concept.get("bloom_level", "understand"),
                "prerequisites": concept.get("prerequisites", []),
                "common_confusions": concept.get("common_confusions", []),
            }
            for concept in graph.get("concepts", [])[:6]
        ],
    }
    return SOURCE_ANALYSIS_PROMPT + "\n\nINPUT_JSON:\n" + json.dumps(manifest, separators=(",", ":"))


def _gemini_video_parts(graph: dict[str, Any]) -> list[dict[str, Any]]:
    parts = []
    seen: set[str] = set()
    for source in graph.get("sources", []):
        url = str(source.get("url", "")).strip()
        if not url or url in seen:
            continue
        if _is_public_video_url(url):
            parts.append({"file_data": {"file_uri": url}})
            seen.add(url)
        if len(parts) >= 3:
            break
    return parts


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("text"), str):
        return payload["text"]
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []):
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                return part["text"]
    raise KeyError("No Gemini text part found.")


def _normalize_model_result(
    result: dict[str, Any],
    graph: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    fallback = _fallback_source_analysis(graph, retrieved_chunks)
    if not isinstance(result, dict):
        return fallback

    compact_timestamps = result.get("timestamp_guide")
    source_insights = _source_insights_from_compact(result.get("source_notes"), graph, compact_timestamps)
    if not source_insights:
        source_insights = _list_or_default(result.get("source_insights"), fallback["source_insights"])

    video_timeline = _timeline_from_compact(
        compact_timestamps or result.get("video_timeline"),
        fallback["video_timeline"],
    )
    concepts = _concepts_from_compact(result.get("key_concepts") or result.get("concepts"))
    if not concepts:
        concepts = fallback["concepts"]

    student_video_lesson = _student_lesson_from_model_result(result, fallback["student_video_lesson"])
    normalized = {
        "summary": str(result.get("summary") or fallback["summary"]),
        "source_insights": source_insights,
        "video_timeline": video_timeline,
        "concepts": concepts,
        "visual_learning_cues": _list_or_default(result.get("visual_learning_cues"), fallback["visual_learning_cues"]),
        "page_sequence": fallback["page_sequence"],
        "questions_to_ask": fallback["questions_to_ask"],
        "video_learning_plan": _dict_or_default(result.get("video_learning_plan"), fallback["video_learning_plan"]),
        "student_video_lesson": student_video_lesson,
        "concept_diagrams": fallback["concept_diagrams"],
        "flowcharts": fallback["flowcharts"],
        "adaptive_quiz_blueprint": fallback["adaptive_quiz_blueprint"],
        "reteaching_plan": fallback["reteaching_plan"],
    }
    return normalized


def _source_insights_from_compact(
    value: Any,
    graph: dict[str, Any],
    timestamp_guide: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return []
    sources = {str(source.get("id", "")): source for source in graph.get("sources", [])}
    sections_by_source = _sections_from_compact_timestamps(timestamp_guide)
    insights: list[dict[str, Any]] = []
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        source_id = _compact_text(item.get("source_id"), 120)
        source = sources.get(source_id, {})
        title = _compact_text(item.get("title") or source.get("title"), 160)
        media_role = _compact_text(item.get("media_role"), 40) or (_media_role(source) if source else "other")
        bullets = clean_list_for_student(item.get("bullets", []))[:5]
        why_useful = _compact_text(item.get("why_useful") or item.get("why_chosen"), 260)
        insights.append(
            {
                "source_id": source_id,
                "title": title,
                "type": source.get("type", ""),
                "url": source.get("url", ""),
                "media_role": media_role,
                "why_chosen": why_useful or "Use for source-grounded learning.",
                "concepts": clean_list_for_student(item.get("concepts", []))[:6],
                "sections": sections_by_source.get(source_id, []),
                "bullets": bullets,
                "visual_cues": [],
            }
        )
    return insights


def _sections_from_compact_timestamps(value: Any) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(value, list):
        return sections
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        source_id = _compact_text(item.get("source_id"), 120)
        if not source_id:
            continue
        title = _compact_text(item.get("title"), 160) or "Source section"
        summary = _compact_text(item.get("what_happens") or item.get("teaches"), 300)
        sections.setdefault(source_id, []).append(
            {
                "start": _compact_text(item.get("start"), 40),
                "end": _compact_text(item.get("end"), 40),
                "title": title,
                "summary": summary,
                "source_chunk_id": "",
            }
        )
    return sections


def _timeline_from_compact(value: Any, default: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return default
    timeline: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        title = _compact_text(item.get("concept") or item.get("title"), 160)
        teaches = _compact_text(item.get("teaches") or item.get("what_happens"), 300)
        if not title and not teaches:
            continue
        timeline.append(
            {
                "source_id": _compact_text(item.get("source_id"), 120),
                "start": _compact_text(item.get("start"), 40),
                "end": _compact_text(item.get("end"), 40),
                "concept": title,
                "teaches": teaches,
            }
        )
    return timeline or default


def _concepts_from_compact(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    concepts: list[dict[str, str]] = []
    for item in value[:6]:
        if isinstance(item, dict):
            name = _compact_text(item.get("name") or item.get("concept") or item.get("title"), 120)
            why = _compact_text(item.get("why_it_matters") or item.get("why"), 260)
            trap = _compact_text(item.get("common_trap") or item.get("trap"), 200)
        else:
            name = _compact_text(item, 120)
            why = ""
            trap = ""
        if name:
            concepts.append(
                {
                    "name": name,
                    "why_it_matters": why or "It is needed for the source-backed lesson.",
                    "common_trap": trap or "Learners may remember the word but miss how to use it.",
                }
            )
    return concepts


def _student_lesson_from_model_result(result: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    lesson = dict(fallback)
    if isinstance(result.get("student_video_lesson"), dict):
        lesson.update(result["student_video_lesson"])

    summary = _compact_text(result.get("summary"), 600)
    if summary:
        lesson["one_minute_summary"] = summary

    facts = _key_facts_from_compact(result.get("key_facts"))
    if facts:
        lesson["key_facts"] = facts
        lesson["things_to_remember"] = _unique(
            [fact["fact"] for fact in facts[:4]] + clean_list_for_student(lesson.get("things_to_remember", []))
        )[:5]

    formula_cards = _formula_cards_from_compact(result.get("formulas") or result.get("formula_cards"))
    if formula_cards:
        lesson["formula_cards"] = formula_cards

    timestamps = _compact_timestamp_guide(result.get("timestamp_guide"))
    if timestamps:
        lesson["timestamp_guide"] = timestamps

    mistakes = clean_list_for_student(result.get("common_mistakes", []))[:8]
    if mistakes:
        lesson["common_mistakes"] = mistakes

    return lesson


def _key_facts_from_compact(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    facts: list[dict[str, str]] = []
    for item in value[:8]:
        if isinstance(item, dict):
            fact = _compact_text(item.get("fact") or item.get("text"), 300)
            why = _compact_text(item.get("why_it_matters") or item.get("why"), 220)
        else:
            fact = _compact_text(item, 300)
            why = ""
        if fact:
            facts.append({"fact": fact, "why_it_matters": why or _why_fact_matters(fact, "")})
    return facts


def _formula_cards_from_compact(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    cards: list[dict[str, str]] = []
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        label = _compact_text(item.get("label") or item.get("name"), 120)
        latex = _compact_text(item.get("latex") or item.get("formula"), 120, allow_source_noise=True)
        meaning = _compact_text(item.get("meaning"), 260)
        when_to_use = _compact_text(item.get("when_to_use") or item.get("use"), 260)
        if label or latex or meaning:
            cards.append(
                {
                    "label": label or "Formula or rule",
                    "latex": latex,
                    "meaning": meaning or "Use the source definition before applying this.",
                    "when_to_use": when_to_use or "Use when the question matches the source-backed condition.",
                }
            )
    return cards


def _compact_timestamp_guide(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    timestamps: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        title = _compact_text(item.get("title") or item.get("concept"), 160)
        what_happens = _compact_text(item.get("what_happens") or item.get("teaches"), 300)
        if not title and not what_happens:
            continue
        timestamps.append(
            {
                "start": _compact_text(item.get("start"), 40),
                "end": _compact_text(item.get("end"), 40),
                "title": title or "Useful source moment",
                "what_happens": what_happens,
                "watch_for": clean_list_for_student(item.get("watch_for", []))[:4]
                or ["definition", "example", "common mistake"],
            }
        )
    return timestamps


def _compact_text(value: Any, limit: int, allow_source_noise: bool = False) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or (not allow_source_noise and _looks_like_source_noise(text)):
        return ""
    return text[:limit]


def _fallback_source_analysis(graph: dict[str, Any], retrieved_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    chunks_by_source: dict[str, list[dict[str, Any]]] = {}
    for chunk in retrieved_chunks or graph.get("chunks", [])[:8]:
        chunks_by_source.setdefault(str(chunk.get("source_id", "")), []).append(chunk)

    insights = []
    for source in graph.get("sources", [])[:10]:
        source_chunks = chunks_by_source.get(str(source.get("id", "")), [])
        if not source_chunks:
            source_chunks = [
                chunk for chunk in graph.get("chunks", []) if chunk.get("source_id") == source.get("id")
            ][:2]
        concepts = _unique(
            concept
            for chunk in source_chunks
            for concept in chunk.get("concepts", [])
        )
        bullets = _bullets_from_chunks(source_chunks, source)
        sections = [
            section
            for section in (_section_from_chunk(chunk, index) for index, chunk in enumerate(source_chunks[:4], start=1))
            if section.get("summary")
        ]
        insights.append(
            {
                "source_id": source.get("id", ""),
                "title": source.get("title", ""),
                "type": source.get("type", ""),
                "url": source.get("url", ""),
                "media_role": _media_role(source),
                "why_chosen": _why_source(source, concepts),
                "concepts": concepts[:6],
                "sections": sections,
                "bullets": bullets,
                "visual_cues": _visual_cues_for_concepts(concepts, graph),
            }
        )

    concepts = [
        {
            "name": concept.get("name", ""),
            "why_it_matters": _concept_reason(concept, graph),
            "common_trap": ", ".join(concept.get("common_confusions", [])[:2])
            or "Learners may know the definition but fail on transfer.",
        }
        for concept in graph.get("concepts", [])[:7]
    ]
    visual_cues = [
        {
            "cue": cue,
            "target_gap": "separate definition, representation, and application",
            "best_after": "first checkpoint",
        }
        for cue in _visual_cues_for_concepts([item["name"] for item in concepts], graph)[:6]
    ]
    video_learning_plan = _video_learning_plan(graph, insights)
    return {
        "status": "deterministic_fallback",
        "provider": "local",
        "summary": "Parsed sources and retrieved chunks were converted into a first-pass learning sequence.",
        "source_insights": insights,
        "video_timeline": _video_timeline(insights),
        "concepts": concepts,
        "visual_learning_cues": visual_cues,
        "page_sequence": _page_sequence(graph),
        "questions_to_ask": _questions_to_ask(graph),
        "video_learning_plan": video_learning_plan,
        "student_video_lesson": _student_video_lesson(
            graph,
            insights,
            video_learning_plan,
        ),
        "concept_diagrams": _concept_diagrams(graph),
        "flowcharts": _flowcharts(graph),
        "adaptive_quiz_blueprint": _adaptive_quiz_blueprint(graph),
        "reteaching_plan": _reteaching_plan(graph),
        "reason": "Local source analysis ran from parsed sources and RAG chunks.",
    }


def _list_or_default(value: Any, default: list[Any]) -> list[Any]:
    if not isinstance(value, list) or not value:
        return default
    return value


def _dict_or_default(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        return default
    return value


def _media_role(source: dict[str, Any]) -> str:
    source_type = str(source.get("type", "")).lower()
    url = str(source.get("url", "")).lower()
    if "video" in source_type or _is_public_video_url(url):
        return "video"
    if source_type == "video_transcript":
        return "transcript"
    if source_type == "pdf" or url.endswith(".pdf") or source.get("mime_type") == "application/pdf":
        return "pdf"
    if "worksheet" in source_type:
        return "worksheet"
    if source.get("url"):
        return "web"
    if "note" in source_type or "document" in source_type:
        return "notes"
    return "other"


def _is_public_video_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "youtube.com/watch" in lowered
        or "youtu.be/" in lowered
        or lowered.endswith((".mp4", ".mov", ".webm", ".mpeg", ".mpg"))
    )


def _why_source(source: dict[str, Any], concepts: list[str]) -> str:
    role = _media_role(source)
    if role == "video":
        return "Use as the opening lesson media because it can show sequencing, visuals, and spoken explanation."
    if role == "transcript":
        return "Use for timestamped concept anchors and quote-level grounding."
    if role == "pdf":
        return "Use as a stable reference for definitions, formulas, and scope control."
    if role == "worksheet":
        return "Use for worked examples, checks, and final transfer practice."
    if concepts:
        return f"Use for grounding {', '.join(concepts[:3])}."
    return "Use for objective-aligned source grounding."


def _section_from_chunk(chunk: dict[str, Any], index: int) -> dict[str, Any]:
    concepts = chunk.get("concepts", [])
    title = concepts[0] if concepts else f"Source section {index}"
    summary = _first_sentence(str(chunk.get("text", "")))
    if _looks_like_source_noise(summary):
        summary = ""
    return {
        "start": str(chunk.get("start", "")),
        "end": str(chunk.get("end", "")),
        "title": title,
        "summary": summary,
        "source_chunk_id": chunk.get("id", ""),
    }


def _bullets_from_chunks(chunks: list[dict[str, Any]], source: dict[str, Any]) -> list[str]:
    bullets = []
    for chunk in chunks[:3]:
        sentence = _first_sentence(str(chunk.get("text", "")))
        if sentence and not _looks_like_source_noise(sentence) and sentence not in bullets:
            bullets.append(sentence)
    if not bullets and source.get("text"):
        sentence = _first_sentence(str(source.get("text", "")))
        if sentence and not _looks_like_source_noise(sentence):
            bullets.append(sentence)
    return [bullet for bullet in bullets if bullet][:4]


def _first_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return parts[0][:260]


def _looks_like_source_noise(text: str) -> bool:
    lower = text.lower()
    if any(token in lower for token in ["/filter", "/flatedecode", "function()", "ytplayer", "client_canary_state", "xref"]):
        return True
    weird = sum(1 for char in text if char in "{}<>/\\\ufffd")
    return weird / max(1, len(text)) > 0.16


def _visual_cues_for_concepts(concepts: list[str], graph: dict[str, Any]) -> list[str]:
    cues: list[str] = []
    concept_lookup = {concept.get("name", ""): concept for concept in graph.get("concepts", [])}
    for concept in concepts:
        meta = concept_lookup.get(concept, {})
        confusions = meta.get("common_confusions", [])
        if confusions:
            cues.append(f"Contrast {concept} with {confusions[0]}")
        elif concept:
            cues.append(f"Build a formula or definition card for {concept}")
    if not cues:
        cues = [
            "Use a three-column definition, representation, application board",
            "Add a flowchart that separates read, reason, calculate, check",
        ]
    return _unique(cues)[:6]


def _concept_reason(concept: dict[str, Any], graph: dict[str, Any]) -> str:
    bloom = concept.get("bloom_level", "understand")
    objective = graph.get("learning_objective", "the objective")
    return f"It is a {bloom} level idea needed to complete {objective}."


def _video_timeline(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = []
    for insight in insights:
        if insight.get("media_role") not in {"video", "transcript"}:
            continue
        for section in insight.get("sections", []):
            timeline.append(
                {
                    "source_id": insight.get("source_id", ""),
                    "start": section.get("start", ""),
                    "end": section.get("end", ""),
                    "concept": section.get("title", ""),
                    "teaches": section.get("summary", ""),
                }
            )
    return timeline[:8]


def _page_sequence(graph: dict[str, Any]) -> list[dict[str, Any]]:
    primary = graph.get("concepts", [{}])[0].get("name", "core concept") if graph.get("concepts") else "core concept"
    return [
        {
            "id": "source_media_lesson",
            "page_type": "media_lesson",
            "title": "Understand the source",
            "intent": f"Use video, PDF, and notes to introduce {primary} with source grounding.",
            "interaction": "read extracted ideas, open reference only if needed, mark one confusing idea",
            "unlocks_next": "notes_checkpoint",
        },
        {
            "id": "notes_checkpoint",
            "page_type": "checkpoint",
            "title": "Check the first understanding",
            "intent": "Collect concept, confidence, timing, and source-grounding signals while teaching.",
            "interaction": "MCQ, typed explanation, and visual-map probe",
            "unlocks_next": "visual_repair",
        },
        {
            "id": "visual_repair",
            "page_type": "visual_repair",
            "title": "Repair with a flowchart",
            "intent": "Convert weak or ambiguous signals into a diagram, contrast, and memory card.",
            "interaction": "complete the flowchart and explain one trap",
            "unlocks_next": "practice_mix",
        },
        {
            "id": "practice_mix",
            "page_type": "practice",
            "title": "Mixed practice",
            "intent": "Mix repeats and fresh variants based on checkpoint evidence.",
            "interaction": "short quiz plus one written step",
            "unlocks_next": "final_dynamic_case",
        },
        {
            "id": "final_dynamic_case",
            "page_type": "case",
            "title": "Final transfer case",
            "intent": "Require a proof-of-work output that can update the learner model.",
            "interaction": "written answer with reasoning, source citation, and confidence",
            "unlocks_next": "revision_loop",
        },
    ]


def _questions_to_ask(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = [concept.get("name", "") for concept in graph.get("concepts", []) if concept.get("name")]
    primary = concepts[0] if concepts else "the main concept"
    secondary = concepts[1] if len(concepts) > 1 else "the prerequisite"
    return [
        {
            "type": "mcq",
            "prompt": f"Which source-backed statement best separates {primary} from {secondary}?",
            "captures": ["recognition", "concept_discrimination", "confidence"],
        },
        {
            "type": "typed_explanation",
            "prompt": f"Explain {primary} in two sentences and point to the source section that supports it.",
            "captures": ["text_comprehension", "written_reasoning", "source_grounding"],
        },
        {
            "type": "visual_map",
            "prompt": f"Place {primary}, {secondary}, prerequisite, and common trap on a four-node map.",
            "captures": ["visual_interpretation", "concept_edges", "misconception"],
        },
    ]


def _video_learning_plan(graph: dict[str, Any], insights: list[dict[str, Any]]) -> dict[str, Any]:
    concepts = _lesson_concept_names(graph)
    primary = concepts[0] if concepts else "the target concept"
    secondary = concepts[1] if len(concepts) > 1 else "the prerequisite idea"
    video_insights = [insight for insight in insights if insight.get("media_role") in {"video", "transcript"}]
    segments: list[dict[str, Any]] = []
    for insight in video_insights[:3]:
        sections = insight.get("sections") or [
            {
                "start": "",
                "end": "",
                "title": concept,
                "summary": "",
                "source_chunk_id": "",
            }
            for concept in insight.get("concepts", [])[:3]
        ]
        for section in sections[:4]:
            summary = str(section.get("summary", ""))
            raw_title = section.get("title") or primary
            concept = primary if primary.lower() in summary.lower() else raw_title
            watch_goal = (
                f"Understand this idea: {summary}"
                if summary
                else f"Watch for how {concept} is defined or used."
            )
            segments.append(
                {
                    "source_id": insight.get("source_id", ""),
                    "start": section.get("start", ""),
                    "end": section.get("end", ""),
                    "title": concept,
                    "watch_goal": watch_goal,
                    "signals_to_notice": [
                        "definition words",
                        "diagram or board transition",
                        "example setup before calculation",
                    ],
                    "noise_to_ignore": ["intro/outro", "decorative text", "unrelated recap"],
                    "pause_prompt": f"Pause and write the one line that explains {concept}.",
                    "self_explanation_prompt": f"Why does this step follow from {secondary} rather than from memorizing a formula?",
                    "retrieval_check": f"Without replaying, state {concept} and one trap in your own words.",
                    "expected_evidence": [
                        "source_grounding",
                        "self_explanation_quality",
                        "concept_discrimination",
                        "confidence",
                    ],
                }
            )
    if not segments:
        segments = [
            {
                "source_id": "",
                "start": "",
                "end": "",
                "title": primary,
                "watch_goal": f"Watch for the definition, representation, and use of {primary}.",
                "signals_to_notice": ["definition", "visual representation", "worked example"],
                "noise_to_ignore": ["intro/outro", "off-topic source noise"],
                "pause_prompt": f"Pause after the first explanation of {primary}.",
                "self_explanation_prompt": f"Explain how {primary} connects to {secondary}.",
                "retrieval_check": f"Close the video and write one sentence defining {primary}.",
                "expected_evidence": ["attention", "recall", "self_explanation", "confidence"],
            }
        ]
    return {
        "pre_watch": [
            {
                "label": "Prime terms",
                "prompt": f"Before watching, name what {primary} is and how it differs from {secondary}.",
                "why": "Pre-training key names reduces overload during the video.",
            },
            {
                "label": "Watch target",
                "prompt": "Do not take full notes. Capture only definitions, diagrams, traps, and one example.",
                "why": "Signaling focuses attention on information that supports transfer.",
            },
        ],
        "segments": segments[:6],
        "after_watch": [
            {
                "label": "One-minute recall",
                "task": "Write the core idea without replaying the video.",
                "evidence": ["retrieval_success", "text_comprehension", "confidence_calibration"],
            },
            {
                "label": "Self-explain",
                "task": "Explain why the worked step follows; do not just repeat the formula.",
                "evidence": ["causal_link_quality", "step_order_quality", "misconception"],
            },
            {
                "label": "Map it",
                "task": "Draw a four-node map: prerequisite, target concept, trap, example.",
                "evidence": ["visual_interpretation", "concept_edges", "transfer_seed"],
            },
        ],
        "research_basis": [
            "segmenting",
            "signaling",
            "weeding",
            "pre-training",
            "interpolated retrieval",
            "self-explanation",
        ],
    }


def _student_video_lesson(
    graph: dict[str, Any],
    insights: list[dict[str, Any]],
    video_plan: dict[str, Any],
) -> dict[str, Any]:
    concepts = _lesson_concept_names(graph)
    primary = concepts[0] if concepts else "the main idea"
    secondary = concepts[1] if len(concepts) > 1 else "a related idea"
    concept_lookup = {concept.get("name", ""): concept for concept in graph.get("concepts", [])}
    trap = (
        (concept_lookup.get(primary, {}).get("common_confusions") or [secondary])[0]
        if primary in concept_lookup
        else secondary
    )

    facts = _learner_facts_from_insights(insights, primary, secondary)
    formula_cards = _formula_cards_from_facts(facts, primary)
    timestamp_guide = _timestamp_guide_from_plan(video_plan, facts, primary)
    remember = _unique(
        [
            f"Say the meaning of {primary} before using a formula.",
            f"Keep {primary} separate from {trap}.",
            "After each formula, name what every symbol means.",
            "Use the video timestamp when a step feels unclear.",
        ]
    )[:5]
    tips = [
        "Use one short video part, then pause and write the idea in your own words.",
        "Do not copy the whole video. Capture definition, formula, trap, and example.",
        "When two ideas look similar, make a two-column comparison.",
        "Try one question without replaying the video before checking again.",
    ]
    return {
        "friendly_title": f"{primary}: learn it from the video",
        "one_minute_summary": (
            f"This lesson is about {primary}. First understand the idea in simple words, "
            f"then connect it to the formula or example, and finally avoid confusing it with {trap}."
        ),
        "key_facts": [
            {"fact": fact, "why_it_matters": _why_fact_matters(fact, primary)}
            for fact in facts[:5]
        ],
        "formula_cards": formula_cards,
        "things_to_remember": remember,
        "tips_and_tricks": tips,
        "shortcuts": [
            "First ask: what quantity is being described?",
            "Then choose the formula and name each symbol.",
            "Finally check units and signs before calculating.",
            f"If confused, compare {primary} with {trap}.",
        ],
        "timestamp_guide": timestamp_guide,
        "mindmap": {
            "center": primary,
            "branches": [
                {"label": "Meaning", "points": facts[:2] or [f"What {primary} means in words."]},
                {"label": "Formula or rule", "points": _formula_like_facts(facts) or ["Write the formula only after the meaning is clear."]},
                {"label": "Trap", "points": [f"Do not mix it up with {trap}."]},
                {"label": "Use in questions", "points": ["Identify what is given, choose the rule, then check units/signs."]},
            ],
        },
        "diagram_prompts": [
            {
                "title": "Draw the idea path",
                "description": f"Make a simple diagram that connects {secondary}, {primary}, formula, and example.",
                "steps": [
                    f"Write {secondary} on the left.",
                    f"Put {primary} in the center.",
                    "Add the formula or rule under it.",
                    "Add one example on the right.",
                    f"Draw a warning arrow to the trap: {trap}.",
                ],
            },
            {
                "title": "Make a two-column trap chart",
                "description": f"Compare {primary} with {trap} so the common mistake becomes visible.",
                "steps": [
                    f"Column 1: {primary}.",
                    f"Column 2: {trap}.",
                    "Add meaning, formula/rule, and one example in each column.",
                ],
            },
        ],
        "common_mistakes": [
            f"Using the formula before explaining what {primary} means.",
            f"Treating {primary} and {trap} as the same idea.",
            "Rewatching passively without doing a recall check.",
        ],
        "audio_overview_script": _audio_overview_script(primary, trap, facts, formula_cards),
        "tiny_check": {
            "prompt": f"In two lines, explain {primary} and one way it differs from {trap}.",
            "expected": "A clear meaning, one contrast, and one source-backed detail.",
        },
    }


def _learner_facts_from_insights(
    insights: list[dict[str, Any]],
    primary: str,
    secondary: str,
) -> list[str]:
    facts: list[str] = []
    for insight in insights:
        if insight.get("media_role") not in {"video", "transcript"}:
            continue
        for bullet in insight.get("bullets", []):
            text = _first_sentence(str(bullet))
            if text and not _looks_like_source_noise(text):
                facts.append(text)
        for section in insight.get("sections", []):
            text = _first_sentence(str(section.get("summary", "")))
            if text and not _looks_like_source_noise(text):
                facts.append(text)
    facts = _unique(facts)
    if facts:
        return facts[:6]
    return [
        f"{primary} is the main idea of this lesson.",
        f"{primary} must be understood in words before solving questions.",
        f"A common trap is confusing {primary} with {secondary}.",
        "Use one worked example to connect the definition to the question.",
    ]


def _timestamp_guide_from_plan(
    video_plan: dict[str, Any],
    facts: list[str],
    primary: str,
) -> list[dict[str, Any]]:
    guide = []
    for index, segment in enumerate(video_plan.get("segments", [])[:6], start=1):
        if not isinstance(segment, dict):
            continue
        title = str(segment.get("title") or f"Part {index}").strip()
        what_happens = (
            str(segment.get("watch_goal") or "").replace("Watch only for ", "This part shows ")
            or (facts[index - 1] if index - 1 < len(facts) else f"This part explains {primary}.")
        )
        guide.append(
            {
                "start": str(segment.get("start", "")),
                "end": str(segment.get("end", "")),
                "title": title,
                "what_happens": what_happens,
                "watch_for": clean_list_for_student(segment.get("signals_to_notice", []))[:3]
                or ["definition", "example", "common mistake"],
            }
        )
    if guide:
        return guide
    return [
        {
            "start": "",
            "end": "",
            "title": primary,
            "what_happens": f"Use this video part to understand {primary} in simple words.",
            "watch_for": ["definition", "formula or rule", "example"],
        }
    ]


def clean_list_for_student(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        text = _first_sentence(str(value))
        if text and not _looks_like_source_noise(text):
            result.append(text)
    return _unique(result)


def _formula_like_facts(facts: list[str]) -> list[str]:
    formula_tokens = ("=", "equals", "formula", "rule", "divided", "per unit", "add")
    return [fact for fact in facts if any(token in fact.lower() for token in formula_tokens)][:3]


def _formula_cards_from_facts(facts: list[str], primary: str) -> list[dict[str, str]]:
    joined = " ".join(facts).lower()
    primary_lower = primary.lower()
    cards: list[dict[str, str]] = []
    if "work" in joined and ("per unit" in joined or "charge" in joined):
        cards.append(
            {
                "label": "Potential from work",
                "latex": "V = \\frac{W}{q}",
                "meaning": "Potential is work done per unit positive test charge.",
                "when_to_use": "Use this when the problem connects work, charge, and potential.",
            }
        )
    if "point charge" in joined or ("kq" in joined and "r" in joined) or "electric potential" in primary_lower:
        cards.append(
            {
                "label": "Point charge potential",
                "latex": "V = \\frac{kQ}{r}",
                "meaning": "A point charge creates potential that decreases with distance.",
                "when_to_use": "Use this for potential at a point due to one point charge.",
            }
        )
    if "add" in joined or "many charges" in joined or "multiple" in joined:
        cards.append(
            {
                "label": "Many charges",
                "latex": "V_{net} = V_1 + V_2 + V_3 + \\cdots",
                "meaning": "Electric potential is scalar, so potentials add directly.",
                "when_to_use": "Use this when more than one charge contributes to the same point.",
            }
        )
    return cards[:4]


def _audio_overview_script(
    primary: str,
    trap: str,
    facts: list[str],
    formula_cards: list[dict[str, str]],
) -> str:
    fact_lines = " ".join(facts[:3]) if facts else f"{primary} is the main idea."
    formula_line = ""
    if formula_cards:
        first = formula_cards[0]
        formula_line = f"The key formula is {first.get('latex', '')}, which means {first.get('meaning', '')} "
    return (
        f"Here is the short version. The lesson is about {primary}. {fact_lines} "
        f"{formula_line}Do not mix it up with {trap}. "
        "When solving, first say the meaning in words, then choose the formula, then check units and signs. "
        "After that, try one fresh question without replaying the video."
    )


def _why_fact_matters(fact: str, primary: str) -> str:
    lower = fact.lower()
    if "mistake" in lower or "confus" in lower or "trap" in lower:
        return "This prevents the most likely wrong answer."
    if "=" in fact or "equals" in lower or "formula" in lower:
        return "This is what you will use while solving."
    if primary.lower() in lower:
        return "This anchors the main concept."
    return "This helps connect the video to practice."


def _lesson_concept_names(graph: dict[str, Any]) -> list[str]:
    names = [concept.get("name", "") for concept in graph.get("concepts", []) if concept.get("name")]
    objective = str(graph.get("learning_objective", "")).lower()
    objective_matches = [name for name in names if name.lower() in objective]
    if not objective_matches:
        target = _target_phrase_from_objective(graph.get("learning_objective", ""))
        objective_matches = [target] if target else []
    return _unique(objective_matches + [name for name in names if name not in objective_matches])


def _target_phrase_from_objective(objective: str) -> str:
    text = re.sub(r"\s+", " ", str(objective or "")).strip()
    match = re.search(r"\b(?:understand|learn|explain|master)\s+(.+?)(?:\s+and\s+|\s+to\s+|[.;,]|$)", text, re.I)
    if not match:
        return ""
    phrase = match.group(1).strip()
    phrase = re.sub(r"\b(?:how to|the|a|an)\b", "", phrase, flags=re.I).strip()
    return phrase[:80].title() if phrase else ""


def _concept_diagrams(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = graph.get("concepts", [])
    if not concepts:
        return []
    primary = concepts[0]
    primary_name = primary.get("name", "core concept")
    prereq = (primary.get("prerequisites") or [concepts[1].get("name", "prerequisite") if len(concepts) > 1 else "source definition"])[0]
    trap = (primary.get("common_confusions") or [concepts[1].get("name", "common trap") if len(concepts) > 1 else "surface memorization"])[0]
    application = concepts[2].get("name", "new problem") if len(concepts) > 2 else "new problem"
    diagrams = [
        {
            "title": f"{primary_name}: source-to-solution map",
            "concept": primary_name,
            "nodes": [
                {"id": "source", "label": "source anchor", "kind": "definition"},
                {"id": "prereq", "label": prereq, "kind": "prerequisite"},
                {"id": "target", "label": primary_name, "kind": "formula"},
                {"id": "application", "label": application, "kind": "application"},
                {"id": "check", "label": f"not {trap}", "kind": "check"},
            ],
            "edges": [
                {"from": "source", "to": "target", "label": "defines"},
                {"from": "prereq", "to": "target", "label": "supports"},
                {"from": "target", "to": "application", "label": "applies to"},
                {"from": "target", "to": "check", "label": "contrast"},
            ],
            "takeaway": f"Learn {primary_name} by linking definition, prerequisite, application, and trap check.",
        }
    ]
    if len(concepts) > 1:
        secondary = concepts[1]
        secondary_name = secondary.get("name", "related idea")
        diagrams.append(
            {
                "title": f"{primary_name} vs {secondary_name}",
                "concept": primary_name,
                "nodes": [
                    {"id": "left", "label": primary_name, "kind": "definition"},
                    {"id": "right", "label": secondary_name, "kind": "definition"},
                    {"id": "similarity", "label": "same problem family", "kind": "check"},
                    {"id": "difference", "label": _difference_label(primary_name, secondary_name), "kind": "trap"},
                ],
                "edges": [
                    {"from": "left", "to": "similarity", "label": "appears with"},
                    {"from": "right", "to": "similarity", "label": "appears with"},
                    {"from": "similarity", "to": "difference", "label": "separate by"},
                ],
                "takeaway": "The repair page should make the learner state the difference before calculating.",
            }
        )
    return diagrams[:3]


def _flowcharts(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = graph.get("concepts", [])
    primary = concepts[0].get("name", "the target concept") if concepts else "the target concept"
    secondary = concepts[1].get("name", "the prerequisite") if len(concepts) > 1 else "the prerequisite"
    trap = "the nearest-looking concept"
    if concepts:
        trap = (concepts[0].get("common_confusions") or [trap])[0]
    return [
        {
            "title": f"How to reason through {primary}",
            "concept": primary,
            "steps": [
                {
                    "label": "Anchor",
                    "action": f"Find the source line or note that defines {primary}.",
                    "check": "Can the learner point to a source section?",
                },
                {
                    "label": "Separate",
                    "action": f"Say how {primary} differs from {trap}.",
                    "check": "Does the answer avoid concept substitution?",
                },
                {
                    "label": "Connect",
                    "action": f"Use {secondary} only as a support, not as the final answer.",
                    "check": "Is the prerequisite used in the right order?",
                },
                {
                    "label": "Apply",
                    "action": "Solve a small variant and explain why each step follows.",
                    "check": "Does reasoning survive a fresh example?",
                },
            ],
            "misconception_fixed": f"Confusing {primary} with {trap}.",
        }
    ]


def _adaptive_quiz_blueprint(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = [concept.get("name", "") for concept in graph.get("concepts", []) if concept.get("name")]
    if not concepts:
        concepts = ["core concept"]
    rows = []
    for index, concept in enumerate(concepts[:4]):
        rows.append(
            {
                "concept": concept,
                "mix": "40-60% repeat-style variants for missed items, 40-60% fresh equivalents; exact split changes after evidence.",
                "question_types": [
                    "mcq",
                    "typed_explanation",
                    "visual_map" if index == 0 else "worked_step",
                    "fresh_variant",
                    "repeat_variant",
                ],
                "repeat_policy": (
                    "If wrong, repeat the same concept with changed numbers/context and one stronger hint. "
                    "Some original traps can reappear, but never as a fixed identical set."
                ),
                "fresh_variant_policy": (
                    "If right and confident, move to a new surface form that tests the same concept edge."
                ),
            }
        )
    return rows


def _reteaching_plan(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = graph.get("concepts", [])[:4]
    if not concepts:
        return []
    plan = []
    for concept in concepts:
        name = concept.get("name", "target concept")
        trap = (concept.get("common_confusions") or ["nearby concept"])[0]
        plan.append(
            {
                "concept": name,
                "trigger": "wrong answer, low confidence, slow response after hint, or concept-map edge error",
                "mode": "visual_contrast" if concept.get("common_confusions") else "worked_example",
                "explanation": f"Reteach {name} by contrasting it against {trap}, then show one source-backed worked step.",
                "next_check": f"Ask for a two-sentence explanation of {name} plus one fresh variant.",
            }
        )
    return plan


def _difference_label(primary: str, secondary: str) -> str:
    p = primary.lower()
    s = secondary.lower()
    if "potential" in p and "field" in s:
        return "scalar value vs vector field"
    if "field" in p and "potential" in s:
        return "vector field vs scalar value"
    if "potential" in p and "energy" in s:
        return "per unit charge vs charge-specific energy"
    return "definition, representation, and use case"


def _location(chunk: dict[str, Any]) -> str:
    return f"{chunk.get('start', '')}-{chunk.get('end', '')}".strip("-") or str(chunk.get("id", ""))


def _unique(values: Any) -> list[str]:
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _redact(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
    return re.sub(r"(key=)[^&\s]+", r"\1[redacted]", text)
