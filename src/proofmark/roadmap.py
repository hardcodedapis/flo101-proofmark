from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import os
from typing import Any

from .case_builder import build_dynamic_case
from .content_graph import build_content_graph, retrieve_chunks
from .curator import build_curated_bundle
from .evidence_grader import grade_learner_event
from .generation import generate_learning_assets
from .learner_model import compress_for_llm, filter_events_for_graph, infer_learner_profile, sample_evidence_events
from .lesson_graph import build_lesson_graph
from .schema import InputError
from .session_store import dedupe_events, load_session_state, resolve_session_id, save_session_state
from .source_analysis import analyze_sources


AVAILABLE_MODES = [
    "structured_notes",
    "mind_map",
    "video_or_source_sections",
    "visual_cue",
    "hint_ladder",
    "micro_quiz",
    "typed_explanation",
    "voice_demo",
    "roleplay",
    "worked_example",
    "dynamic_case",
    "adaptive_retest",
]


def sample_track_b_payload(include_evidence: bool = True, topic: str = "electric_potential") -> dict[str, Any]:
    if topic == "ray_optics":
        payload = _sample_ray_optics_payload()
    elif topic == "chemistry":
        payload = _sample_chemistry_payload()
    else:
        payload = _sample_electric_potential_payload()
    if include_evidence:
        payload["learner_events"] = sample_evidence_events()
    return payload


def _sample_electric_potential_payload() -> dict[str, Any]:
    return {
        "learning_objective": "Understand electric potential and solve CBSE/JEE-style electrostatics transfer problems.",
        "content_set": [
            {
                "id": "electrostatics-lecture",
                "type": "video_transcript",
                "title": "Electrostatics lecture transcript",
                "segments": [
                    {
                        "start": "03:15",
                        "end": "04:20",
                        "text": "Electric potential is defined as work done per unit positive test charge in bringing it from infinity to a point. Potential is a scalar quantity, while electric field is a vector.",
                    },
                    {
                        "start": "07:05",
                        "end": "09:10",
                        "text": "For a point charge, potential V equals kQ divided by r. Potentials from multiple charges add algebraically, so signs of charges matter.",
                    },
                    {
                        "start": "12:00",
                        "end": "13:40",
                        "text": "A common mistake is to treat electric potential like electric field. Field uses vector addition, but potential uses scalar addition.",
                    },
                ],
            },
            {
                "id": "board-notes",
                "type": "notes",
                "title": "Teacher board notes",
                "text": (
                    "Prerequisites: charge, Coulomb force, work-energy theorem, and electric field. "
                    "Potential difference is the work done per unit charge between two points. "
                    "Equipotential surfaces are surfaces with the same potential, so no work is done moving charge along them. "
                    "Potential energy of a charge q at potential V is qV."
                ),
            },
            {
                "id": "practice-sheet",
                "type": "worksheet",
                "title": "Electrostatics practice sheet",
                "text": (
                    "Worked example: find potential at a point due to +Q and -2Q charges. "
                    "First compute kQ/r for each charge, preserve signs, then add scalar values. "
                    "Challenge: compare potential zero point with electric field zero point and explain why they differ."
                ),
            },
            {
                "id": "electric-potential-video",
                "type": "video",
                "title": "Electrostatic potential video lesson",
                "url": "https://www.youtube.com/watch?v=sGb3VLDvNRU",
                "text": (
                    "Long-form video lesson covering electrostatic potential energy, electrostatic potential, "
                    "relation between electric field and potential, electric dipole, equipotential surface, "
                    "conductor behavior, and revision problems for JEE-style electrostatics."
                ),
            },
            {
                "id": "nptel-electromagnetic-fields",
                "type": "pdf",
                "title": "NPTEL electromagnetic fields syllabus reference",
                "url": "https://archive.nptel.ac.in/content/syllabus_pdf/108106073.pdf",
                "text": (
                    "Public NPTEL reference listing electrostatics topics including Coulomb law, "
                    "electric field, electrostatic potential, Poisson equation, energy in the field, "
                    "capacitance, dielectrics, and boundary conditions."
                ),
            },
        ],
        "constraints": {
            "time_budget_minutes": 28,
            "available_modes": AVAILABLE_MODES,
            "exam_context": "CBSE/JEE",
        },
    }


def _sample_ray_optics_payload() -> dict[str, Any]:
    return {
        "learning_objective": "Understand convex lens image formation with ray diagrams and solve CBSE/JEE lens formula questions.",
        "content_set": [
            {
                "id": "convex-lens-video",
                "type": "video",
                "title": "Convex lens ray diagram video lesson",
                "url": "https://www.youtube.com/watch?v=c6mLLaqLdvg",
                "text": (
                    "YouTube video lesson explaining how to draw convex lens ray diagrams, why parallel rays pass through the focus, "
                    "how to draw two principal rays, and how image position changes as the object moves."
                ),
            },
            {
                "id": "convex-lens-khan-academy",
                "type": "lesson",
                "title": "Khan Academy convex lenses reference",
                "url": "https://www.khanacademy.org/science/physics/geometric-optics/lenses/v/convex-lenses",
                "text": (
                    "Khan Academy reference for convex lenses, converging rays, focal points, and image formation."
                ),
            },
            {
                "id": "ray-optics-ncert-pdf",
                "type": "pdf",
                "title": "NCERT Ray Optics PDF reference",
                "url": "https://www.ncertbooks.net/textbook/pdf/leph201.pdf",
                "text": (
                    "NCERT chapter reference for ray optics and optical instruments, including refraction, lenses, "
                    "ray diagrams, lens formula, magnification, and optical instruments."
                ),
            },
            {
                "id": "ray-optics-transcript",
                "type": "video_transcript",
                "title": "Ray optics transcript excerpts",
                "segments": [
                    {
                        "start": "01:10",
                        "end": "02:20",
                        "text": "A ray parallel to the principal axis passes through the focus after refraction by a convex lens.",
                    },
                    {
                        "start": "04:00",
                        "end": "05:30",
                        "text": "A ray through the optical center goes straight without deviation. The intersection of refracted rays locates the image.",
                    },
                    {
                        "start": "07:15",
                        "end": "08:40",
                        "text": "When the object is beyond 2F, the image forms between F and 2F, is real, inverted, and diminished.",
                    },
                ],
            },
            {
                "id": "ray-diagram-notes",
                "type": "notes",
                "title": "Convex lens board notes",
                "text": (
                    "Core diagram: draw principal axis, convex lens, optical center O, focal points F1 and F2, and 2F points. "
                    "Ray 1: from object top parallel to principal axis, refracts through focus. "
                    "Ray 2: through optical center, continues straight. The crossing point gives image top. "
                    "Lens formula: $\\frac{1}{f}=\\frac{1}{v}-\\frac{1}{u}$. Magnification: $m=\\frac{h_i}{h_o}=\\frac{v}{u}$. "
                    "Sign convention matters: object distance is negative for a real object on the left."
                ),
            },
            {
                "id": "ray-optics-practice",
                "type": "worksheet",
                "title": "Ray optics practice",
                "text": (
                    "Draw image formation for object beyond 2F, at 2F, between F and 2F, at F, and between F and O. "
                    "Then solve a numerical using f = 10 cm and u = -30 cm. "
                    "Challenge: explain why the image becomes virtual and erect when the object is inside focal length."
                ),
            },
        ],
        "constraints": {
            "time_budget_minutes": 30,
            "available_modes": AVAILABLE_MODES,
            "exam_context": "CBSE/JEE",
        },
    }


def _sample_chemistry_payload() -> dict[str, Any]:
    return {
        "learning_objective": "Understand galvanic cells, electrode potential, and the Nernst equation for CBSE/JEE electrochemistry.",
        "content_set": [
            {
                "id": "galvanic-cell-video",
                "type": "video",
                "title": "Khan Academy galvanic cell lesson",
                "url": "https://www.khanacademy.org/science/chemistry/oxidation-reduction/cell-potentials/v/galvanic-cells",
                "text": (
                    "Video lesson covering oxidation at the anode, reduction at the cathode, electron flow through wire, "
                    "ion flow through salt bridge, and how cell potential predicts spontaneity."
                ),
            },
            {
                "id": "electrochemistry-youtube",
                "type": "video",
                "title": "YouTube electrochemistry Nernst equation problems",
                "url": "https://www.youtube.com/watch?v=n4JCEFJKWA0",
                "text": (
                    "YouTube problem lesson on cell potential, equilibrium constant, galvanic cells, and using "
                    "electrochemistry formulas in exam-style calculations."
                ),
            },
            {
                "id": "electrochemistry-ncert-pdf",
                "type": "pdf",
                "title": "NCERT Electrochemistry PDF reference",
                "url": "https://ncert.nic.in/textbook/pdf/lech103.pdf",
                "text": (
                    "NCERT chapter reference for electrochemical cells, electrode potential, galvanic cells, "
                    "Nernst equation, conductance, batteries, fuel cells, and corrosion."
                ),
            },
            {
                "id": "electrochemistry-notes",
                "type": "notes",
                "title": "Electrochemistry board notes",
                "text": (
                    "Galvanic cell converts chemical energy to electrical energy. Oxidation occurs at anode and reduction occurs at cathode. "
                    "Electrons flow from anode to cathode through the external circuit. Salt bridge maintains charge balance. "
                    "Cell potential: $E^\\circ_{cell}=E^\\circ_{cathode}-E^\\circ_{anode}$. "
                    "Nernst equation at 298 K: $E_{cell}=E^\\circ_{cell}-\\frac{0.0591}{n}\\log Q$."
                ),
            },
            {
                "id": "cell-diagram-practice",
                "type": "worksheet",
                "title": "Cell diagram practice",
                "text": (
                    "For Zn/Cu cell, identify anode, cathode, electron direction, ion movement, and salt bridge role. "
                    "Write cell notation: Zn(s)|Zn2+(aq)||Cu2+(aq)|Cu(s). "
                    "Challenge: use concentration change to predict whether Ecell increases or decreases."
                ),
            },
        ],
        "constraints": {
            "time_budget_minutes": 30,
            "available_modes": AVAILABLE_MODES,
            "exam_context": "CBSE/JEE",
        },
    }


def build_track_b_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")

    graph = build_content_graph(payload)
    learner_profile = infer_learner_profile(payload, graph)
    bundle = build_curated_bundle(payload, graph, learner_profile)
    retrieval_config = _retrieval_config(payload)
    source_analysis = analyze_sources(payload, graph, bundle["rag_context"]["selected_chunks"])
    dynamic_case = build_dynamic_case(graph["learning_objective"], graph, bundle, learner_profile)
    roadmap = _build_roadmap(graph, bundle, dynamic_case, learner_profile, payload.get("constraints", {}), retrieval_config)
    llm_packet = compress_for_llm(
        graph["learning_objective"],
        learner_profile,
        bundle["rag_context"]["selected_chunks"],
        {
            "available_modes": (payload.get("constraints", {}) or {}).get("available_modes", AVAILABLE_MODES),
            "time_budget_minutes": (payload.get("constraints", {}) or {}).get("time_budget_minutes", 30),
            "must_return": [
                "next_learning_plan",
                "notes",
                "mind_map",
                "voice_or_roleplay_task",
                "hints",
                "micro_assessment",
                "revision_schedule",
                "concept_diagrams",
                "flowcharts",
                "adaptive_quiz_plan",
                "reteaching_plan",
                "forgetting_curve_notes",
            ],
        },
    )
    llm_packet["source_analysis_summary"] = {
        "provider": source_analysis.get("provider", "local"),
        "status": source_analysis.get("status", "deterministic_fallback"),
        "summary": source_analysis.get("summary", ""),
        "video_timeline": source_analysis.get("video_timeline", [])[:5],
        "video_learning_plan": source_analysis.get("video_learning_plan", {}),
        "student_video_lesson": source_analysis.get("student_video_lesson", {}),
        "page_sequence": source_analysis.get("page_sequence", [])[:6],
        "visual_learning_cues": source_analysis.get("visual_learning_cues", [])[:6],
        "concept_diagrams": source_analysis.get("concept_diagrams", [])[:3],
        "flowcharts": source_analysis.get("flowcharts", [])[:3],
        "adaptive_quiz_blueprint": source_analysis.get("adaptive_quiz_blueprint", [])[:4],
        "reteaching_plan": source_analysis.get("reteaching_plan", [])[:4],
    }
    constraints = payload.get("constraints", {}) if isinstance(payload.get("constraints"), dict) else {}
    generate_with_model = bool(
        payload.get("generate_with_model")
        or constraints.get("generate_with_model")
        or os.getenv("PROOFLOOP_GENERATE_WITH_MODEL", "").lower() in {"1", "true", "yes"}
    )
    runtime_api_key = str(
        payload.get("api_key")
        or payload.get("openai_api_key")
        or constraints.get("api_key")
        or constraints.get("openai_api_key")
        or ""
    ).strip()
    runtime_model = str(payload.get("model") or constraints.get("model") or "").strip()
    model_generation = generate_learning_assets(
        llm_packet,
        enabled=generate_with_model,
        api_key=runtime_api_key,
        model=runtime_model,
    )
    lesson_graph = build_lesson_graph(
        graph,
        bundle,
        dynamic_case,
        learner_profile,
        source_analysis,
        roadmap,
        model_generation,
        constraints,
    )
    provider_notices = _provider_notices(source_analysis, model_generation)
    return {
        "product": "track_b_content_curator_dynamic_case_builder",
        "contract": {
            "required_input": ["learning_objective", "content_set"],
            "optional_input": ["learner_profile", "learner_events", "performance_history", "available_modes"],
            "core_output": ["curated_learning_bundle", "dynamic_case", "source_rationale", "required_learner_output"],
            "advanced_output": [
                "ai_source_analysis",
                "adaptive_lesson_graph",
                "personalized_variants",
                "learner_model",
                "adaptive_roadmap",
                "rag_grounded_llm_packet",
            ],
        },
        "mode": "personalized_after_evidence" if learner_profile["profile_available"] else "cold_start",
        "content_graph": graph,
        "curated_learning_bundle": bundle,
        "dynamic_case": dynamic_case,
        "learner_model": learner_profile,
        "adaptive_roadmap": roadmap,
        "rag_pipeline": {
            "type": bundle["rag_context"].get("strategy", "local_lexical_tfidf"),
            "retrieval_role": "Ground notes, mind maps, video/source sections, cases, hints, and tests in the supplied content set.",
            "not_used_for": "Learner mastery, confidence calibration, hint dependence, and forgetting curves are engine analytics, not retrieval results.",
            "retrieved_chunks": bundle["rag_context"]["selected_chunks"],
            "trace": bundle["rag_context"]["trace"],
            "embedding_model": bundle["rag_context"].get("embedding_model", ""),
            "pinecone_namespace": bundle["rag_context"].get("pinecone_namespace", ""),
            "fallback_used": bundle["rag_context"].get("fallback_used", False),
            "fallback_reason": bundle["rag_context"].get("fallback_reason", ""),
            "pinecone_enabled": bool(retrieval_config.get("pinecone_api_key") and retrieval_config.get("pinecone_index_host")),
            "vector_rag_requested": bool(retrieval_config.get("use_vector_rag")),
        },
        "llm_generation_packet": llm_packet,
        "model_generation": model_generation,
        "ai_source_analysis": source_analysis,
        "provider_notices": provider_notices,
        "lesson_graph": lesson_graph,
        "research_backed_design": [
            "Cold start still makes a first source-analysis call when Gemini is configured; without that key, a local planner returns the same structure.",
            "Cold start uses instructional design defaults instead of fake personalization.",
            "Embedded checks collect visual, text, quiz, typing, voice, hint, timing, confidence, and memory signals while learning happens.",
            "After first-pass evidence, the engine feeds compressed learner analytics plus retrieved content chunks to the LLM.",
            "The LLM generates the next learning methods, while the engine constrains target concept, difficulty, schedule, and evidence to collect.",
        ],
    }


def adapt_track_b_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")
    base_payload = payload.get("base_payload")
    if not isinstance(base_payload, dict):
        raise InputError("missing_base_payload", "Adaptive regeneration requires the original Track B payload.")

    adapted = deepcopy(base_payload)
    base_graph = build_content_graph(adapted)
    prior_events = adapted.get("learner_events") or adapted.get("evidence_events") or []
    if not isinstance(prior_events, list):
        prior_events = []

    new_event = payload.get("learner_event")
    extra_events = payload.get("learner_events") if isinstance(payload.get("learner_events"), list) else []
    graded_new_event: dict[str, Any] | None = None
    session_id = resolve_session_id(payload, base_payload, new_event if isinstance(new_event, dict) else None)
    stored_state = load_session_state(session_id)
    stored_events = stored_state.get("events") if isinstance(stored_state.get("events"), list) else []
    events = [
        grade_learner_event(event, base_graph) if _needs_server_score(event) else event
        for event in [*stored_events, *prior_events]
        if isinstance(event, dict)
    ]
    if isinstance(new_event, dict):
        graded_new_event = grade_learner_event(new_event, base_graph)
        events.append(graded_new_event)
    events.extend(
        grade_learner_event(event, base_graph) if _needs_server_score(event) else event
        for event in extra_events
        if isinstance(event, dict)
    )
    events, duplicate_event_ids = dedupe_events(events)
    events, ignored_stale_event_count = filter_events_for_graph(events, base_graph)
    adapted["learner_events"] = events

    result = build_track_b_plan(adapted)
    roadmap = result.get("adaptive_roadmap", {})
    profile = result.get("learner_model", {})
    schedule = roadmap.get("review_schedule", [])
    stored_update = save_session_state(
        session_id=session_id,
        base_payload=base_payload,
        events=events,
        latest_event=graded_new_event,
        roadmap=roadmap,
        learner_profile=profile,
        duplicate_event_ids=duplicate_event_ids,
    )
    result["adaptive_update"] = {
        "session_id": session_id,
        "accepted_event_count": len(events),
        "latest_event_id": _nested_event_value(new_event, "identity", "event_id") if isinstance(new_event, dict) else "",
        "latest_server_score": _nested_event_value(graded_new_event, "response_quality", "score") if graded_new_event else "",
        "latest_scoring_basis": _nested_event_value(graded_new_event, "response_quality", "server_scoring_basis")
        if graded_new_event
        else "",
        "latest_scoring_rubric": _nested_event_value(graded_new_event, "response_quality", "server_rubric_version")
        if graded_new_event
        else "",
        "state": roadmap.get("state", result.get("mode", "")),
        "dominant_anchor": profile.get("dominant_anchor", "balanced"),
        "next_mode": roadmap.get("next_mode", "collect_more_evidence"),
        "target_concepts": roadmap.get("target_concepts", []),
        "next_review": schedule[0] if schedule else {},
        "event_store": {
            "persisted": stored_update["persisted"],
            "version": stored_update["version"],
            "event_count": stored_update["event_count"],
            "duplicate_event_ids": duplicate_event_ids,
            "ignored_stale_event_count": ignored_stale_event_count,
            "audit_record": stored_update["audit_record"],
        },
    }
    return result


def _needs_server_score(event: dict[str, Any]) -> bool:
    if event.get("server_scored"):
        return False
    response_quality = event.get("response_quality") if isinstance(event.get("response_quality"), dict) else {}
    if response_quality.get("client_observation"):
        return True
    identity = event.get("identity") if isinstance(event.get("identity"), dict) else {}
    return str(identity.get("event_id", "")).startswith("live-")


def _nested_event_value(event: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = event or {}
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value if value is not None else ""


def _provider_notices(source_analysis: dict[str, Any], model_generation: dict[str, Any]) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = []
    if source_analysis.get("provider_error"):
        error = source_analysis.get("provider_error", {})
        status_code = error.get("status_code")
        notices.append(
            {
                "provider": error.get("provider") or source_analysis.get("provider") or "gemini",
                "stage": "source/video analysis",
                "kind": "rate_limit" if status_code == 429 else "provider_fallback",
                "status_code": status_code,
                "retry_after": error.get("retry_after"),
                "message": error.get("message") or source_analysis.get("reason", ""),
                "fallback": "Local planner produced the same product shape from parsed sources and RAG chunks.",
            }
        )
    if model_generation.get("provider_error"):
        error = model_generation.get("provider_error", {})
        status_code = error.get("status_code")
        notices.append(
            {
                "provider": error.get("provider") or model_generation.get("provider") or "openai-compatible",
                "stage": "learning asset generation",
                "kind": "rate_limit" if status_code == 429 else "provider_fallback",
                "status_code": status_code,
                "retry_after": error.get("retry_after"),
                "message": error.get("message") or model_generation.get("reason", ""),
                "fallback": "Local assets filled the same lesson fields so the demo can continue.",
            }
        )
    return notices


def _build_roadmap(
    graph: dict[str, Any],
    bundle: dict[str, Any],
    dynamic_case: dict[str, Any],
    learner_profile: dict[str, Any],
    constraints: dict[str, Any] | None = None,
    retrieval_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = constraints if isinstance(constraints, dict) else {}
    concepts = graph.get("concepts", [])[:5]
    dominant = learner_profile.get("dominant_anchor", "balanced")
    profile_available = learner_profile.get("profile_available", False)
    review_schedule = _review_schedule(concepts, learner_profile)
    first_sequence = bundle.get("embedded_evidence_sequence", [])

    if not profile_available:
        return {
            "state": "cold_start_first_pass",
            "summary": "Use the general bundle to teach and collect evidence side by side. Personalization starts after embedded checks and the final dynamic case.",
            "first_pass_sequence": first_sequence,
            "after_first_pass": [
                "Score final case with rubric.",
                "Compress telemetry into learner-state summary.",
                "Retrieve source chunks for the weakest concept.",
                "Ask the LLM to generate the next personalized notes, mind map, hints, roleplay, quiz, and review plan.",
            ],
            "review_schedule": review_schedule,
            "next_generation_rule": "No profile yet: show all three profile variants as previews, then select after first-pass evidence.",
        }

    target_concepts = _target_concepts(concepts, learner_profile)
    next_mode = _next_mode(learner_profile)
    retrieval = retrieve_chunks(
        graph,
        " ".join(target_concepts),
        limit=4,
        focus_terms=target_concepts,
        retrieval_config=retrieval_config,
    )

    return {
        "state": "personalized_after_evidence",
        "summary": f"Dominant anchor is {dominant}; generate the next bundle around {', '.join(target_concepts[:3])}.",
        "target_concepts": target_concepts,
        "next_mode": next_mode,
        "next_learning_methods": _methods_for_anchor(dominant, target_concepts),
        "source_sections_for_next_plan": retrieval["selected_chunks"],
        "review_schedule": review_schedule,
        "dynamic_case_adjustment": dynamic_case["personalized_variants"]["variants"][dominant]["case_adjustment"],
        "evidence_to_collect_next": _evidence_to_collect(dominant),
        "llm_role": "Generate the concrete content assets for the chosen method using the engine state and retrieved source chunks.",
    }


def _target_concepts(concepts: list[dict[str, Any]], learner_profile: dict[str, Any]) -> list[str]:
    mastery = learner_profile.get("concept_mastery", {})
    if mastery:
        weak = [concept for concept, _score in sorted(mastery.items(), key=lambda item: item[1])]
        return weak[:4]
    return [concept["name"] for concept in concepts[:4]]


def _next_mode(learner_profile: dict[str, Any]) -> str:
    weak = set(learner_profile.get("weakest_signals", []))
    if "concept_discrimination" in weak or learner_profile.get("current_misconceptions"):
        return "visual_contrast_plus_hint_ladder"
    if "typed_explanation" in weak:
        return "teach_back_then_typed_rewrite"
    if "spoken_explanation" in weak:
        return "low_pressure_voice_demo"
    if "transfer" in weak:
        return "scenario_roleplay"
    if learner_profile.get("dominant_anchor") == "advanced":
        return "transfer_challenge"
    return "mixed_practice"


def _methods_for_anchor(anchor: str, target_concepts: list[str]) -> list[dict[str, Any]]:
    concept = target_concepts[0] if target_concepts else "target concept"
    if anchor == "high_support":
        return [
            {"mode": "visual_cue", "task": f"Contrast {concept} against the misconception with a two-column diagram."},
            {"mode": "worked_example", "task": "Show one solved example with a checkpoint after each step."},
            {"mode": "hint_ladder", "task": "Offer definition, contrast, step, and mini-example hints."},
            {"mode": "micro_quiz", "task": "Use easy variants first, then one fresh same-concept question."},
        ]
    if anchor == "advanced":
        return [
            {"mode": "compressed_notes", "task": f"Summarize {concept} with boundary conditions and exceptions."},
            {"mode": "roleplay", "task": "Defend a decision while the system challenges weak reasoning."},
            {"mode": "transfer_challenge", "task": "Solve a harder variant with a distractor constraint."},
            {"mode": "adaptive_retest", "task": "Use mostly fresh variants and only repeat failed traps."},
        ]
    return [
        {"mode": "structured_notes", "task": f"Read concise notes for {concept} with one source anchor."},
        {"mode": "mind_map", "task": "Complete two missing concept edges."},
        {"mode": "teach_back", "task": "Explain the idea in writing or voice, then answer one follow-up."},
        {"mode": "mixed_practice", "task": "Run MCQ, typed explanation, and one short scenario."},
    ]


def _evidence_to_collect(anchor: str) -> list[str]:
    common = [
        "concept-level correctness",
        "confidence vs correctness",
        "hint level needed",
        "time to first action",
        "retention after delay",
    ]
    if anchor == "high_support":
        return common + ["improvement after visual cue", "prerequisite repair success", "dropoff risk"]
    if anchor == "advanced":
        return common + ["transfer quality", "counterexample handling", "ambiguity tolerance"]
    return common + ["teach-back quality", "mixed-mode performance", "source grounding"]


def _review_schedule(concepts: list[dict[str, Any]], learner_profile: dict[str, Any]) -> list[dict[str, Any]]:
    today = date.today()
    mastery = learner_profile.get("concept_mastery", {})
    anchor = learner_profile.get("dominant_anchor", "balanced")
    rows = []
    for index, concept in enumerate(concepts[:5], start=1):
        score = float(mastery.get(concept["name"], 0.5 if learner_profile.get("profile_available") else 0.42))
        base_days = 1 if score < 0.45 else 2 if score < 0.68 else 5
        if anchor == "advanced" and score >= 0.68:
            base_days += 2
        if anchor == "high_support":
            base_days = max(1, base_days - 1)
        rows.append(
            {
                "concept": concept["name"],
                "mastery_estimate": round(score, 2),
                "review_in_days": base_days,
                "review_date": (today + timedelta(days=base_days)).isoformat(),
                "review_type": "fresh_variant" if score >= 0.68 else "repair_plus_repeat",
                "reason": _review_reason(score, anchor),
            }
        )
    return rows


def _review_reason(score: float, anchor: str) -> str:
    if score < 0.45:
        return "Low first-pass mastery or unknown stability; schedule early repair before decay."
    if score < 0.68:
        return "Partial mastery; use a mixed repeat/fresh check after short spacing."
    if anchor == "advanced":
        return "Strong enough for delayed transfer check instead of immediate repetition."
    return "Currently stable; verify with a fresh application after spacing."


def _retrieval_config(payload: dict[str, Any]) -> dict[str, Any]:
    constraints = payload.get("constraints", {}) if isinstance(payload.get("constraints"), dict) else {}
    return {
        "use_vector_rag": bool(
            payload.get("use_vector_rag")
            or constraints.get("use_vector_rag")
            or os.getenv("PROOFLOOP_USE_VECTOR_RAG", "").lower() in {"1", "true", "yes"}
        ),
        "openai_api_key": str(
            payload.get("api_key")
            or payload.get("openai_api_key")
            or constraints.get("api_key")
            or constraints.get("openai_api_key")
            or ""
        ).strip(),
        "embedding_model": str(
            payload.get("embedding_model")
            or constraints.get("embedding_model")
            or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        ).strip(),
        "pinecone_api_key": str(
            payload.get("pinecone_api_key")
            or constraints.get("pinecone_api_key")
            or os.getenv("PINECONE_API_KEY", "")
            or ""
        ).strip(),
        "pinecone_index_host": str(
            payload.get("pinecone_index_host")
            or constraints.get("pinecone_index_host")
            or os.getenv("PINECONE_INDEX_HOST", "")
            or ""
        ).strip(),
        "pinecone_namespace": str(
            payload.get("pinecone_namespace")
            or constraints.get("pinecone_namespace")
            or os.getenv("PINECONE_NAMESPACE", "proofloop-demo")
        ).strip(),
    }
