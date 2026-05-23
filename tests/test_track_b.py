from __future__ import annotations

import base64
from collections import deque
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from proofmark.app import DEFAULT_MAX_POST_BODY_BYTES, _client_authorized, _max_post_body_bytes, _rate_limit_decision, internal_error_payload
from proofmark.content_graph import build_content_graph, retrieve_chunks
from proofmark.evidence_grader import grade_learner_event
from proofmark.generation import _merge_model_asset_patch, _parse_generation_json, _parse_generation_payload
from proofmark.learner_model import infer_learner_profile, sample_evidence_events
from proofmark.provider_runtime import cached_json, parse_provider_json_object, with_provider_retries
from proofmark.providers import ProviderError
from proofmark.rag import RagError, _validated_redirect_url, extract_url_text, pinecone_upsert_and_query
from proofmark.roadmap import adapt_track_b_plan, build_track_b_plan, sample_track_b_payload
from proofmark.runtime_config import load_runtime_env
from proofmark.schema import InputError
from proofmark.source_analysis import _call_gemini_source_analysis
from proofmark.voice import generate_voice_summary, list_elevenlabs_models, list_elevenlabs_voices


def _data_url(mime_type: str, raw: bytes) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"


class _FakeHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class TrackBEngineTest(unittest.TestCase):
    def test_content_graph_builds_rag_chunks_from_required_inputs(self) -> None:
        graph = build_content_graph(sample_track_b_payload(include_evidence=False))

        self.assertGreaterEqual(graph["source_count"], 3)
        self.assertGreaterEqual(graph["chunk_count"], 3)
        self.assertTrue(graph["concepts"])
        retrieval = retrieve_chunks(graph, "electric potential scalar field", limit=3)
        self.assertEqual(len(retrieval["selected_chunks"]), 3)
        self.assertGreaterEqual(retrieval["selected_chunks"][0]["score"], retrieval["selected_chunks"][-1]["score"])

    def test_url_only_input_is_metadata_not_grounded_content(self) -> None:
        payload = {
            "learning_objective": "Understand Bayes theorem for medical testing.",
            "content_set": [
                {
                    "type": "url",
                    "title": "Bayes article",
                    "url": "https://example.com/bayes",
                }
            ],
        }

        graph = build_content_graph(payload)
        retrieval = retrieve_chunks(graph, "Bayes theorem medical testing", limit=1)

        self.assertEqual(graph["sources"][0]["source_state"], "metadata_only")
        self.assertFalse(graph["sources"][0]["content_is_grounded"])
        self.assertEqual(graph["warnings"][0]["code"], "url_metadata_only")
        self.assertFalse(retrieval["selected_chunks"][0]["content_is_grounded"])
        self.assertIn("Metadata-only", retrieval["selected_chunks"][0]["selected_because"])

    def test_bayes_concepts_are_clean_and_dynamic_case_is_concrete(self) -> None:
        payload = {
            "learning_objective": "Teach Bayes theorem for medical test interpretation.",
            "content_set": [
                {
                    "type": "notes",
                    "title": "Bayes medical test notes",
                    "text": (
                        "Bayes theorem connects base rate, sensitivity, specificity, and posterior probability. "
                        "In a medical test, sensitivity is the true positive rate and specificity is the true negative rate. "
                        "A positive result can still have low posterior probability when the base rate is low because false positives dominate."
                    ),
                }
            ],
        }

        result = build_track_b_plan(payload)
        concepts = [concept["name"].lower() for concept in result["content_graph"]["concepts"]]
        case_text = str(result["dynamic_case"]).lower()

        self.assertIn("bayes theorem", concepts)
        self.assertIn("base rate", concepts)
        self.assertIn("sensitivity", concepts)
        self.assertIn("specificity", concepts)
        self.assertNotIn("theorem medical", concepts)
        self.assertNotIn("sensitivity true", concepts)
        self.assertIn("medical-test bayes trap", result["dynamic_case"]["title"].lower())
        self.assertIn("calculate p(disease | positive)", case_text)
        self.assertIn("base-rate trap", case_text)

    def test_physics_sensitivity_word_does_not_trigger_bayes_domain(self) -> None:
        payload = {
            "learning_objective": "Understand convex lens image formation with ray diagrams.",
            "content_set": [
                {
                    "id": "ray-optics-pdf-text",
                    "type": "notes",
                    "title": "Ray optics PDF text",
                    "text": (
                        "Nature has endowed the human eye with the sensitivity to detect electromagnetic waves. "
                        "A convex lens uses a principal axis, focal point, optical center, and lens formula "
                        "to locate image formation with ray diagrams."
                    ),
                }
            ],
        }

        graph = build_content_graph(payload)
        concepts = [concept["name"] for concept in graph["concepts"]]

        self.assertIn("Convex lens", concepts)
        self.assertIn("Principal axis", concepts)
        self.assertNotIn("Bayes theorem", concepts)
        self.assertNotIn("Base rate", concepts)
        self.assertNotIn("Sensitivity", concepts)
        result = build_track_b_plan(payload)
        self.assertIn("convex-lens", result["dynamic_case"]["title"])
        self.assertNotIn("Bayes", json.dumps(result["dynamic_case"]))

    def test_markdown_document_upload_preserves_math(self) -> None:
        markdown = "# Electrostatics\n\nPotential is $V = kQ/r$ and field is $E = F/q$."
        payload = {
            "learning_objective": "Understand electric potential formulas.",
            "content_set": [
                {
                    "type": "document",
                    "filename": "electrostatics.md",
                    "mime_type": "text/markdown",
                    "data_url": _data_url("text/markdown", markdown.encode("utf-8")),
                }
            ],
        }
        graph = build_content_graph(payload)

        self.assertEqual(graph["source_count"], 1)
        self.assertTrue(graph["sources"][0]["math_detected"])
        self.assertIn("$V = kQ/r$", graph["chunks"][0]["text"])

    def test_latex_document_upload_normalizes_text_and_preserves_math(self) -> None:
        latex = "\\section{Potential} Electric potential is \\(V = kQ/r\\). % teacher note"
        payload = {
            "learning_objective": "Understand electric potential formulas.",
            "content_set": [
                {
                    "type": "document",
                    "filename": "potential.tex",
                    "mime_type": "text/x-tex",
                    "data_url": _data_url("text/x-tex", latex.encode("utf-8")),
                }
            ],
        }
        graph = build_content_graph(payload)

        self.assertIn("Potential", graph["chunks"][0]["text"])
        self.assertIn("\\(V = kQ/r\\)", graph["chunks"][0]["text"])
        self.assertNotIn("teacher note", graph["chunks"][0]["text"])

    def test_pdf_document_upload_extracts_text_stream(self) -> None:
        pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 72 >> stream\n"
            b"BT\n/F1 12 Tf\n72 720 Td\n(Electric potential V = kQ/r) Tj\nET\n"
            b"endstream\nendobj\n%%EOF\n"
        )
        payload = {
            "learning_objective": "Understand electric potential formulas.",
            "content_set": [
                {
                    "type": "document",
                    "filename": "notes.pdf",
                    "mime_type": "application/pdf",
                    "data_url": _data_url("application/pdf", pdf),
                }
            ],
        }
        graph = build_content_graph(payload)

        self.assertEqual(graph["sources"][0]["document_parser"], "pdf_text_stream_best_effort")
        self.assertIn("Electric potential", graph["chunks"][0]["text"])

    def test_track_b_cold_start_does_not_require_learner_profile(self) -> None:
        result = build_track_b_plan(sample_track_b_payload(include_evidence=False))

        self.assertEqual(result["mode"], "cold_start")
        self.assertEqual(result["contract"]["required_input"], ["learning_objective", "content_set"])
        self.assertIn("curated_learning_bundle", result)
        self.assertIn("dynamic_case", result)
        self.assertFalse(result["learner_model"]["profile_available"])
        self.assertEqual(result["adaptive_roadmap"]["state"], "cold_start_first_pass")
        self.assertTrue(result["curated_learning_bundle"]["embedded_evidence_sequence"])
        self.assertEqual(result["model_generation"]["status"], "deterministic_fallback")
        self.assertEqual(result["ai_source_analysis"]["status"], "deterministic_fallback")
        self.assertTrue(result["lesson_graph"]["pages"])
        self.assertIn("source_media_lesson", result["lesson_graph"]["page_order"])
        media_page = next(page for page in result["lesson_graph"]["pages"] if page["type"] == "media_lesson")
        visual_page = next(page for page in result["lesson_graph"]["pages"] if page["type"] == "visual_repair")
        practice_page = next(page for page in result["lesson_graph"]["pages"] if page["type"] == "practice")
        revision_page = next(page for page in result["lesson_graph"]["pages"] if page["type"] == "revision")
        self.assertTrue(media_page["video_learning_plan"]["pre_watch"])
        self.assertTrue(media_page["video_learning_plan"]["segments"])
        self.assertTrue(media_page["video_learning_plan"]["after_watch"])
        self.assertTrue(media_page["student_video_lesson"]["one_minute_summary"])
        self.assertTrue(media_page["student_video_lesson"]["key_facts"])
        self.assertTrue(media_page["student_video_lesson"]["formula_cards"])
        self.assertTrue(media_page["student_video_lesson"]["audio_overview_script"])
        self.assertTrue(media_page["student_video_lesson"]["timestamp_guide"])
        self.assertTrue(visual_page["concept_diagrams"])
        self.assertTrue(visual_page["flowcharts"])
        self.assertTrue(practice_page["retest_quiz_plan"])
        self.assertTrue(practice_page["adaptive_quiz_blueprint"])
        self.assertTrue(revision_page["forgetting_curve"])
        self.assertTrue(revision_page["reteaching_plan"])
        self.assertTrue(revision_page["next_retake"])

    def test_sample_payloads_include_diagram_friendly_physics_and_chemistry_seeds(self) -> None:
        physics = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        chemistry = sample_track_b_payload(include_evidence=False, topic="chemistry")
        physics_urls = " ".join(item.get("url", "") for item in physics["content_set"])
        chemistry_urls = " ".join(item.get("url", "") for item in chemistry["content_set"])

        self.assertIn("convex lens", physics["learning_objective"].lower())
        self.assertIn("ray", " ".join(item.get("text", "") for item in physics["content_set"]).lower())
        self.assertIn("youtube.com/watch", physics_urls)
        self.assertIn("khanacademy.org", physics_urls)
        self.assertIn("leph201.pdf", physics_urls)
        self.assertIn("galvanic", chemistry["learning_objective"].lower())
        self.assertIn("nernst", " ".join(item.get("text", "") for item in chemistry["content_set"]).lower())
        self.assertIn("khanacademy.org", chemistry_urls)
        self.assertIn("youtube.com/watch", chemistry_urls)
        self.assertIn("lech103.pdf", chemistry_urls)

    def test_seed_dynamic_cases_are_domain_specific(self) -> None:
        physics = build_track_b_plan(sample_track_b_payload(include_evidence=False, topic="ray_optics"))
        chemistry = build_track_b_plan(sample_track_b_payload(include_evidence=False, topic="chemistry"))

        self.assertIn("convex-lens", physics["dynamic_case"]["title"].lower())
        self.assertIn("ray diagram", str(physics["dynamic_case"]).lower())
        self.assertIn("lens formula", str(physics["dynamic_case"]).lower())
        self.assertIn("zn-cu galvanic cell", chemistry["dynamic_case"]["title"].lower())
        self.assertIn("anode", str(chemistry["dynamic_case"]).lower())
        self.assertIn("nernst", str(chemistry["dynamic_case"]).lower())

    def test_track_b_rejects_known_domain_objective_source_mismatch(self) -> None:
        payload = {
            "learning_objective": sample_track_b_payload(include_evidence=False, topic="ray_optics")["learning_objective"],
            "content_set": [
                {
                    "type": "notes",
                    "title": "Bayes note",
                    "text": (
                        "Bayes theorem connects base rate, sensitivity, specificity, false positive, "
                        "posterior probability, and conditional probability in medical testing."
                    ),
                }
            ],
        }

        with self.assertRaises(InputError) as exc:
            build_track_b_plan(payload)

        self.assertEqual(exc.exception.code, "objective_source_mismatch")

    def test_stale_cross_topic_evidence_does_not_personalize_new_sample(self) -> None:
        payload = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        payload["learner_events"] = sample_evidence_events()

        result = build_track_b_plan(payload)

        self.assertEqual(result["mode"], "cold_start")
        self.assertFalse(result["learner_model"]["profile_available"])
        self.assertGreater(result["learner_model"]["ignored_event_count"], 0)
        self.assertNotIn("electric potential", str(result["learner_model"]["concept_mastery"]).lower())

    def test_explicit_stale_event_concept_is_ignored_even_when_objective_matches(self) -> None:
        payload = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        payload["learner_events"] = [
            {
                "identity": {"event_id": "stale-bayes-001", "session_id": "unit-stale-session"},
                "learning_context": {
                    "objective": payload["learning_objective"],
                    "concepts": ["Base rate"],
                    "topic": "Practice",
                },
                "activity": {
                    "stage": "practice",
                    "mode": "typed",
                    "activity_type": "adaptive_retest",
                    "prompt_variant": "Solve a new Base rate question that tests the same idea.",
                },
                "response_quality": {
                    "score": 0.9,
                    "correctness": "correct",
                    "raw_response": "A convex lens answer was typed into a stale Base rate retest card.",
                },
            }
        ]

        result = build_track_b_plan(payload)

        self.assertEqual(result["mode"], "cold_start")
        self.assertFalse(result["learner_model"]["profile_available"])
        self.assertEqual(result["learner_model"]["ignored_event_count"], 1)
        self.assertNotIn("base rate", str(result["learner_model"]["concept_mastery"]).lower())
        revision_page = next(page for page in result["lesson_graph"]["pages"] if page["type"] == "revision")
        self.assertEqual(revision_page["next_retake"]["concept"], "Convex lens")

    def test_track_b_uses_optional_evidence_for_personalization(self) -> None:
        result = build_track_b_plan(sample_track_b_payload(include_evidence=True))

        self.assertEqual(result["mode"], "personalized_after_evidence")
        self.assertTrue(result["learner_model"]["profile_available"])
        self.assertIn(result["learner_model"]["dominant_anchor"], {"high_support", "balanced", "advanced"})
        self.assertIn("next_learning_methods", result["adaptive_roadmap"])
        self.assertTrue(result["llm_generation_packet"]["retrieved_source_chunks"])
        self.assertTrue(result["llm_generation_packet"]["source_analysis_summary"]["student_video_lesson"])
        self.assertTrue(result["model_generation"]["assets"]["next_learning_plan"])
        self.assertTrue(result["model_generation"]["assets"]["student_study_pack"]["key_facts"])
        self.assertTrue(result["model_generation"]["assets"]["student_study_pack"]["formula_cards"])
        self.assertTrue(result["model_generation"]["assets"]["student_study_pack"]["voice_over_script"])
        self.assertIn("visual_artifact", result["model_generation"]["assets"])
        self.assertTrue(result["model_generation"]["assets"]["visual_artifact"]["nodes"])
        self.assertNotEqual(result["model_generation"]["assets"]["visual_artifact"]["kind"], "ai_unavailable")

    def test_generation_json_parser_accepts_wrapped_json(self) -> None:
        parsed = _parse_generation_json('Here is the JSON:\\n```json\\n{"next_learning_plan":["read"]}\\n```')

        self.assertEqual(parsed["next_learning_plan"], ["read"])

    def test_generation_json_parser_repairs_common_model_wrappers(self) -> None:
        parsed = _parse_generation_json(
            'Here is the JSON:\\n```json\\n{"next_learning_plan":["read",],}\\n```\\nDone.'
        )

        self.assertEqual(parsed["next_learning_plan"], ["read"])

    def test_provider_json_parser_accepts_single_object_array(self) -> None:
        parsed = parse_provider_json_object('[{"summary":"compact"}]')

        self.assertEqual(parsed["summary"], "compact")

    def test_gemini_source_analysis_parser_accepts_fenced_json(self) -> None:
        graph = build_content_graph(sample_track_b_payload(include_evidence=False))
        gemini_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "```json\n"
                                    '{"summary":"Compact source summary.","key_concepts":[{"name":"Electric potential",}],'
                                    '"key_facts":[],"formulas":[],"timestamp_guide":[],"common_mistakes":[],"source_notes":[]}'
                                    "\n```"
                                )
                            }
                        ]
                    }
                }
            ]
        }
        raw = json.dumps(gemini_payload).encode("utf-8")

        with patch.dict(os.environ, {"PROOFMARK_DISABLE_PROVIDER_CACHE": "1"}):
            with patch("proofmark.source_analysis.urllib.request.urlopen", return_value=_FakeHttpResponse(raw)):
                result, from_cache = _call_gemini_source_analysis(
                    graph,
                    [],
                    api_key="AIza-test-secret",
                    model="unit-gemini-model",
                )

        self.assertFalse(from_cache)
        self.assertEqual(result["summary"], "Compact source summary.")
        self.assertEqual(result["key_concepts"][0]["name"], "Electric potential")

    def test_adaptive_endpoint_regenerates_from_live_learner_event(self) -> None:
        base = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        event = {
            "identity": {"event_id": "live-test-001", "session_id": "unit-adapt-session"},
            "learning_context": {
                "objective": base["learning_objective"],
                "concepts": ["convex lens", "ray diagram"],
            },
            "activity": {"stage": "visual_check", "mode": "visual", "activity_type": "draw_question"},
            "response_quality": {"score": 0.18, "correctness": "incorrect", "raw_response": "I drew only the formula."},
            "reasoning_signals": {
                "error_type": "concept_substitution",
                "misconception": "uses formula without ray diagram",
                "step_order_quality": 0.2,
                "causal_link_quality": 0.18,
                "transfer_quality": 0.12,
            },
            "metacognition": {"self_reported_confidence": 0.75},
            "modality_signals": {"visual_interpretation": 0.16, "typed_explanation": 0.28},
            "intervention_trace": {"selected_next_mode": "visual_contrast", "did_improve_after_hint": False},
            "memory_state": {"encoding_strength": 0.2, "retrieval_success": False},
        }

        with tempfile.TemporaryDirectory() as state_dir:
            with patch.dict(os.environ, {"PROOFMARK_STATE_DIR": state_dir}):
                result = adapt_track_b_plan({"base_payload": base, "learner_event": event})

        self.assertEqual(result["mode"], "personalized_after_evidence")
        self.assertEqual(result["adaptive_update"]["latest_event_id"], "live-test-001")
        self.assertGreaterEqual(result["adaptive_update"]["accepted_event_count"], 1)
        self.assertTrue(result["adaptive_update"]["next_review"])
        self.assertEqual(result["adaptive_update"]["session_id"], "unit-adapt-session")
        self.assertTrue(result["adaptive_update"]["event_store"]["persisted"])
        self.assertEqual(result["adaptive_update"]["latest_scoring_rubric"], "track-b-evidence-rubric-v1")

    def test_adaptive_session_persists_and_deduplicates_events(self) -> None:
        base = sample_track_b_payload(include_evidence=False, topic="ray_optics")

        def event(event_id: str, answer: str) -> dict[str, object]:
            return {
                "identity": {"event_id": event_id, "session_id": "persisted-unit-session"},
                "learning_context": {"objective": base["learning_objective"], "concepts": ["convex lens"]},
                "activity": {"stage": "checkpoint", "mode": "typed", "activity_type": "typed_explanation"},
                "response_quality": {"raw_response": answer, "client_observation": "raw"},
            }

        with tempfile.TemporaryDirectory() as state_dir:
            with patch.dict(os.environ, {"PROOFMARK_STATE_DIR": state_dir}):
                first = adapt_track_b_plan({"base_payload": base, "learner_event": event("live-persist-1", "formula only")})
                duplicate = adapt_track_b_plan({"base_payload": base, "learner_event": event("live-persist-1", "formula only")})
                second = adapt_track_b_plan(
                    {
                        "base_payload": base,
                        "learner_event": event(
                            "live-persist-2",
                            "A convex lens ray diagram needs a principal axis because the source separates ray direction from the formula.",
                        ),
                    }
                )

        self.assertEqual(first["adaptive_update"]["accepted_event_count"], 1)
        self.assertEqual(duplicate["adaptive_update"]["accepted_event_count"], 1)
        self.assertIn("live-persist-1", duplicate["adaptive_update"]["event_store"]["duplicate_event_ids"])
        self.assertEqual(second["adaptive_update"]["accepted_event_count"], 2)
        self.assertEqual(second["adaptive_update"]["event_store"]["version"], 3)

    def test_adaptive_endpoint_drops_stored_stale_concepts_before_saving(self) -> None:
        base = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        stale_event = {
            "identity": {"event_id": "stale-live-001", "session_id": "stale-adapt-session"},
            "learning_context": {
                "objective": base["learning_objective"],
                "concepts": ["Bayes theorem"],
                "topic": "Practice",
            },
            "activity": {
                "stage": "practice",
                "mode": "typed",
                "activity_type": "adaptive_retest",
                "prompt_variant": "Solve a fresh Bayes theorem retest.",
            },
            "response_quality": {"raw_response": "This stale answer should not affect a convex lens lesson."},
        }
        valid_event = {
            "identity": {"event_id": "valid-live-001", "session_id": "stale-adapt-session"},
            "learning_context": {
                "objective": base["learning_objective"],
                "concepts": ["Convex lens"],
                "topic": "Practice",
            },
            "activity": {
                "stage": "practice",
                "mode": "typed",
                "activity_type": "typed_explanation",
                "prompt_variant": "Explain the convex lens ray diagram.",
            },
            "response_quality": {
                "raw_response": "A convex lens converges parallel rays through focus and uses the optical center ray.",
            },
        }

        with tempfile.TemporaryDirectory() as state_dir:
            with patch.dict(os.environ, {"PROOFMARK_STATE_DIR": state_dir}):
                stale = adapt_track_b_plan({"base_payload": base, "learner_event": stale_event})
                valid = adapt_track_b_plan({"base_payload": base, "learner_event": valid_event})

        self.assertEqual(stale["adaptive_update"]["accepted_event_count"], 0)
        self.assertEqual(stale["adaptive_update"]["event_store"]["ignored_stale_event_count"], 1)
        self.assertEqual(stale["mode"], "cold_start")
        self.assertEqual(valid["adaptive_update"]["accepted_event_count"], 1)
        self.assertEqual(valid["adaptive_update"]["event_store"]["event_count"], 1)
        self.assertNotIn("bayes", str(valid["learner_model"]["concept_mastery"]).lower())
        self.assertIn("Convex lens", valid["learner_model"]["concept_mastery"])

    def test_provider_rate_limit_notice_is_structured_without_key_leakage(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["generate_with_model"] = True
        payload["api_key"] = "sk-test-secret"
        payload["model"] = "unit-test-model"
        payload["constraints"]["analyze_sources_with_gemini"] = False

        with patch(
            "proofmark.generation._call_openai_compatible",
            side_effect=ProviderError("Generation provider HTTP 429: token rate limit", status_code=429, retry_after=3),
        ):
            result = build_track_b_plan(payload)

        self.assertEqual(result["model_generation"]["status"], "deterministic_fallback")
        self.assertEqual(result["provider_notices"][0]["status_code"], 429)
        self.assertIn("learning asset generation", result["provider_notices"][0]["stage"])
        self.assertNotIn("sk-test-secret", str(result))

    def test_provider_retry_reuses_full_context_after_rate_limit(self) -> None:
        calls = {"count": 0}

        def flaky_call() -> dict[str, str]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise ProviderError("HTTP 429", status_code=429, retry_after=0)
            return {"status": "ok"}

        with patch("proofmark.provider_runtime.time.sleep") as sleep:
            result = with_provider_retries("demo", flaky_call)

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(calls["count"], 2)
        sleep.assert_called_once()

    def test_provider_cache_avoids_repeating_successful_full_context_call(self) -> None:
        request_body = {"input": "large raw source context", "model": "unit-test-model"}
        calls = {"count": 0}

        def model_call() -> dict[str, str]:
            calls["count"] += 1
            return {"visual_artifact": "cached"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"PROOFMARK_PROVIDER_CACHE_DIR": tmpdir}):
                first, first_cache = cached_json("openai-generation", "unit-test-model", request_body, model_call)
                second, second_cache = cached_json("openai-generation", "unit-test-model", request_body, model_call)

        self.assertEqual(first, {"visual_artifact": "cached"})
        self.assertEqual(second, {"visual_artifact": "cached"})
        self.assertFalse(first_cache)
        self.assertTrue(second_cache)
        self.assertEqual(calls["count"], 1)

    def test_generation_parser_accepts_json_content_parts(self) -> None:
        parsed = _parse_generation_payload(
            {
                "output": [
                    {"type": "reasoning", "content": []},
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_json",
                                "json": {
                                    "next_learning_plan": ["Read the source chunk."],
                                    "visual_artifact": {"kind": "diagram"},
                                },
                            }
                        ],
                    },
                ]
            }
        )

        self.assertEqual(parsed["next_learning_plan"], ["Read the source chunk."])
        self.assertEqual(parsed["visual_artifact"]["kind"], "diagram")

    def test_voice_summary_requires_runtime_key(self) -> None:
        with self.assertRaises(InputError) as context:
            generate_voice_summary({"text": "Explain electric potential simply."})
        self.assertEqual(context.exception.code, "missing_elevenlabs_key")

    def test_voice_summary_selects_backend_voice_and_model(self) -> None:
        with patch("proofmark.voice._default_voice_id", return_value="voice-1"):
            with patch("proofmark.voice._default_model_id", return_value="model-1"):
                with patch("proofmark.voice._call_elevenlabs_tts", return_value=b"audio"):
                    result = generate_voice_summary({
                        "text": "Explain electric potential simply.",
                        "elevenlabs_api_key": "sk_test",
                    })
        self.assertEqual(result["voice_id"], "voice-1")
        self.assertEqual(result["model_id"], "model-1")
        self.assertNotIn("sk_test", str(result))

    def test_voice_summary_reports_when_backend_voice_unavailable(self) -> None:
        with patch("proofmark.voice._default_voice_id", return_value=""):
            with self.assertRaises(InputError) as context:
                generate_voice_summary({
                    "text": "Explain electric potential simply.",
                    "elevenlabs_api_key": "sk_test",
                })
        self.assertEqual(context.exception.code, "missing_elevenlabs_voice")

    def test_voice_summary_reports_when_backend_model_unavailable(self) -> None:
        with patch("proofmark.voice._default_voice_id", return_value="voice-1"):
            with patch("proofmark.voice._default_model_id", return_value=""):
                with self.assertRaises(InputError) as context:
                    generate_voice_summary({
                        "text": "Explain electric potential simply.",
                        "elevenlabs_api_key": "sk_test",
                    })
        self.assertEqual(context.exception.code, "missing_elevenlabs_model")

    def test_elevenlabs_voice_setup_normalizes_account_voices(self) -> None:
        raw = b'{"voices":[{"voice_id":"voice-1","name":"Asha","category":"premade","labels":{"accent":"Indian","use_case":"education"}}]}'
        with patch("proofmark.voice.urllib.request.urlopen", return_value=_FakeHttpResponse(raw)):
            result = list_elevenlabs_voices({"elevenlabs_api_key": "sk_test"})

        self.assertEqual(result["status"], "voices_loaded")
        self.assertEqual(result["voices"][0]["voice_id"], "voice-1")
        self.assertEqual(result["voices"][0]["name"], "Asha")
        self.assertNotIn("sk_test", str(result))

    def test_elevenlabs_model_setup_recommends_available_tts_model(self) -> None:
        raw = (
            b'[{"model_id":"eleven_multilingual_v2","name":"Multilingual v2",'
            b'"can_do_text_to_speech":true,"languages":[{"name":"English"}]}]'
        )
        with patch("proofmark.voice.urllib.request.urlopen", return_value=_FakeHttpResponse(raw)):
            result = list_elevenlabs_models({"elevenlabs_api_key": "sk_test"})

        self.assertEqual(result["status"], "models_loaded")
        self.assertEqual(result["recommended_model_id"], "eleven_multilingual_v2")
        self.assertEqual(result["models"][0]["languages"], ["English"])
        self.assertNotIn("sk_test", str(result))

    def test_runtime_api_key_is_not_echoed_in_generation_response(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["generate_with_model"] = False
        payload["api_key"] = "sk-test-secret"
        payload["gemini_api_key"] = "AIza-test-secret"
        payload["pinecone_api_key"] = "pcsk-test-secret"
        payload["pinecone_index_host"] = "https://test-index-host"
        result = build_track_b_plan(payload)

        serialized = str(result)
        self.assertNotIn("sk-test-secret", serialized)
        self.assertNotIn("AIza-test-secret", serialized)
        self.assertNotIn("pcsk-test-secret", serialized)
        self.assertIn("model_generation", result)

    def test_gemini_source_analysis_is_wired_when_requested(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["gemini_api_key"] = "AIza-test-secret"
        payload["gemini_model"] = "unit-gemini-model"
        payload["constraints"]["analyze_sources_with_gemini"] = True

        fake_analysis = {
            "summary": "Model saw source material and planned the pages.",
            "source_insights": [
                {
                    "source_id": "electrostatics-lecture",
                    "title": "Electrostatics lecture transcript",
                    "type": "video_transcript",
                    "url": "",
                    "media_role": "transcript",
                    "why_chosen": "Timestamped explanation.",
                    "concepts": ["Electric potential"],
                    "sections": [
                        {
                            "start": "03:15",
                            "end": "04:20",
                            "title": "Electric potential",
                            "summary": "Defines potential as work per unit charge.",
                            "source_chunk_id": "electrostatics-lecture-seg-1",
                        }
                    ],
                    "bullets": ["Potential is scalar."],
                    "visual_cues": ["Contrast electric potential with electric field"],
                }
            ],
            "video_timeline": [
                {
                    "source_id": "electrostatics-lecture",
                    "start": "03:15",
                    "end": "04:20",
                    "concept": "Electric potential",
                    "teaches": "Definition and scalar nature.",
                }
            ],
            "concepts": [
                {
                    "name": "Electric potential",
                    "why_it_matters": "It drives the transfer task.",
                    "common_trap": "Electric field",
                }
            ],
            "visual_learning_cues": [
                {
                    "cue": "Contrast electric potential with electric field",
                    "target_gap": "scalar vs vector",
                    "best_after": "first checkpoint",
                }
            ],
            "page_sequence": [
                {
                    "id": "source_media_lesson",
                    "page_type": "media_lesson",
                    "title": "Watch source",
                    "intent": "Ground the concept.",
                    "interaction": "watch",
                    "unlocks_next": "notes_checkpoint",
                }
            ],
            "questions_to_ask": [
                {
                    "type": "typed_explanation",
                    "prompt": "Explain electric potential in two sentences.",
                    "captures": ["typed_explanation", "source_grounding"],
                }
            ],
        }

        with patch("proofmark.source_analysis._call_gemini_source_analysis", return_value=fake_analysis):
            result = build_track_b_plan(payload)

        self.assertEqual(result["ai_source_analysis"]["status"], "model_generated")
        self.assertEqual(result["lesson_graph"]["planner_provider"], "gemini:unit-gemini-model")
        self.assertEqual(result["lesson_graph"]["pages"][0]["source_cards"][0]["sections"][0]["start"], "03:15")
        self.assertNotIn("AIza-test-secret", str(result))

    def test_provider_quiz_plan_is_regenerated_from_current_graph(self) -> None:
        payload = sample_track_b_payload(include_evidence=False, topic="ray_optics")
        payload["gemini_api_key"] = "AIza-test-secret"
        payload["gemini_model"] = "unit-gemini-model"
        payload["constraints"]["analyze_sources_with_gemini"] = True
        stale_analysis = {
            "summary": "The model returned a stale quiz plan.",
            "source_insights": [],
            "questions_to_ask": [
                {
                    "type": "mcq",
                    "prompt": "Which source-backed statement best separates Bayes theorem from Base rate?",
                    "captures": ["recognition"],
                },
                {
                    "type": "typed_explanation",
                    "prompt": "Explain Bayes theorem in two sentences.",
                    "captures": ["typed_explanation"],
                },
            ],
            "adaptive_quiz_blueprint": [{"concept": "Bayes theorem", "repeat_policy": "repeat"}],
            "reteaching_plan": [{"concept": "Base rate", "explanation": "stale reteach"}],
            "page_sequence": [{"id": "stale", "page_type": "checkpoint"}],
        }

        with patch("proofmark.source_analysis._call_gemini_source_analysis", return_value=stale_analysis):
            result = build_track_b_plan(payload)

        source_analysis = result["ai_source_analysis"]
        prompts = " ".join(question["prompt"] for question in source_analysis["questions_to_ask"])
        lesson_prompts = " ".join(
            question["prompt"]
            for page in result["lesson_graph"]["pages"]
            for question in page.get("questions", [])
            if isinstance(question, dict)
        )
        retest_text = str(next(page for page in result["lesson_graph"]["pages"] if page["type"] == "practice"))

        self.assertIn("Convex lens", prompts)
        self.assertIn("Principal axis", prompts)
        self.assertNotIn("Bayes", prompts)
        self.assertNotIn("Base rate", prompts)
        self.assertNotIn("Bayes", lesson_prompts)
        self.assertNotIn("Base rate", lesson_prompts)
        self.assertNotIn("Bayes", retest_text)
        self.assertNotIn("Base rate", retest_text)

    def test_model_asset_patch_drops_unsupported_known_concepts(self) -> None:
        packet = {
            "learning_objective": "Understand convex lens image formation with ray diagrams.",
            "learner_state_summary": {},
            "source_analysis_summary": {},
            "retrieved_source_chunks": [
                {
                    "source_title": "Ray optics notes",
                    "concepts": ["Convex lens", "Principal axis"],
                    "text": "A convex lens bends parallel rays toward the focal point along the principal axis.",
                }
            ],
        }
        stale_patch = {
            "personalized_notes": [
                "Bayes theorem depends on Base rate and sensitivity.",
            ],
            "student_study_pack": {
                "one_minute_summary": "Bayes theorem updates posterior probability from a Base rate.",
                "key_facts": ["Base rate is needed for Bayes theorem."],
            },
            "micro_assessment": ["Explain Bayes theorem in two sentences."],
            "hint_ladder": ["source-anchor hint"],
        }

        assets = _merge_model_asset_patch(packet, stale_patch)
        serialized = json.dumps(assets)

        self.assertNotIn("Bayes", serialized)
        self.assertNotIn("Base rate", serialized)
        self.assertIn("Convex lens", serialized)
        self.assertEqual(assets["hint_ladder"], ["source-anchor hint"])

    def test_compact_gemini_source_analysis_is_normalized_into_lesson_shape(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["gemini_api_key"] = "AIza-test-secret"
        payload["gemini_model"] = "unit-gemini-model"
        payload["constraints"]["analyze_sources_with_gemini"] = True

        compact_analysis = {
            "summary": "Potential is work per unit charge, and it behaves as a scalar.",
            "key_concepts": [
                {
                    "name": "Electric potential",
                    "why_it_matters": "It connects work, charge, and later circuit ideas.",
                    "common_trap": "Treating it like electric field.",
                }
            ],
            "key_facts": [
                {
                    "fact": "Electric potential is scalar.",
                    "why_it_matters": "Scalar addition changes how multi-charge questions are solved.",
                }
            ],
            "formulas": [
                {
                    "label": "Potential from work",
                    "latex": "V = \\frac{W}{q}",
                    "meaning": "Potential is work done per unit charge.",
                    "when_to_use": "Use when the source connects work, charge, and potential.",
                }
            ],
            "timestamp_guide": [
                {
                    "source_id": "electrostatics-lecture",
                    "start": "03:15",
                    "end": "04:20",
                    "title": "Definition",
                    "what_happens": "Defines electric potential using work per unit charge.",
                    "watch_for": ["scalar quantity", "work per charge"],
                }
            ],
            "common_mistakes": ["Confusing potential with electric field."],
            "source_notes": [
                {
                    "source_id": "electrostatics-lecture",
                    "title": "Electrostatics lecture transcript",
                    "media_role": "transcript",
                    "why_useful": "It provides the timestamped definition.",
                    "bullets": ["Potential is scalar."],
                }
            ],
        }

        with patch("proofmark.source_analysis._call_gemini_source_analysis", return_value=compact_analysis):
            result = build_track_b_plan(payload)

        source_analysis = result["ai_source_analysis"]
        lesson = source_analysis["student_video_lesson"]
        self.assertEqual(source_analysis["status"], "model_generated")
        self.assertEqual(source_analysis["concepts"][0]["name"], "Electric potential")
        self.assertEqual(source_analysis["video_timeline"][0]["start"], "03:15")
        self.assertEqual(lesson["one_minute_summary"], compact_analysis["summary"])
        self.assertEqual(lesson["key_facts"][0]["fact"], "Electric potential is scalar.")
        self.assertEqual(lesson["formula_cards"][0]["latex"], "V = \\frac{W}{q}")
        self.assertEqual(lesson["timestamp_guide"][0]["watch_for"][0], "scalar quantity")
        self.assertTrue(source_analysis["page_sequence"])
        self.assertTrue(source_analysis["concept_diagrams"])

    def test_vector_rag_request_falls_back_without_embedding_key(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["constraints"]["use_vector_rag"] = True
        result = build_track_b_plan(payload)

        self.assertEqual(result["rag_pipeline"]["type"], "local_lexical_tfidf")
        self.assertTrue(result["rag_pipeline"]["fallback_used"])
        self.assertIn("OpenAI API key", result["rag_pipeline"]["fallback_reason"])
        self.assertTrue(result["rag_pipeline"]["vector_rag_requested"])
        self.assertTrue(result["rag_pipeline"]["retrieved_chunks"])

    def test_vector_rag_uses_embeddings_when_key_is_supplied(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["constraints"]["use_vector_rag"] = True
        payload["api_key"] = "sk-test-secret"

        def fake_embeddings(texts: list[str], **_kwargs: object) -> list[list[float]]:
            vectors = [[1.0, 0.0, 0.0]]
            vectors.extend([[1.0, 0.0, 0.0] for _text in texts[1:]])
            return vectors

        with patch("proofmark.content_graph.embed_texts", side_effect=fake_embeddings):
            result = build_track_b_plan(payload)

        self.assertEqual(result["rag_pipeline"]["type"], "local_vector_rag")
        self.assertTrue(result["rag_pipeline"]["retrieved_chunks"])
        self.assertNotIn("sk-test-secret", str(result))

    def test_vector_rag_uses_pinecone_when_configured(self) -> None:
        payload = sample_track_b_payload(include_evidence=False)
        payload["constraints"]["use_vector_rag"] = True
        payload["api_key"] = "sk-test-secret"
        payload["pinecone_api_key"] = "pcsk-test-secret"
        payload["pinecone_index_host"] = "test-index-host.svc.pinecone.io"
        payload["constraints"]["pinecone_namespace"] = "learner-a"

        def fake_embeddings(texts: list[str], **_kwargs: object) -> list[list[float]]:
            vectors = [[1.0, 0.0, 0.0]]
            vectors.extend([[1.0, 0.0, 0.0] for _text in texts[1:]])
            return vectors

        def fake_pinecone(**kwargs: object) -> dict[str, object]:
            chunks = kwargs["chunks"]
            return {
                "namespace": kwargs["namespace"],
                "matches": [{"chunk": chunks[0], "score": 0.99}],
            }

        with patch("proofmark.content_graph.embed_texts", side_effect=fake_embeddings):
            with patch("proofmark.content_graph.pinecone_upsert_and_query", side_effect=fake_pinecone):
                result = build_track_b_plan(payload)

        self.assertEqual(result["rag_pipeline"]["type"], "pinecone_vector_rag")
        self.assertTrue(result["rag_pipeline"]["pinecone_enabled"])
        self.assertEqual(result["rag_pipeline"]["pinecone_namespace"], "learner-a")
        self.assertNotIn("sk-test-secret", str(result))
        self.assertNotIn("pcsk-test-secret", str(result))

    def test_pinecone_helper_accepts_host_without_scheme(self) -> None:
        calls: list[str] = []

        def fake_post(url: str, _headers: dict[str, str], _payload: dict[str, object]) -> dict[str, object]:
            calls.append(url)
            if url.endswith("/query"):
                return {"matches": [{"id": "chunk-1", "score": 0.9, "metadata": {"text": "grounded text"}}]}
            return {"upsertedCount": 1}

        with patch("proofmark.rag._post_json", side_effect=fake_post):
            result = pinecone_upsert_and_query(
                chunks=[
                    {
                        "id": "chunk-1",
                        "source_id": "source-1",
                        "source_title": "Source",
                        "source_type": "notes",
                        "text": "grounded text",
                    }
                ],
                vectors=[[1.0, 0.0]],
                query_vector=[1.0, 0.0],
                api_key="pcsk-test-secret",
                index_host="test-index-host.svc.pinecone.io",
                namespace="learner-a",
                top_k=1,
            )

        self.assertEqual(calls[0], "https://test-index-host.svc.pinecone.io/vectors/upsert")
        self.assertEqual(calls[1], "https://test-index-host.svc.pinecone.io/query")
        self.assertEqual(result["matches"][0]["chunk"]["text"], "grounded text")

    def test_pinecone_helper_handles_stale_match_metadata_without_crashing(self) -> None:
        def fake_post(url: str, _headers: dict[str, str], _payload: dict[str, object]) -> dict[str, object]:
            if url.endswith("/query"):
                return {
                    "matches": [
                        {
                            "id": "stale-record",
                            "score": 0.73,
                            "metadata": {
                                "text": "Older indexed text",
                                "source_title": "Old source",
                                "source_type": "notes",
                                "concepts": "Bayes theorem, Base rate",
                            },
                        }
                    ]
                }
            return {"upsertedCount": 1}

        with patch("proofmark.rag._post_json", side_effect=fake_post):
            result = pinecone_upsert_and_query(
                chunks=[
                    {
                        "id": "current-chunk",
                        "source_id": "source-1",
                        "source_title": "Source",
                        "source_type": "notes",
                        "text": "current grounded text",
                    }
                ],
                vectors=[[1.0, 0.0]],
                query_vector=[1.0, 0.0],
                api_key="pcsk-test-secret",
                index_host="test-index-host.svc.pinecone.io",
                namespace="learner-a",
                top_k=1,
            )

        match = result["matches"][0]["chunk"]
        self.assertEqual(match["id"], "stale-record")
        self.assertEqual(match["source_title"], "Old source")
        self.assertEqual(match["text"], "Older indexed text")
        self.assertEqual(match["concepts"], ["Bayes theorem", "Base rate"])

    def test_url_pdf_fetch_does_not_return_raw_pdf_noise(self) -> None:
        class FakeResponse:
            headers = {"Content-Type": "application/pdf"}

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self, _size: int) -> bytes:
                return b"%PDF-1.7\n1 0 obj << /Filter /FlateDecode >> stream\nx\x9c\x00\x00endstream"

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = extract_url_text("https://example.com/notes.pdf")

        self.assertEqual(result["text"], "")
        self.assertEqual(result["warning"], "url_type_not_text_fetched")

    def test_youtube_url_fetch_is_skipped_for_gemini_video_path(self) -> None:
        result = extract_url_text("https://www.youtube.com/watch?v=sGb3VLDvNRU")

        self.assertEqual(result["text"], "")
        self.assertEqual(result["warning"], "url_type_not_text_fetched")

    def test_url_fetch_blocks_private_and_local_targets(self) -> None:
        blocked = [
            "file:///etc/passwd",
            "http://127.0.0.1:8000/private",
            "http://localhost:8000/private",
            "http://10.0.0.5/internal",
            "http://169.254.169.254/latest/meta-data",
        ]
        for url in blocked:
            with self.subTest(url=url):
                with self.assertRaises(RagError):
                    extract_url_text(url)

    def test_url_fetch_blocks_private_redirect_targets(self) -> None:
        with self.assertRaises(RagError):
            _validated_redirect_url("https://example.com/source", "http://127.0.0.1:8000/private")

        with self.assertRaises(RagError):
            _validated_redirect_url("https://example.com/source", "//169.254.169.254/latest/meta-data")

    def test_server_grader_attaches_rubric_and_answer_based_misconception(self) -> None:
        graph = build_content_graph(sample_track_b_payload(include_evidence=False, topic="ray_optics"))
        graded = grade_learner_event(
            {
                "identity": {"event_id": "live-rubric-001"},
                "learning_context": {"concepts": ["convex lens"]},
                "activity": {"mode": "visual", "activity_type": "draw_question"},
                "response_quality": {"raw_response": "I only wrote the formula."},
                "interaction": {
                    "selected_features": ["formula"],
                    "expected_features": ["principal axis", "focus", "ray"],
                },
            },
            graph,
        )

        quality = graded["response_quality"]
        self.assertTrue(graded["server_scored"])
        self.assertEqual(quality["server_rubric_version"], "track-b-evidence-rubric-v1")
        self.assertTrue(quality["server_rubric"])
        self.assertIn("rubric_evidence", quality)
        self.assertIn("drawing omitted", graded["reasoning_signals"]["misconception"])

    def test_source_rationale_exposes_case_claims(self) -> None:
        result = build_track_b_plan(
            {
                "learning_objective": "Teach HTTP caching with ETag validators.",
                "content_set": [
                    {
                        "type": "notes",
                        "title": "HTTP caching note",
                        "text": (
                            "HTTP caching uses Cache-Control directives such as max-age and no-store. "
                            "An ETag is a validator representing a resource version. "
                            "Clients send If-None-Match with a previous ETag and the server can return 304 Not Modified."
                        ),
                    }
                ],
            }
        )

        selected_source = result["curated_learning_bundle"]["selected_sources"][0]
        claims = result["dynamic_case"]["grounding"]["source_claims"]

        self.assertIn("key_excerpt", selected_source)
        self.assertTrue(selected_source["key_excerpt"])
        self.assertTrue(any("HTTP caching uses Cache-Control" in claim for claim in claims))

    def test_unseen_linux_container_concepts_do_not_promote_generic_limit(self) -> None:
        result = build_track_b_plan(
            {
                "learning_objective": "Explain Linux containers, namespaces, cgroups, and container isolation.",
                "content_set": [
                    {
                        "type": "notes",
                        "title": "Linux container note",
                        "text": (
                            "Linux containers isolate processes using namespaces for PID, network, mount, IPC, and users. "
                            "Cgroups limit CPU, memory, and IO usage for a group of processes. "
                            "Container images are built from read-only layers plus a writable container layer. "
                            "Containers share the host kernel, so they are lighter than virtual machines but require careful isolation."
                        ),
                    }
                ],
            }
        )
        concepts = [concept["name"].lower() for concept in result["content_graph"]["concepts"]]

        self.assertIn("linux containers", concepts)
        self.assertIn("namespaces", concepts)
        self.assertIn("cgroups", concepts)
        self.assertNotEqual(concepts[0], "limit")
        self.assertNotIn("namespaces cgroups", concepts)

    def test_http_caching_extracts_protocol_specific_concepts(self) -> None:
        result = build_track_b_plan(
            {
                "learning_objective": "Teach backend engineers HTTP caching with ETag and Cache-Control for API responses.",
                "content_set": [
                    {
                        "type": "notes",
                        "title": "HTTP caching note",
                        "text": (
                            "HTTP caching uses Cache-Control directives such as max-age, no-store, private, and must-revalidate. "
                            "An ETag is a validator representing a resource version. "
                            "Clients send If-None-Match with a previous ETag and the server can return 304 Not Modified without the response body. "
                            "Avoid caching personalized API responses without private or no-store because shared caches can leak user data."
                        ),
                    }
                ],
            }
        )
        concepts = [concept["name"].lower() for concept in result["content_graph"]["concepts"]]

        self.assertIn("http caching", concepts)
        self.assertIn("etag", concepts)
        self.assertIn("cache-control", concepts)
        self.assertIn("304 not modified", concepts)
        self.assertNotIn("api responses", concepts)

    def test_source_quality_warnings_cover_thin_and_irrelevant_inputs(self) -> None:
        thin = build_content_graph(
            {
                "learning_objective": "Teach photosynthesis inputs and outputs.",
                "content_set": [{"type": "notes", "title": "Tiny note", "text": "Plants make food."}],
            }
        )
        irrelevant = build_content_graph(
            {
                "learning_objective": "Teach Bayes theorem for medical testing.",
                "content_set": [
                    {
                        "type": "notes",
                        "title": "Recipe note",
                        "text": "Sourdough bread uses flour, water, salt, and a starter culture.",
                    }
                ],
            }
        )

        self.assertIn("thin_content_set", [warning["code"] for warning in thin["warnings"]])
        self.assertIn("low_objective_source_overlap", [warning["code"] for warning in irrelevant["warnings"]])

    def test_app_auth_and_rate_limit_helpers_are_deterministic(self) -> None:
        with patch.dict(os.environ, {"PROOFMARK_API_TOKEN": "secret-token"}):
            self.assertFalse(_client_authorized({}))
            self.assertTrue(_client_authorized({"Authorization": "Bearer secret-token"}))
            self.assertTrue(_client_authorized({"X-Proofmark-Token": "secret-token"}))

        records: deque[float] = deque()
        self.assertEqual(_rate_limit_decision(records, now=10.0, limit=2, window_seconds=60), (True, 0))
        self.assertEqual(_rate_limit_decision(records, now=11.0, limit=2, window_seconds=60), (True, 0))
        allowed, retry_after = _rate_limit_decision(records, now=12.0, limit=2, window_seconds=60)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_default_post_body_limit_accepts_demo_pdf_uploads(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_max_post_body_bytes(), DEFAULT_MAX_POST_BODY_BYTES)
            self.assertGreaterEqual(_max_post_body_bytes(), 24 * 1024 * 1024)

        with patch.dict(os.environ, {"PROOFMARK_MAX_POST_BODY_BYTES": "4096"}):
            self.assertEqual(_max_post_body_bytes(), 1_000_000)

    def test_internal_error_payload_does_not_expose_exception_details(self) -> None:
        payload = internal_error_payload("req-123")
        rendered = str(payload)

        self.assertEqual(payload["error"]["request_id"], "req-123")
        self.assertNotIn("ValueError", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("Exception", rendered)

    def test_runtime_env_loader_keeps_existing_env_and_loads_demo_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, ".proofmark_demo.env")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "# local demo keys only\n"
                    "OPENAI_API_KEY=file-secret\n"
                    "OPENAI_MODEL=\"gpt-5.1\"\n"
                    "PROOFLOOP_GENERATE_WITH_MODEL=1 # enable demo provider\n"
                )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "existing-secret"}, clear=False):
                result = load_runtime_env(path)

                self.assertTrue(result["loaded"])
                self.assertEqual(os.environ["OPENAI_API_KEY"], "existing-secret")
                self.assertEqual(os.environ["OPENAI_MODEL"], "gpt-5.1")
                self.assertEqual(os.environ["PROOFLOOP_GENERATE_WITH_MODEL"], "1")

    def test_learner_model_is_multidimensional(self) -> None:
        profile = infer_learner_profile({"learner_events": sample_evidence_events()})

        self.assertTrue(profile["profile_available"])
        self.assertIn("concept_mastery", profile)
        self.assertIn("typed_explanation", profile["skill_dimensions"])
        self.assertIn("hint_independence", profile["skill_dimensions"])
        self.assertTrue(profile["current_misconceptions"])

    def test_missing_required_track_b_inputs_are_rejected(self) -> None:
        with self.assertRaises(InputError) as exc:
            build_track_b_plan({"content_set": [{"text": "Some content"}]})

        self.assertEqual(exc.exception.code, "missing_learning_objective")


if __name__ == "__main__":
    unittest.main()
