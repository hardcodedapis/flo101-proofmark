from __future__ import annotations

from typing import Any

from .learner_model import ANCHOR_PROFILES


def build_dynamic_case(
    objective: str,
    graph: dict[str, Any],
    bundle: dict[str, Any],
    learner_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    concepts = graph.get("concepts", [])[:5]
    primary = concepts[0]["name"] if concepts else "the main concept"
    secondary = concepts[1]["name"] if len(concepts) > 1 else "a prerequisite concept"
    selected_sources = bundle.get("selected_sources", [])
    domain_case = _domain_case(objective, graph, bundle, primary, selected_sources)
    if domain_case:
        domain_case["rubric"] = _rubric(primary)
        domain_case["source_requirements"] = _source_requirements(selected_sources, primary)
        domain_case["personalized_variants"] = build_profile_variants(objective, graph, bundle, learner_profile)
        return domain_case

    source_claims = _case_claims(selected_sources, graph)
    case = {
        "title": f"Dynamic case: source-grounded transfer for {primary}",
        "scenario": (
            f"Use the selected source bundle to teach {primary}, then turn it into a fresh challenge for '{objective}'. "
            f"The learner must explain the source claim, connect it to {secondary}, and apply it to a changed example "
            "that is not copied from the notes."
        ),
        "constraints": [
            "Use only the supplied source bundle for factual claims.",
            f"Anchor the answer in this source claim: {source_claims[0] if source_claims else primary}.",
            "Show the reasoning chain, not just the final answer.",
            "Name at least one misconception or trap and how you avoided it.",
            "Include one confidence rating and one part you would review again.",
        ],
        "required_output": {
            "format": "mixed_response",
            "components": [
                f"one-sentence meaning of {primary}",
                "source citation to the selected bundle",
                f"changed example that uses {primary}",
                f"connection to {secondary}",
                "reasoning chain with the trap check",
                "confidence rating and revision target",
                "optional voice or roleplay explanation",
            ],
            "minimum_evidence": "The response must cite a selected source, transform it into a new case, and explain the reasoning.",
        },
        "grounding": {
            "must_cite": [source.get("source_id") for source in selected_sources[:3] if source.get("source_id")],
            "why_this_challenge_follows": _source_reason(selected_sources, primary),
            "source_claims": source_claims[:4],
            "what_would_fail": [
                "Uses only the concept name without a source-backed claim.",
                "Copies the source example without changing the situation.",
                "Gives a final answer without the misconception/trap check.",
            ],
        },
        "rubric": _rubric(primary),
        "source_requirements": [
            *_source_requirements(selected_sources, primary)
        ],
        "personalized_variants": build_profile_variants(objective, graph, bundle, learner_profile),
    }
    return case


def _case_claims(selected_sources: list[dict[str, Any]], graph: dict[str, Any]) -> list[str]:
    claims: list[str] = []
    for source in selected_sources:
        source_claims = source.get("source_claims") if isinstance(source.get("source_claims"), list) else []
        candidates = [
            *source_claims,
            source.get("key_excerpt"),
            source.get("text"),
            source.get("why_selected"),
            *(source.get("why_chosen") if isinstance(source.get("why_chosen"), list) else []),
        ]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            sentence = text.split(". ", 1)[0].strip()
            if len(sentence) > 18 and sentence not in claims:
                claims.append(sentence[:220])
    if claims:
        return claims
    for chunk in graph.get("chunks", [])[:4]:
        if not chunk.get("content_is_grounded", True):
            continue
        sentence = str(chunk.get("text", "")).split(". ", 1)[0].strip()
        if len(sentence) > 18 and sentence not in claims:
            claims.append(sentence[:220])
    return claims


def _domain_case(
    objective: str,
    graph: dict[str, Any],
    bundle: dict[str, Any],
    primary: str,
    selected_sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    haystack = " ".join(
        [objective]
        + [concept.get("name", "") for concept in graph.get("concepts", [])]
        + [chunk.get("text", "") for chunk in graph.get("chunks", []) if chunk.get("content_is_grounded", True)]
    ).lower()
    source_ids = [source.get("source_id") for source in selected_sources[:3] if source.get("source_id")]
    grounding = {
        "must_cite": source_ids,
        "why_this_challenge_follows": _source_reason(selected_sources, primary),
        "what_would_fail": [
            "Uses facts not present in the supplied content.",
            "Gives only a formula or final answer without explaining the reasoning.",
            "Misses the common misconception the bundle was built to repair.",
        ],
    }

    if _has_bayes_case_context(haystack):
        return {
            "title": "Dynamic case: medical-test Bayes trap",
            "scenario": (
                "A screening test is used for a disease that affects 1% of a population. "
                "The test has 95% sensitivity and 90% specificity. A learner claims that a positive result "
                "means the patient has a 95% chance of having the disease."
            ),
            "constraints": [
                "Use Bayes theorem or an equivalent frequency table.",
                "Keep base rate, sensitivity, specificity, false positives, and posterior probability separate.",
                "Cite the supplied source idea that supports the correction.",
                "State one sentence explaining why the learner's 95% claim is wrong.",
            ],
            "required_output": {
                "format": "calculation_plus_explanation",
                "components": [
                    "calculate P(disease | positive)",
                    "show a 10,000-person frequency table or symbolic Bayes setup",
                    "explain the base-rate trap",
                    "cite the source chunk used",
                    "give one review target if the answer was wrong",
                ],
                "minimum_evidence": "The response must distinguish sensitivity from posterior probability.",
            },
            "grounding": grounding,
        }

    if any(token in haystack for token in ["convex lens", "ray diagram", "lens formula", "focal point", "optical center"]):
        return {
            "title": "Dynamic case: convex-lens image from rays and formula",
            "scenario": (
                "An object is placed 30 cm in front of a convex lens of focal length 10 cm. "
                "The learner must predict the image using both a ray diagram and the lens formula."
            ),
            "constraints": [
                "Draw or describe the principal axis, lens, optical center, F and 2F marks.",
                "Use two principal rays: parallel-to-axis then through focus, and through optical center.",
                "Use the sign convention in the lens formula.",
                "State whether the image is real/virtual, inverted/erect, and magnified/diminished.",
            ],
            "required_output": {
                "format": "diagram_plus_numerical_solution",
                "components": [
                    "ray diagram description or uploaded drawing evidence",
                    "lens formula setup",
                    "image distance and magnification",
                    "image nature",
                    "one common sign-convention trap",
                ],
                "minimum_evidence": "The response must use both a diagrammatic argument and a formula check.",
            },
            "grounding": grounding,
        }

    if any(token in haystack for token in ["galvanic", "nernst", "electrode", "cell potential", "salt bridge"]):
        return {
            "title": "Dynamic case: Zn-Cu galvanic cell under concentration change",
            "scenario": (
                "A Zn/Cu galvanic cell is set up with Zn(s)|Zn2+(0.10 M)||Cu2+(1.0 M)|Cu(s). "
                "The learner must explain current flow and predict how changing ion concentration affects Ecell."
            ),
            "constraints": [
                "Identify anode, cathode, oxidation, and reduction.",
                "Show electron flow through the wire and ion role through the salt bridge.",
                "Use Ecell = Ecathode - Eanode for standard potential reasoning.",
                "Use the Nernst equation directionally for the concentration change.",
            ],
            "required_output": {
                "format": "labeled_cell_explanation",
                "components": [
                    "cell notation",
                    "anode/cathode labels",
                    "electron-flow explanation",
                    "Nernst direction or calculation",
                    "one misconception about anode/cathode signs",
                ],
                "minimum_evidence": "The response must connect chemical change to electrical output.",
            },
            "grounding": grounding,
        }

    if any(token in haystack for token in ["electric potential", "point charge", "equipotential", "work per unit charge"]):
        return {
            "title": "Dynamic case: potential from two charges",
            "scenario": (
                "Two point charges, +Q and -2Q, are placed at different distances from point P. "
                "The learner must find the electric potential at P and explain why the zero-potential point "
                "does not have to match the zero-field point."
            ),
            "constraints": [
                "Use scalar addition for potential.",
                "Preserve charge signs.",
                "Contrast potential with electric field.",
                "Cite the source segment that defines potential or scalar behavior.",
            ],
            "required_output": {
                "format": "calculation_plus_concept_contrast",
                "components": [
                    "potential expression",
                    "sign-aware scalar addition",
                    "contrast with electric field vector addition",
                    "source citation",
                    "one confidence rating and review target",
                ],
                "minimum_evidence": "The response must not treat electric potential like a vector field.",
            },
            "grounding": grounding,
        }

    return None


def _has_bayes_case_context(haystack: str) -> bool:
    if "bayes" in haystack:
        return True
    medical_markers = {"medical test", "disease", "screening", "prevalence"}
    probability_markers = {
        "base rate",
        "posterior",
        "specificity",
        "false positive",
        "false negative",
        "true positive",
        "true negative",
        "positive predictive",
        "negative predictive",
        "conditional probability",
    }
    if any(marker in haystack for marker in medical_markers):
        return any(marker in haystack for marker in probability_markers | {"sensitivity"})
    if "posterior" in haystack and any(marker in haystack for marker in {"base rate", "sensitivity", "specificity"}):
        return True
    if "base rate" in haystack and any(marker in haystack for marker in {"sensitivity", "specificity", "false positive"}):
        return True
    return "sensitivity" in haystack and "specificity" in haystack and "probability" in haystack


def _source_requirements(selected_sources: list[dict[str, Any]], primary: str) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source.get("source_id"),
            "title": source.get("title"),
            "use": f"Use this source for {', '.join(source.get('concepts', [])[:3]) or primary}.",
        }
        for source in selected_sources[:5]
    ]


def _source_reason(selected_sources: list[dict[str, Any]], primary: str) -> str:
    if not selected_sources:
        return f"The challenge targets {primary}, but no source rationale was available."
    titles = ", ".join(source.get("title", "source") for source in selected_sources[:3])
    concepts = []
    for source in selected_sources[:3]:
        for concept in source.get("concepts", []):
            if concept not in concepts:
                concepts.append(concept)
    concept_text = ", ".join(concepts[:5]) or primary
    return f"The selected sources ({titles}) cover {concept_text}, so the case asks the learner to apply those ideas in a changed scenario."


def _rubric(primary: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "Concept accuracy",
            "weight": 0.24,
            "checks": [
                f"Uses {primary} correctly.",
                "Separates the target concept from common confusions.",
            ],
        },
        {
            "name": "Reasoning chain",
            "weight": 0.22,
            "checks": [
                "Explains why each step follows.",
                "Does not jump from formula/definition to answer without a causal link.",
            ],
        },
        {
            "name": "Source grounding",
            "weight": 0.18,
            "checks": [
                "References the curated source or segment used.",
                "Avoids unsupported claims outside the content set.",
            ],
        },
        {
            "name": "Transfer",
            "weight": 0.2,
            "checks": [
                "Applies the concept to the new case, not only the original example.",
                "Handles a changed number/context/constraint.",
            ],
        },
        {
            "name": "Metacognition",
            "weight": 0.16,
            "checks": [
                "Reports confidence.",
                "Identifies what should be reviewed next.",
            ],
        },
    ]


def build_profile_variants(
    objective: str,
    graph: dict[str, Any],
    bundle: dict[str, Any],
    learner_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    concepts = graph.get("concepts", [])[:5]
    primary = concepts[0]["name"] if concepts else "the core idea"
    selected_chunks = bundle.get("rag_context", {}).get("selected_chunks", [])
    video_segments = [
        {
            "source": chunk.get("source_title"),
            "segment": f"{chunk.get('start', '')}-{chunk.get('end', '')}".strip("-") or chunk.get("id"),
            "concepts": chunk.get("concepts", []),
        }
        for chunk in selected_chunks
        if chunk.get("start") or chunk.get("end")
    ][:3]
    if not video_segments:
        video_segments = [
            {
                "source": chunk.get("source_title"),
                "segment": chunk.get("id"),
                "concepts": chunk.get("concepts", []),
            }
            for chunk in selected_chunks[:3]
        ]

    variants = {
        "high_support": {
            "profile": ANCHOR_PROFILES["high_support"],
            "notes": f"Prerequisite-first notes for {primary}; define terms, show one small example, then ask the learner to restate it.",
            "mind_map": "Show only prerequisite -> concept -> misconception -> example. Hide advanced branches until checkpoint success.",
            "video_or_source_sections": video_segments[:2],
            "hints": [
                "Definition hint",
                "Contrast hint against the common confusion",
                "Step hint",
                "Worked mini-example",
            ],
            "voice_or_roleplay": "Scripted peer-teaching: explain the concept to a peer using one provided sentence starter.",
            "practice": "Two easy checks, one same-concept variant, one typed explanation.",
            "case_adjustment": "Use a guided version with labeled givens and fewer distractors.",
            "review_plan": "Review in 1 day, then 3 days if the learner solves a fresh variant.",
        },
        "balanced": {
            "profile": ANCHOR_PROFILES["balanced"],
            "notes": f"Structured notes for {primary}; include definition, example, common trap, and one application.",
            "mind_map": "Show full chapter-level map with two missing edges for the learner to complete.",
            "video_or_source_sections": video_segments[:3],
            "hints": [
                "Strategic hint",
                "Source-anchor hint",
                "Step hint only after a wrong second attempt",
            ],
            "voice_or_roleplay": "Teach-back prompt: explain the idea to a classmate, then answer one follow-up question.",
            "practice": "Mixed MCQ, typed explanation, and one transfer mini-case.",
            "case_adjustment": "Use the standard dynamic case with moderate ambiguity.",
            "review_plan": "Review in 2-3 days depending on confidence and written reasoning.",
        },
        "advanced": {
            "profile": ANCHOR_PROFILES["advanced"],
            "notes": f"Compressed notes for {primary}; focus on boundary conditions, traps, and transfer.",
            "mind_map": "Show dense concept graph with prerequisite links collapsed; ask learner to explain an edge.",
            "video_or_source_sections": video_segments[-2:] if len(video_segments) > 1 else video_segments,
            "hints": [
                "Minimal strategic nudge",
                "Counterexample",
                "No full scaffold unless transfer fails twice",
            ],
            "voice_or_roleplay": "Ambiguous roleplay: defend a decision while the system challenges the reasoning.",
            "practice": "One hard transfer case and one misconception trap question.",
            "case_adjustment": "Increase ambiguity, add a distractor constraint, and require justification.",
            "review_plan": "Review in 5-7 days unless the final case reveals a transfer gap.",
        },
    }

    dominant = (learner_profile or {}).get("dominant_anchor")
    return {
        "active_variant": dominant if dominant in variants and (learner_profile or {}).get("profile_available") else "cold_start_all_variants_shown",
        "why_variants_exist": "Same content can generate different teaching methods after evidence exists; before that, the first bundle exposes all channels through embedded checks.",
        "variants": variants,
    }
