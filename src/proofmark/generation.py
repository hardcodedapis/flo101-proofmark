from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .content_graph import KNOWN_CONCEPTS
from .provider_runtime import cached_json, parse_provider_json_object, provider_error_from_http, with_provider_retries
from .providers import ProviderError, _extract_response_text

DEFAULT_OPENAI_MODEL = ""


GENERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "next_learning_plan": {"type": "array", "items": {"type": "string"}},
        "personalized_notes": {"type": "array", "items": {"type": "string"}},
        "mind_map_changes": {"type": "array", "items": {"type": "string"}},
        "video_or_source_sections": {"type": "array", "items": {"type": "string"}},
        "roleplay_or_voice_task": {"type": "string"},
        "hint_ladder": {"type": "array", "items": {"type": "string"}},
        "micro_assessment": {"type": "array", "items": {"type": "string"}},
        "evidence_to_collect_next": {"type": "array", "items": {"type": "string"}},
        "student_study_pack": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "one_minute_summary": {"type": "string"},
                "key_facts": {"type": "array", "items": {"type": "string"}},
                "formula_cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "latex": {"type": "string"},
                            "meaning": {"type": "string"},
                            "when_to_use": {"type": "string"},
                        },
                        "required": ["label", "latex", "meaning", "when_to_use"],
                    },
                },
                "things_to_remember": {"type": "array", "items": {"type": "string"}},
                "tips_and_tricks": {"type": "array", "items": {"type": "string"}},
                "shortcuts": {"type": "array", "items": {"type": "string"}},
                "mind_map_branches": {"type": "array", "items": {"type": "string"}},
                "diagram_ideas": {"type": "array", "items": {"type": "string"}},
                "voice_over_script": {"type": "string"},
            },
            "required": [
                "one_minute_summary",
                "key_facts",
                "formula_cards",
                "things_to_remember",
                "tips_and_tricks",
                "shortcuts",
                "mind_map_branches",
                "diagram_ideas",
                "voice_over_script",
            ],
        },
        "concept_diagrams": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "concept": {"type": "string"},
                    "nodes": {"type": "array", "items": {"type": "string"}},
                    "edges": {"type": "array", "items": {"type": "string"}},
                    "takeaway": {"type": "string"},
                },
                "required": ["title", "concept", "nodes", "edges", "takeaway"],
            },
        },
        "flowcharts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "misconception_fixed": {"type": "string"},
                },
                "required": ["title", "steps", "misconception_fixed"],
            },
        },
        "visual_artifact": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "kind": {"type": "string"},
                "title": {"type": "string"},
                "concept": {"type": "string"},
                "learner_goal": {"type": "string"},
                "instructions": {"type": "array", "items": {"type": "string"}},
                "draw_question": {"type": "string"},
                "expected_features": {"type": "array", "items": {"type": "string"}},
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "role": {"type": "string"},
                        },
                        "required": ["id", "label", "x", "y", "role"],
                    },
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "label": {"type": "string"},
                            "kind": {"type": "string"},
                        },
                        "required": ["from", "to", "label", "kind"],
                    },
                },
                "rays": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "from_x": {"type": "number"},
                            "from_y": {"type": "number"},
                            "to_x": {"type": "number"},
                            "to_y": {"type": "number"},
                            "label": {"type": "string"},
                            "style": {"type": "string"},
                        },
                        "required": ["from_x", "from_y", "to_x", "to_y", "label", "style"],
                    },
                },
                "annotations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "text": {"type": "string"},
                        },
                        "required": ["x", "y", "text"],
                    },
                },
            },
            "required": [
                "kind",
                "title",
                "concept",
                "learner_goal",
                "instructions",
                "draw_question",
                "expected_features",
                "nodes",
                "edges",
                "rays",
                "annotations",
            ],
        },
        "adaptive_quiz_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "concept": {"type": "string"},
                    "mix": {"type": "string"},
                    "question": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["concept", "mix", "question", "why"],
            },
        },
        "reteaching_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "concept": {"type": "string"},
                    "mode": {"type": "string"},
                    "trigger": {"type": "string"},
                    "next_check": {"type": "string"},
                },
                "required": ["concept", "mode", "trigger", "next_check"],
            },
        },
        "forgetting_curve_notes": {"type": "array", "items": {"type": "string"}},
        "why_this_plan": {"type": "string"},
    },
    "required": [
        "next_learning_plan",
        "personalized_notes",
        "mind_map_changes",
        "video_or_source_sections",
        "roleplay_or_voice_task",
        "hint_ladder",
        "micro_assessment",
        "evidence_to_collect_next",
        "student_study_pack",
        "concept_diagrams",
        "flowcharts",
        "visual_artifact",
        "adaptive_quiz_plan",
        "reteaching_plan",
        "forgetting_curve_notes",
        "why_this_plan",
    ],
}


GENERATION_PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "next_learning_plan": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "personalized_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "micro_assessment": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "evidence_to_collect_next": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "student_study_pack": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "one_minute_summary": {"type": "string", "maxLength": 700},
                "key_facts": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "formula_cards": {
                    "type": "array",
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "latex": {"type": "string"},
                            "meaning": {"type": "string"},
                            "when_to_use": {"type": "string"},
                        },
                        "required": ["label", "latex", "meaning", "when_to_use"],
                    },
                },
                "things_to_remember": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                "tips_and_tricks": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                "shortcuts": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                "mind_map_branches": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                "diagram_ideas": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                "voice_over_script": {"type": "string", "maxLength": 900},
            },
            "required": [
                "one_minute_summary",
                "key_facts",
                "formula_cards",
                "things_to_remember",
                "tips_and_tricks",
                "shortcuts",
                "mind_map_branches",
                "diagram_ideas",
                "voice_over_script",
            ],
        },
        "visual_artifact": GENERATION_SCHEMA["properties"]["visual_artifact"],
        "why_this_plan": {"type": "string", "maxLength": 600},
    },
    "required": [
        "next_learning_plan",
        "personalized_notes",
        "micro_assessment",
        "evidence_to_collect_next",
        "student_study_pack",
        "visual_artifact",
        "why_this_plan",
    ],
}


GENERATION_INSTRUCTIONS = """
You generate the next learning assets for a Track B content curator and dynamic case builder.

Use only the supplied learner-state summary and retrieved source chunks.
Do not invent unsupported facts.
Do not describe the learner as a fixed visual/audio/text learner.
Treat notes, visual cues, voice, roleplay, hints, quizzes, and cases as interventions selected from evidence.
Return a compact patch only. The backend already has deterministic plans, flowcharts, quiz plans, reteaching plans, and review timing; do not regenerate those.
Generate visual_artifact as the main renderable AI diagram: use coordinate nodes, edges, rays, annotations, and a draw_question that asks the learner to draw or explain the same diagram. Coordinates must use the 720 by 360 SVG canvas, not normalized 0-1 coordinates. Keep labels short. For physics optics, include principal axis, lens/center/focus nodes, object/image nodes, and at least two principal rays when supported by the source.
If source_analysis_summary contains a student_video_lesson, refine it into learner-friendly study material. Use simple words: summary, facts, formulas, remember, shortcuts, mind map, diagram, and voice overview. Do not expose source ids, telemetry labels, provider names, or chunk ids.
Formula cards must use LaTeX that KaTeX can render, define each symbol in words, and say when to use it.
Voice overview script should be 45-75 seconds, conversational, source-grounded, and usable by ElevenLabs text-to-speech.
Return concise JSON matching the compact patch schema.
"""


def generate_learning_assets(
    packet: dict[str, Any],
    enabled: bool | None = None,
    api_key: str = "",
    model: str = "",
) -> dict[str, Any]:
    should_call = enabled
    if should_call is None:
        should_call = os.getenv("PROOFLOOP_GENERATE_WITH_MODEL", "").lower() in {"1", "true", "yes"}
    if not should_call:
        return {
            "status": "deterministic_fallback",
            "provider": "local",
            "reason": "Model generation is disabled. Set generate_with_model=true or PROOFLOOP_GENERATE_WITH_MODEL=1 to call a provider.",
            "assets": _fallback_assets(packet),
        }

    api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return {
            "status": "deterministic_fallback",
            "provider": "local",
            "reason": "OPENAI_API_KEY is not set, so the local fallback generated the learning assets.",
            "assets": _fallback_assets(packet),
        }
    runtime_model = (model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)).strip()
    if not runtime_model:
        return {
            "status": "deterministic_fallback",
            "provider": "local",
            "reason": "A runtime API key was supplied, but no generation model id was selected. Enter a model id or set OPENAI_MODEL.",
            "assets": _fallback_assets(packet),
        }

    try:
        assets, from_cache = _call_openai_compatible(packet, api_key, model=runtime_model)
    except ProviderError as exc:
        return {
            "status": "deterministic_fallback",
            "provider": "local",
            "reason": str(exc),
            "provider_error": {
                "provider": f"openai-compatible:{runtime_model}",
                "status_code": exc.status_code,
                "retry_after": exc.retry_after,
                "message": str(exc),
            },
            "assets": _fallback_assets(packet),
        }

    return {
        "status": "model_generated",
        "provider": f"openai-compatible:{runtime_model}",
        "from_cache": from_cache,
        "reason": (
            "Model-generated learning assets were reused from cache."
            if from_cache
            else "RAG chunks and learner-state summary were sent to the model generation layer."
        ),
        "assets": assets,
    }


def _call_openai_compatible(packet: dict[str, Any], api_key: str, model: str = "") -> tuple[dict[str, Any], bool]:
    model = (model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)).strip()
    if not model:
        raise ProviderError("No OpenAI-compatible model id was selected.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    timeout = float(os.getenv("PROOFMARK_OPENAI_TIMEOUT", os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "120")))
    max_output_tokens = int(os.getenv("PROOFLOOP_GENERATION_MAX_OUTPUT_TOKENS", "5500"))
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "high").strip()
    body = {
        "model": model,
        "instructions": GENERATION_INSTRUCTIONS,
        "input": json.dumps(_compact_generation_packet(packet), separators=(",", ":")),
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "track_b_learning_assets",
                "strict": True,
                "schema": GENERATION_PATCH_SCHEMA,
            }
        },
    }
    def call_provider() -> dict[str, Any]:
        def attempt() -> dict[str, Any]:
            req = urllib.request.Request(
                f"{base_url}/responses",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise provider_error_from_http("Generation provider", exc, detail) from exc
            except TimeoutError as exc:
                raise ProviderError(
                    f"Generation provider timed out after {timeout:.0f}s. "
                    "The selected generation model request was attempted, but the app returned local assets so the demo does not stay stuck.",
                    status_code=504,
                ) from exc
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                status_code = 504 if isinstance(reason, TimeoutError) else None
                timeout_note = (
                    f" after {timeout:.0f}s"
                    if isinstance(reason, TimeoutError)
                    else ""
                )
                raise ProviderError(f"Generation provider network error{timeout_note}: {exc}", status_code=status_code) from exc

            try:
                payload = json.loads(raw)
                return _merge_model_asset_patch(packet, _parse_generation_payload(payload))
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise ProviderError("Generation provider output did not match the expected learning-assets schema.") from exc

        return with_provider_retries("OpenAI-compatible generation", attempt)

    return cached_json("openai-generation", model, body, call_provider)


def _parse_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    direct_json = _extract_response_json(payload)
    if direct_json is not None:
        return direct_json
    content = _extract_response_text(payload)
    if isinstance(content, dict):
        return content
    return _parse_generation_json(content)


def _extract_response_json(payload: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(payload.get("output_parsed"), dict):
        return payload["output_parsed"]
    if isinstance(payload.get("parsed"), dict):
        return payload["parsed"]

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            for key in ("json", "parsed"):
                value = content.get(key)
                if isinstance(value, dict):
                    return value
            for key in ("text", "output_text"):
                value = content.get(key)
                if isinstance(value, dict):
                    return value

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, dict):
                return content
    return None


def _parse_generation_json(content: str) -> dict[str, Any]:
    return parse_provider_json_object(content)


def _compact_generation_packet(packet: dict[str, Any]) -> dict[str, Any]:
    source_summary = packet.get("source_analysis_summary", {})
    study = source_summary.get("student_video_lesson", {}) if isinstance(source_summary, dict) else {}
    return {
        "learning_objective": packet.get("learning_objective", ""),
        "learner_state_summary": packet.get("learner_state_summary", {}),
        "retrieved_source_chunks": [
            {
                "source_title": chunk.get("source_title", ""),
                "location": chunk.get("location", ""),
                "concepts": chunk.get("concepts", []),
                "text": str(chunk.get("text", ""))[:450],
            }
            for chunk in packet.get("retrieved_source_chunks", [])[:5]
            if isinstance(chunk, dict)
        ],
        "student_video_lesson": {
            "summary": study.get("one_minute_summary", ""),
            "key_facts": study.get("key_facts", [])[:5] if isinstance(study.get("key_facts"), list) else [],
            "formula_cards": study.get("formula_cards", [])[:4] if isinstance(study.get("formula_cards"), list) else [],
            "common_mistakes": study.get("common_mistakes", [])[:5] if isinstance(study.get("common_mistakes"), list) else [],
        },
        "video_timeline": source_summary.get("video_timeline", [])[:5] if isinstance(source_summary, dict) else [],
        "visual_learning_cues": source_summary.get("visual_learning_cues", [])[:4] if isinstance(source_summary, dict) else [],
    }


def _merge_model_asset_patch(packet: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    assets = _fallback_assets(packet)
    if not isinstance(patch, dict):
        return assets
    support_text = _supported_generation_text(packet)
    for key, value in patch.items():
        if value not in (None, "", [], {}) and not _contains_unsupported_known_concept(value, support_text):
            assets[key] = value
    return assets


def _supported_generation_text(packet: dict[str, Any]) -> str:
    parts = [
        packet.get("learning_objective", ""),
        packet.get("learner_state_summary", {}),
        packet.get("source_analysis_summary", {}),
    ]
    for chunk in packet.get("retrieved_source_chunks", []) or []:
        if not isinstance(chunk, dict):
            continue
        parts.extend(
            [
                chunk.get("source_title", ""),
                chunk.get("text", ""),
                chunk.get("concepts", []),
            ]
        )
    return " ".join(_strings_from_value(parts)).lower()


def _contains_unsupported_known_concept(value: Any, support_text: str) -> bool:
    generated_text = " ".join(_strings_from_value(value)).lower()
    if not generated_text:
        return False
    return any(concept in generated_text and concept not in support_text for concept in KNOWN_CONCEPTS)


def _strings_from_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_strings_from_value(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_strings_from_value(item))
        return strings
    if value is None:
        return []
    return [str(value)]


def _fallback_assets(packet: dict[str, Any]) -> dict[str, Any]:
    learner = packet.get("learner_state_summary", {})
    chunks = packet.get("retrieved_source_chunks", [])
    objective = packet.get("learning_objective", "the objective")
    dominant = learner.get("dominant_anchor") or "balanced"
    weak = learner.get("weakest_signals") or ["concept_discrimination"]
    concepts = []
    for chunk in chunks:
        for concept in chunk.get("concepts", []):
            if concept not in concepts:
                concepts.append(concept)
    concept = _concept_from_objective(objective, concepts) or (concepts[0] if concepts else objective)
    secondary = concepts[1] if len(concepts) > 1 else "prerequisite"
    chunk_refs = [
        f"{chunk.get('source_title')} {chunk.get('location')}".strip()
        for chunk in chunks[:3]
    ]

    if dominant == "high_support":
        plan = [
            f"Repair prerequisite for {concept} with a visual contrast.",
            "Run one worked mini-example with checkpoints after every step.",
            "Use a short typed explanation and a low-pressure voice rehearsal.",
            "Retest with one repeat and two fresh variants.",
        ]
        hints = ["definition hint", "contrast hint", "step hint", "mini-example hint"]
    elif dominant == "advanced":
        plan = [
            f"Compress source notes for {concept} into boundary conditions and traps.",
            "Skip easy repetition and move into a transfer case.",
            "Use roleplay to challenge the reasoning under ambiguity.",
            "Schedule delayed review unless transfer fails.",
        ]
        hints = ["strategic nudge", "counterexample", "source anchor"]
    else:
        plan = [
            f"Read structured notes for {concept}.",
            "Complete a concept-map edge and one MCQ.",
            "Teach the concept back in writing or voice.",
            "Run a mixed short practice set.",
        ]
        hints = ["strategic hint", "source-anchor hint", "step hint"]

    return {
        "next_learning_plan": plan,
        "personalized_notes": [
            f"Use {concept} as the focus concept.",
            f"Address weak signal: {', '.join(str(item).replace('_', ' ') for item in weak[:3])}.",
            "Ground explanations in retrieved chunks, not unsupported outside facts.",
        ],
        "mind_map_changes": [
            f"Place {concept} at the center of the next map.",
            "Add one prerequisite edge and one common-confusion edge.",
        ],
        "video_or_source_sections": chunk_refs,
        "roleplay_or_voice_task": f"Explain {concept} to a peer, then answer one follow-up that targets the weakest signal.",
        "hint_ladder": hints,
        "micro_assessment": [
            "one recognition check",
            "one typed reasoning check",
            "one fresh transfer variant",
        ],
        "concept_diagrams": [
            {
                "title": f"{concept}: definition to transfer",
                "concept": concept,
                "nodes": ["source definition", secondary, concept, "fresh application", "trap check"],
                "edges": [
                    "source definition -> target concept",
                    "prerequisite -> target concept",
                    "target concept -> fresh application",
                    "target concept -> trap check",
                ],
                "takeaway": f"Keep {concept} connected to source evidence, a prerequisite, and a trap check.",
            }
        ],
        "flowcharts": [
            {
                "title": f"Reteach flow for {concept}",
                "steps": [
                    "read source anchor",
                    "state definition in own words",
                    "contrast against the nearest trap",
                    "solve a changed variant",
                    "rate confidence and schedule review",
                ],
                "misconception_fixed": f"surface recall without transfer for {concept}",
            }
        ],
        "adaptive_quiz_plan": [
            {
                "concept": concept,
                "mix": "40-60% repeat-style variants for missed concepts, remainder fresh equivalents.",
                "question": f"Retry {concept} with a changed representation, then solve a fresh transfer question.",
                "why": "Separates memory of the old answer from concept-level learning.",
            }
        ],
        "reteaching_plan": [
            {
                "concept": concept,
                "mode": "visual_contrast",
                "trigger": "wrong answer, overconfident error, or hint-dependent answer",
                "next_check": "two-sentence explanation plus one fresh variant",
            }
        ],
        "forgetting_curve_notes": [
            "Use earlier review for weak or hint-dependent concepts.",
            "Increase spacing only after fresh-variant retrieval succeeds.",
            "Compare every retest against the immediately previous attempt and the first attempt.",
        ],
        "visual_artifact": _fallback_visual_artifact(concept, secondary),
        "evidence_to_collect_next": [
            "correctness",
            "confidence calibration",
            "hint level reached",
            "time after hint",
            "spoken or typed explanation quality",
            "retention on delayed review",
        ],
        "student_study_pack": {
            "one_minute_summary": f"Focus on {concept}. Learn the meaning first, then the rule, then the common trap.",
            "key_facts": [
                f"{concept} is the main idea to explain and use.",
                f"Connect {concept} to {secondary} before solving.",
                "A correct answer should include meaning, rule, and one checked example.",
            ],
            "formula_cards": _fallback_formula_cards(concept),
            "things_to_remember": [
                "Meaning before formula.",
                "Name every symbol before substituting.",
                "Check the common trap before finalizing.",
            ],
            "tips_and_tricks": [
                "Pause after one idea and recall it without looking.",
                "Make a two-column comparison for similar concepts.",
                "Solve one fresh version after the worked example.",
            ],
            "shortcuts": [
                "Meaning -> formula -> units -> trap check.",
                "If two ideas sound similar, compare them in two columns.",
                "After watching, solve one changed example from memory.",
            ],
            "mind_map_branches": [
                f"{concept} -> meaning",
                f"{concept} -> formula/rule",
                f"{concept} -> trap",
                f"{concept} -> practice question",
            ],
            "diagram_ideas": [
                f"Draw {secondary} -> {concept} -> worked example -> trap check.",
                "Make a formula card with symbol meanings.",
            ],
            "voice_over_script": (
                f"Here is the short version. The idea is {concept}. First say what it means, "
                f"then connect it to {secondary}, then choose the rule. Do not jump straight to memorizing. "
                "After you understand the meaning, check units, signs, and the common trap before solving."
            ),
        },
        "why_this_plan": "Generated from the learner-state packet and retrieved source chunks. This is the local deterministic version of the model-generation step.",
    }


def _fallback_formula_cards(concept: str) -> list[dict[str, str]]:
    if "potential" in concept.lower():
        return [
            {
                "label": "Potential from work",
                "latex": "V = \\frac{W}{q}",
                "meaning": "Potential is work done per unit positive test charge.",
                "when_to_use": "Use when work and charge are given or compared.",
            },
            {
                "label": "Point charge potential",
                "latex": "V = \\frac{kQ}{r}",
                "meaning": "Potential due to a point charge decreases with distance.",
                "when_to_use": "Use for potential at a point due to one point charge.",
            },
        ]
    return [
        {
            "label": "Concept rule",
            "latex": "\\text{meaning} \\rightarrow \\text{rule} \\rightarrow \\text{check}",
            "meaning": "Use the rule only after the concept is clear.",
            "when_to_use": "Use before attempting a transfer question.",
        }
    ]


def _fallback_visual_artifact(concept: str, secondary: str) -> dict[str, Any]:
    concept_label = str(concept or "Target concept")
    secondary_label = str(secondary or "Prerequisite")
    return {
        "kind": "local_source_grounded",
        "title": f"{concept_label}: meaning to transfer",
        "concept": concept_label,
        "learner_goal": f"Use this local diagram to connect {concept_label} to a rule, a trap, and a fresh application.",
        "instructions": [
            "Start at the source meaning.",
            "Move through the rule/formula only after the meaning is clear.",
            "Check the common trap before the practice question.",
        ],
        "draw_question": f"Draw {concept_label} and label the source meaning, rule, trap, and practice step.",
        "expected_features": ["source meaning", "rule or formula", "common trap", "fresh practice"],
        "nodes": [
            {"id": "source", "label": "Source meaning", "x": 90, "y": 180, "role": "source"},
            {"id": "prerequisite", "label": secondary_label, "x": 250, "y": 92, "role": "prerequisite"},
            {"id": "concept", "label": concept_label, "x": 360, "y": 180, "role": "concept"},
            {"id": "rule", "label": "Rule / formula", "x": 525, "y": 92, "role": "rule"},
            {"id": "trap", "label": "Trap check", "x": 525, "y": 268, "role": "trap"},
            {"id": "practice", "label": "Fresh practice", "x": 660, "y": 180, "role": "practice"},
        ],
        "edges": [
            {"from": "source", "to": "concept", "label": "define", "kind": "support"},
            {"from": "prerequisite", "to": "concept", "label": "needs", "kind": "support"},
            {"from": "concept", "to": "rule", "label": "choose", "kind": "main"},
            {"from": "concept", "to": "trap", "label": "compare", "kind": "warning"},
            {"from": "rule", "to": "practice", "label": "apply", "kind": "main"},
            {"from": "trap", "to": "practice", "label": "avoid", "kind": "warning"},
        ],
        "rays": [],
        "annotations": [
            {"x": 72, "y": 320, "text": "Local fallback: source-grounded structure, not model art."},
        ],
    }


def _concept_from_objective(objective: str, concepts: list[str]) -> str:
    objective_lower = str(objective or "").lower()
    for concept in concepts:
        if str(concept).lower() in objective_lower:
            return concept
    return ""
