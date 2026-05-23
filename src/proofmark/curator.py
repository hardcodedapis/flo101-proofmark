from __future__ import annotations

import os
from typing import Any

from .content_graph import build_content_graph, retrieve_chunks, source_coverage


def build_curated_bundle(
    payload: dict[str, Any],
    graph: dict[str, Any] | None = None,
    learner_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = graph or build_content_graph(payload)
    objective = graph["learning_objective"]
    concepts = graph.get("concepts", [])[:6]
    focus_terms = [concept["name"] for concept in concepts]
    retrieval = retrieve_chunks(
        graph,
        objective,
        limit=7,
        focus_terms=focus_terms,
        retrieval_config=_retrieval_config(payload),
    )
    selected_chunks = retrieval["selected_chunks"]

    return {
        "mode": "cold_start" if not (learner_profile or {}).get("profile_available") else "profile_aware",
        "objective": objective,
        "source_coverage": source_coverage(graph),
        "selected_sources": _source_rationales(selected_chunks),
        "concept_map": _concept_map(objective, graph),
        "guided_notes": _guided_notes(objective, concepts, selected_chunks),
        "worked_example": _worked_example(objective, concepts, selected_chunks),
        "embedded_evidence_sequence": _evidence_sequence(concepts),
        "checkpoint_questions": _checkpoint_questions(concepts),
        "rag_context": {
            "query": retrieval["query"],
            "strategy": retrieval.get("strategy", "local_lexical_tfidf"),
            "selected_chunks": selected_chunks,
            "trace": retrieval["trace"],
            "embedding_model": retrieval.get("embedding_model", ""),
            "pinecone_namespace": retrieval.get("namespace", ""),
            "fallback_used": retrieval.get("fallback_used", False),
            "fallback_reason": retrieval.get("fallback_reason", ""),
            "why_rag": "RAG grounds notes, examples, cases, and quizzes in the supplied content set instead of letting the model invent facts.",
        },
        "pedagogy": {
            "cold_start_rule": "Before learner data exists, use content structure plus universal supports: concept map, guided notes, worked example, embedded checks, then dynamic case.",
            "research_basis": [
                "Merrill first principles: task, activation, demonstration, application, integration",
                "4C/ID: whole task plus supportive and procedural information",
                "Cognitive load theory: worked examples before unguided problem solving",
                "ICAP: move passive reading into active, constructive, and interactive evidence",
                "Self-explanation: require learners to explain reasoning, not only select answers",
            ],
        },
    }


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


def _source_rationales(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        source_id = chunk["source_id"]
        if source_id not in by_source:
            by_source[source_id] = {
                "source_id": source_id,
                "title": chunk["source_title"],
                "type": chunk["source_type"],
                "url": chunk.get("url", ""),
                "chosen_segments": [],
                "concepts": [],
                "why_chosen": [],
                "why_selected": "",
                "key_excerpt": "",
                "source_claims": [],
            }
        row = by_source[source_id]
        location = f"{chunk.get('start', '')}-{chunk.get('end', '')}".strip("-") or chunk["id"]
        reason = chunk.get("selected_because", "Relevant to the learning objective.")
        claims = _claim_sentences(chunk.get("text", ""))
        row["chosen_segments"].append(location)
        row["concepts"].extend([concept for concept in chunk.get("concepts", []) if concept not in row["concepts"]])
        row["why_chosen"].append(reason)
        if not row["why_selected"]:
            row["why_selected"] = reason
        for claim in claims:
            if claim not in row["source_claims"]:
                row["source_claims"].append(claim)
        if claims and not row["key_excerpt"]:
            row["key_excerpt"] = claims[0]
    return list(by_source.values())


def _claim_sentences(text: str) -> list[str]:
    sentences = [sentence.strip() for sentence in str(text or "").strip().split(". ") if sentence.strip()]
    claims: list[str] = []
    for sentence in sentences[:3]:
        if len(sentence) >= 18:
            claims.append(sentence[:240])
    return claims


def _concept_map(objective: str, graph: dict[str, Any]) -> dict[str, Any]:
    top_concepts = graph.get("concepts", [])[:8]
    return {
        "center": objective,
        "nodes": [
            {
                "id": concept["id"],
                "label": concept["name"],
                "difficulty": concept["difficulty"],
                "bloom_level": concept["bloom_level"],
                "prerequisites": concept.get("prerequisites", []),
                "common_confusions": concept.get("common_confusions", []),
            }
            for concept in top_concepts
        ],
        "edges": graph.get("edges", [])[:12],
        "learner_task": "Complete one missing prerequisite edge and one common-confusion edge before reading the notes.",
    }


def _guided_notes(objective: str, concepts: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    top = concepts[:4]
    chunk_texts = [chunk["text"] for chunk in chunks[:4]]
    anchors = [
        {
            "concept": concept["name"],
            "definition_or_rule": _best_sentence_for(concept["name"], chunk_texts) or f"Use the supplied sources to define {concept['name']} in the context of {objective}.",
            "watch_for": concept.get("common_confusions", [])[:2],
        }
        for concept in top
    ]
    return {
        "format": "short_structured_notes",
        "sections": [
            {
                "title": "What this objective is really asking",
                "body": f"By the end, the learner should be able to use {top[0]['name'] if top else 'the key idea'} in a new case, explain the reasoning, and avoid common confusions.",
            },
            {
                "title": "Core ideas from supplied content",
                "anchors": anchors,
            },
            {
                "title": "Common traps",
                "body": _trap_sentence(top),
            },
        ],
        "source_grounding": [chunk["id"] for chunk in chunks[:5]],
    }


def _best_sentence_for(concept: str, sentences: list[str]) -> str:
    concept_lower = concept.lower()
    for text in sentences:
        for sentence in text.split(". "):
            if concept_lower in sentence.lower() and len(sentence) > 35:
                return sentence.strip()
    return ""


def _trap_sentence(concepts: list[dict[str, Any]]) -> str:
    confusions = []
    for concept in concepts:
        for confusion in concept.get("common_confusions", []):
            if confusion not in confusions:
                confusions.append(confusion)
    if not confusions:
        return "The first pass should explicitly ask the learner to separate definitions, examples, and application steps."
    return "The first pass should check whether the learner confuses " + ", ".join(confusions[:5]) + "."


def _worked_example(objective: str, concepts: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    primary = concepts[0]["name"] if concepts else "the key concept"
    secondary = concepts[1]["name"] if len(concepts) > 1 else "the prerequisite idea"
    return {
        "title": f"Worked example: applying {primary}",
        "prompt": f"Use {primary} and {secondary} to solve a small version of the objective before attempting the final case.",
        "steps": [
            f"Identify where {primary} appears in the source chunk.",
            f"State the prerequisite idea that connects {secondary} to the case.",
            "Show the operation or reasoning step without skipping the causal link.",
            "Check the answer against one common confusion.",
        ],
        "source_anchor": chunks[0]["id"] if chunks else "",
        "evidence_probe": "Ask the learner to predict the next step before showing the final explanation.",
    }


def _evidence_sequence(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = concepts[0]["name"] if concepts else "core concept"
    secondary = concepts[1]["name"] if len(concepts) > 1 else "supporting concept"
    return [
        {
            "stage": "concept_map_probe",
            "mode": "visual",
            "learner_action": f"Connect {primary} to its prerequisite and one common confusion.",
            "signals_collected": ["visual_interpretation", "concept_discrimination", "confidence", "time_to_first_action"],
            "adaptive_use": "If concept edges are wrong, route to visual contrast before harder practice.",
        },
        {
            "stage": "guided_notes_checkpoint",
            "mode": "text",
            "learner_action": f"Summarize {primary} in one sentence and mark the source chunk that supports it.",
            "signals_collected": ["text_comprehension", "source_grounding", "precision", "confidence_calibration"],
            "adaptive_use": "If summary is vague, generate tighter notes and a source-anchored hint.",
        },
        {
            "stage": "worked_example_checkpoint",
            "mode": "typed_explanation",
            "learner_action": "Predict the next reasoning step in the worked example.",
            "signals_collected": ["causal_link_quality", "step_order_quality", "hint_dependence", "revision_count"],
            "adaptive_use": "If the learner copies formulas without reasoning, route to teach-back or visual contrast.",
        },
        {
            "stage": "micro_quiz",
            "mode": "quiz",
            "learner_action": f"Answer two fast checks mixing {primary} and {secondary}.",
            "signals_collected": ["correctness", "response_time", "guess_or_slip_uncertainty", "confidence"],
            "adaptive_use": "If correctness is high but confidence is low, build calibration; if confidence is high but wrong, repair misconception.",
        },
        {
            "stage": "voice_or_roleplay_probe",
            "mode": "voice_roleplay",
            "learner_action": "Explain the concept aloud or defend a decision in a short roleplay.",
            "signals_collected": ["spoken_explanation", "fluency", "composure", "correction_uptake", "conceptual_clarity"],
            "adaptive_use": "If speech is weak but written is strong, use low-pressure voice rehearsal; if concept is weak, do not over-index on speaking.",
        },
        {
            "stage": "final_dynamic_case",
            "mode": "case",
            "learner_action": "Produce the required final output independently.",
            "signals_collected": ["transfer", "integration", "independent_performance", "retention_seed"],
            "adaptive_use": "This becomes the first full learner model update and drives the next personalized bundle.",
        },
    ]


def _checkpoint_questions(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = concepts[0]["name"] if concepts else "the core concept"
    secondary = concepts[1]["name"] if len(concepts) > 1 else "a prerequisite"
    return [
        {
            "id": "visual-map-1",
            "type": "visual_map",
            "prompt": f"Place {primary}, {secondary}, prerequisite, and common confusion on a four-node map.",
            "captures": ["visual_interpretation", "concept_discrimination"],
        },
        {
            "id": "mcq-1",
            "type": "mcq",
            "prompt": f"Which statement best separates {primary} from {secondary}?",
            "captures": ["recognition", "misconception", "confidence"],
        },
        {
            "id": "typed-1",
            "type": "typed_explanation",
            "prompt": f"Explain why {primary} is needed for the learning objective in two sentences.",
            "captures": ["written_reasoning", "causal_link_quality", "source_grounding"],
        },
        {
            "id": "voice-1",
            "type": "voice_or_roleplay",
            "prompt": f"Teach {primary} to a peer who keeps confusing it with {secondary}.",
            "captures": ["spoken_explanation", "composure", "correction_uptake"],
        },
    ]
