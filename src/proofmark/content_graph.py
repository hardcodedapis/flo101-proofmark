from __future__ import annotations

import math
import os
import re
from collections import Counter, defaultdict
from typing import Any

from .documents import has_document_payload, parse_document_source
from .rag import RagError, cosine_similarity, embed_texts, extract_url_text, pinecone_upsert_and_query
from .schema import InputError


STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "and",
    "also",
    "because",
    "before",
    "being",
    "below",
    "between",
    "both",
    "backend",
    "but",
    "cannot",
    "could",
    "does",
    "doing",
    "done",
    "each",
    "engineer",
    "engineers",
    "explain",
    "explains",
    "for",
    "from",
    "have",
    "into",
    "just",
    "learn",
    "learner",
    "learning",
    "make",
    "manager",
    "managers",
    "more",
    "must",
    "need",
    "not",
    "notes",
    "objective",
    "only",
    "or",
    "other",
    "student",
    "students",
    "should",
    "than",
    "teach",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "understand",
    "using",
    "what",
    "when",
    "where",
    "which",
    "while",
    "without",
    "with",
    "would",
    "fast",
    "faster",
}

KNOWN_CONCEPTS = {
    "anode",
    "base rate",
    "bayes theorem",
    "cathode",
    "cell potential",
    "conditional probability",
    "convex lens",
    "electrode potential",
    "electric potential",
    "electric field",
    "equipotential surface",
    "false negative",
    "false positive",
    "focal length",
    "focal point",
    "galvanic cell",
    "image formation",
    "lens formula",
    "magnification",
    "nernst equation",
    "optical center",
    "oxidation",
    "posterior probability",
    "point charge",
    "potential difference",
    "potential energy",
    "principal axis",
    "probability",
    "reduction",
    "salt bridge",
    "scalar quantity",
    "sensitivity",
    "specificity",
    "true negative",
    "true positive",
    "unit charge",
    "vector quantity",
    "work done",
    "work per unit charge",
    "coulomb force",
    "work-energy theorem",
    "attention weights",
    "autoregressive decoding",
    "cache-control",
    "etag",
    "http caching",
    "if-none-match",
    "inference latency",
    "key vectors",
    "kv cache",
    "no-store",
    "query vectors",
    "shared caches",
    "transformer attention",
    "value vectors",
    "304 not modified",
    "derivative",
    "integral",
    "limit",
    "continuity",
    "reduction",
    "equilibrium",
    "rate law",
    "organic mechanism",
    "coordination compound",
    "hybridization",
}

KNOWN_CONFUSIONS = {
    "bayes theorem": ["base rate", "sensitivity", "posterior probability"],
    "base rate": ["sensitivity", "specificity", "posterior probability"],
    "sensitivity": ["specificity", "positive predictive value", "posterior probability"],
    "specificity": ["sensitivity", "false positive rate"],
    "convex lens": ["concave lens", "mirror", "image distance"],
    "lens formula": ["sign convention", "magnification", "mirror formula"],
    "galvanic cell": ["electrolytic cell", "anode sign", "cathode sign"],
    "anode": ["cathode", "oxidation", "reduction"],
    "cathode": ["anode", "oxidation", "reduction"],
    "nernst equation": ["standard cell potential", "reaction quotient", "equilibrium constant"],
    "electric potential": ["electric field", "potential energy", "voltage"],
    "electric field": ["electric potential", "force", "flux"],
    "work": ["energy", "force", "potential"],
    "derivative": ["slope", "rate of change", "differential"],
    "integral": ["area", "antiderivative", "summation"],
    "equilibrium": ["rate", "completion", "yield"],
    "oxidation": ["reduction", "charge", "valency"],
    "probability": ["odds", "frequency", "conditional probability"],
    "http caching": ["etag", "cache-control", "shared caches"],
    "etag": ["if-none-match", "304 not modified", "resource version"],
}

BAYES_CONTEXT_CONCEPTS = {
    "sensitivity",
    "specificity",
    "false negative",
    "false positive",
    "true negative",
    "true positive",
}
BAYES_CONTEXT_MARKERS = {
    "bayes",
    "base rate",
    "posterior",
    "medical test",
    "disease",
    "screening",
    "prevalence",
    "specificity",
    "false positive",
    "false negative",
    "true positive",
    "true negative",
    "positive predictive",
    "negative predictive",
    "conditional probability",
}

DOMAIN_CONCEPT_RULES = [
    {
        "domain": "bayes_probability",
        "label": "Bayes/probability",
        "triggers": ["bayes", "sensitivity", "specificity", "posterior", "medical test", "disease"],
        "concepts": [
            "bayes theorem",
            "base rate",
            "sensitivity",
            "specificity",
            "false positive",
            "posterior probability",
            "conditional probability",
        ],
    },
    {
        "domain": "ray_optics",
        "label": "ray optics / convex lenses",
        "triggers": ["convex lens", "ray diagram", "lens formula", "focal", "optical center"],
        "concepts": [
            "convex lens",
            "principal axis",
            "focal point",
            "optical center",
            "image formation",
            "lens formula",
            "magnification",
        ],
    },
    {
        "domain": "electrochemistry",
        "label": "electrochemistry",
        "triggers": ["galvanic", "nernst", "electrochem", "cell potential", "salt bridge"],
        "concepts": [
            "galvanic cell",
            "anode",
            "cathode",
            "oxidation",
            "reduction",
            "salt bridge",
            "cell potential",
            "nernst equation",
        ],
    },
    {
        "domain": "electrostatics",
        "label": "electrostatics",
        "triggers": ["electric potential", "equipotential", "point charge", "work per unit charge"],
        "concepts": [
            "electric potential",
            "electric field",
            "work per unit charge",
            "point charge",
            "scalar quantity",
            "equipotential surface",
            "potential energy",
        ],
    },
]

BAD_PHRASE_TAILS = {
    "true",
    "false",
    "medical",
    "example",
    "given",
    "known",
    "unknown",
    "question",
    "answer",
    "enlightenment",
    "response",
    "responses",
    "request",
    "requests",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+", " ", str(value)).strip()


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return text[:72] or "item"


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", text.lower())
        if token not in STOPWORDS
    ]


def _same_url_text(text: str, url: str) -> bool:
    if not text or not url:
        return False
    cleaned_text = text.strip().rstrip("/")
    cleaned_url = url.strip().rstrip("/")
    return cleaned_text == cleaned_url


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", _clean_text(text))
    return [part.strip() for part in parts if part.strip()]


def _chunk_text(text: str, target_sentences: int = 3) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []
    chunks = []
    for index in range(0, len(sentences), target_sentences):
        chunk = " ".join(sentences[index : index + target_sentences]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _normalize_content_set(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("content_set")
    if raw is None:
        raw = payload.get("content")
    if raw is None:
        raw = payload.get("resources")
    if isinstance(raw, str):
        raw = [{"type": "notes", "title": "Pasted notes", "text": raw}]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        raise InputError(
            "missing_content_set",
            "Track B requires a small content set: URLs, docs, notes, transcript chunks, or pasted text.",
        )

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, str):
            source = {
                "id": f"source-{index}",
                "type": "notes",
                "title": f"Content item {index}",
                "text": item,
            }
        elif isinstance(item, dict):
            title = _clean_text(
                item.get("title")
                or item.get("name")
                or item.get("filename")
                or item.get("url")
                or f"Content item {index}"
            )
            source = {
                "id": _clean_text(item.get("id") or _slug(title) or f"source-{index}"),
                "type": _clean_text(item.get("type") or item.get("kind") or "notes").lower(),
                "title": title,
                "url": _clean_text(item.get("url")),
                "text": _clean_text(item.get("text") or item.get("body") or item.get("notes")),
                "transcript": _clean_text(item.get("transcript")),
                "segments": item.get("segments") if isinstance(item.get("segments"), list) else [],
            }
            if _same_url_text(source["text"], source["url"]):
                source["text"] = ""
                source["url_text_discarded"] = True
            if has_document_payload(item):
                parsed = parse_document_source(item)
                source["type"] = _clean_text(item.get("type") or "document").lower()
                source["title"] = title or parsed["filename"]
                source["filename"] = parsed["filename"]
                source["mime_type"] = parsed["mime_type"]
                source["document_parser"] = parsed["parser"]
                source["math_detected"] = parsed["math_detected"]
                if parsed.get("text"):
                    source["text"] = parsed["text"]
                if parsed.get("parse_warning"):
                    source["parse_warning"] = parsed["parse_warning"]
        else:
            continue

        if _should_fetch_urls(payload) and source.get("url") and not source.get("segments"):
            try:
                fetched = extract_url_text(source["url"])
                if fetched.get("text"):
                    source["text"] = fetched["text"]
                    source["fetched"] = True
                    source["content_type"] = fetched.get("content_type", "")
                elif fetched.get("warning"):
                    source["fetch_warning"] = fetched["warning"]
            except RagError as exc:
                source["fetch_error"] = str(exc)

        _set_source_state(source)
        normalized.append(source)

    if not normalized:
        raise InputError("missing_content_set", "No usable content items were found.")
    return normalized[:12]


def _set_source_state(source: dict[str, Any]) -> None:
    has_segments = bool(source.get("segments"))
    has_text = bool(source.get("text"))
    has_transcript = bool(source.get("transcript"))
    if has_segments or has_text or has_transcript:
        if source.get("fetched"):
            state = "fetched_text"
        elif source.get("document_parser"):
            state = "parsed_document"
        elif has_segments:
            state = "transcript_segments"
        else:
            state = "usable_text"
        source["source_state"] = state
        source["content_is_grounded"] = True
        return

    if source.get("fetch_error"):
        source["source_state"] = "fetch_failed"
        source["warning"] = "url_fetch_failed"
    elif source.get("fetch_warning"):
        source["source_state"] = "unsupported_url_fetch"
        source["warning"] = "url_type_not_text_fetched"
    elif source.get("parse_warning"):
        source["source_state"] = "parse_failed"
        source["warning"] = "document_parse_warning"
    else:
        source["source_state"] = "metadata_only"
        source["warning"] = "url_metadata_only" if source.get("url") else "metadata_only"
    source["content_is_grounded"] = False
    source["text"] = " ".join(
        part for part in [f"Metadata only: {source.get('title', '')}", source.get("url", "")] if part
    ).strip()


def _should_fetch_urls(payload: dict[str, Any]) -> bool:
    constraints = payload.get("constraints", {}) if isinstance(payload.get("constraints"), dict) else {}
    return bool(
        payload.get("fetch_urls")
        or constraints.get("fetch_urls")
        or os.getenv("PROOFLOOP_FETCH_URLS", "").lower() in {"1", "true", "yes"}
    )


def _extract_phrases(text: str) -> Counter[str]:
    tokens = _tokens(text)
    counts: Counter[str] = Counter(tokens)
    lower = text.lower()
    for concept in KNOWN_CONCEPTS:
        if not _known_concept_allowed(concept, lower):
            continue
        if concept in lower:
            counts[concept] += 8 + lower.count(concept)
    for size in (2, 3):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase_tokens = tokens[index : index + size]
            if any(token in STOPWORDS for token in phrase_tokens):
                continue
            phrase = " ".join(phrase_tokens)
            if len(phrase) > 6 and _phrase_quality(phrase):
                counts[phrase] += size
    return counts


def _known_concept_allowed(concept: str, lower_text: str) -> bool:
    if concept == "limit":
        math_markers = {"calculus", "function", "continuity", "derivative", "integral", "approaches"}
        return bool(math_markers & set(_tokens(lower_text)))
    if concept in BAYES_CONTEXT_CONCEPTS:
        return _has_bayes_context(lower_text, ignored={concept})
    return True


def _phrase_quality(phrase: str) -> bool:
    parts = phrase.split()
    if not parts:
        return False
    if phrase in KNOWN_CONCEPTS:
        return True
    if parts[0] in {"understand", "explain", "solve", "find", "given"}:
        return False
    if parts[-1] in {"and", "but", "or", "the", "a"}:
        return False
    if parts[-1] in BAD_PHRASE_TAILS:
        return False
    if len(parts) == 2 and parts[0] in {"theorem", "formula", "equation", "cell", "lens"}:
        return False
    if "theorem" in parts and "bayes" not in parts:
        return False
    if "sensitivity true" in phrase or "specificity true" in phrase:
        return False
    if "but" in parts:
        return False
    if len(parts) >= 3 and phrase not in KNOWN_CONCEPTS:
        return False
    if len(parts) == 3 and parts[0] in parts[1:]:
        return False
    return True


def _domain_concepts(corpus: str) -> list[str]:
    concepts: list[str] = []
    for hit in _domain_hits(corpus):
        for concept in hit["concepts"]:
            if concept not in concepts:
                concepts.append(concept)
    return concepts


def _domain_hits(text: str) -> list[dict[str, Any]]:
    lower = text.lower()
    hits: list[dict[str, Any]] = []
    for rule in DOMAIN_CONCEPT_RULES:
        triggers = [trigger for trigger in rule["triggers"] if trigger in lower]
        if triggers and _domain_rule_allowed(rule, lower, triggers):
            hits.append(
                {
                    "domain": rule.get("domain", rule["concepts"][0]),
                    "label": rule.get("label", rule["concepts"][0]),
                    "triggers": triggers,
                    "concepts": rule["concepts"],
                }
            )
    return hits


def _domain_rule_allowed(rule: dict[str, Any], lower_text: str, triggers: list[str]) -> bool:
    if rule.get("domain") != "bayes_probability":
        return True
    if "bayes" in lower_text:
        return True
    if any(marker in lower_text for marker in {"medical test", "disease", "screening", "prevalence"}):
        return any(marker in lower_text for marker in BAYES_CONTEXT_MARKERS - {"medical test", "disease", "screening", "prevalence"})
    if "posterior" in lower_text and any(marker in lower_text for marker in {"base rate", "sensitivity", "specificity", "false positive"}):
        return True
    if "base rate" in lower_text and any(marker in lower_text for marker in {"sensitivity", "specificity", "posterior", "false positive"}):
        return True
    if {"sensitivity", "specificity"}.issubset(set(triggers)) and "probability" in lower_text:
        return True
    return False


def _has_bayes_context(lower_text: str, ignored: set[str] | None = None) -> bool:
    ignored = ignored or set()
    return any(marker not in ignored and marker in lower_text for marker in BAYES_CONTEXT_MARKERS)


def _source_domain_corpus(sources: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for source in sources:
        if not source.get("content_is_grounded", True):
            continue
        parts.extend([source.get("title", ""), source.get("text", ""), source.get("transcript", "")])
        for segment in source.get("segments", []) or []:
            if isinstance(segment, dict):
                parts.append(_clean_text(segment.get("text") or segment.get("transcript") or segment.get("summary")))
    return " ".join(part for part in parts if part)


def _validate_objective_source_alignment(objective: str, sources: list[dict[str, Any]]) -> None:
    objective_hits = _domain_hits(objective)
    source_hits = _domain_hits(_source_domain_corpus(sources))
    if not objective_hits or not source_hits:
        return
    objective_domains = {hit["domain"] for hit in objective_hits}
    source_domains = {hit["domain"] for hit in source_hits}
    if not objective_domains.isdisjoint(source_domains):
        return
    objective_labels = _join_labels(hit["label"] for hit in objective_hits)
    source_labels = _join_labels(hit["label"] for hit in source_hits)
    raise InputError(
        "objective_source_mismatch",
        (
            f"The objective looks like {objective_labels}, but the supplied source text looks like {source_labels}. "
            "Clear the stale source text or change the objective before generating the learning bundle."
        ),
    )


def _join_labels(values: Any) -> str:
    labels = []
    for value in values:
        label = str(value).strip()
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return "another topic"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _objective_concepts(objective: str) -> list[str]:
    text = re.sub(
        r"^\s*(teach|explain|understand|learn|solve|compare|analyze|build|create)\s+",
        "",
        objective.strip(),
        flags=re.IGNORECASE,
    )
    parts = re.split(r",|\band\b|/|;|\bfor\b|\bwith\b|\busing\b|\bthrough\b", text, flags=re.IGNORECASE)
    concepts: list[str] = []
    for part in parts:
        tokens = [
            token
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{1,}", part.lower())
            if token not in STOPWORDS
        ]
        if not tokens or len(tokens) > 4:
            continue
        phrase = " ".join(tokens)
        if len(phrase) < 4 or phrase in concepts:
            continue
        if not _phrase_quality(phrase) and len(tokens) > 1:
            continue
        concepts.append(phrase)
    return concepts[:6]


def _infer_bloom_level(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["design", "create", "build", "generate", "construct"]):
        return "create"
    if any(word in lower for word in ["justify", "compare", "evaluate", "critique", "decide"]):
        return "evaluate"
    if any(word in lower for word in ["analyze", "differentiate", "diagnose", "explain why"]):
        return "analyze"
    if any(word in lower for word in ["solve", "apply", "use", "calculate", "derive"]):
        return "apply"
    if any(word in lower for word in ["explain", "summarize", "understand", "classify"]):
        return "understand"
    return "remember"


def _difficulty(text: str, bloom_level: str) -> float:
    tokens = _tokens(text)
    unique = len(set(tokens))
    formula_signal = len(re.findall(r"[=+\-*/^]|delta|lambda|theta|sigma|integral|derivative", text.lower()))
    bloom_boost = {
        "remember": 0.05,
        "understand": 0.12,
        "apply": 0.22,
        "analyze": 0.32,
        "evaluate": 0.4,
        "create": 0.46,
    }[bloom_level]
    raw = 0.2 + min(0.28, unique / 220) + min(0.24, formula_signal / 18) + bloom_boost
    return round(max(0.15, min(0.95, raw)), 2)


def _concept_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value[:1].upper() + value[1:]


def _build_chunks(sources: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    objective_terms = set(_tokens(objective))
    for source_index, source in enumerate(sources, start=1):
        segments = source.get("segments") or []
        if segments:
            for segment_index, segment in enumerate(segments, start=1):
                if not isinstance(segment, dict):
                    continue
                text = _clean_text(segment.get("text") or segment.get("transcript") or segment.get("summary"))
                if not text:
                    continue
                terms = _tokens(text)
                overlap = sorted(set(terms) & objective_terms)
                chunks.append(
                    {
                        "id": f"{source['id']}-seg-{segment_index}",
                        "source_id": source["id"],
                        "source_title": source["title"],
                        "source_type": source["type"],
                        "source_state": source.get("source_state", "usable_text"),
                        "content_is_grounded": bool(source.get("content_is_grounded", True)),
                        "url": source.get("url", ""),
                        "start": _clean_text(segment.get("start")),
                        "end": _clean_text(segment.get("end")),
                        "text": text,
                        "terms": terms,
                        "objective_overlap": overlap,
                    }
                )
            continue

        text = " ".join(part for part in [source.get("transcript", ""), source.get("text", "")] if part).strip()
        for chunk_index, chunk_text in enumerate(_chunk_text(text), start=1):
            terms = _tokens(chunk_text)
            overlap = sorted(set(terms) & objective_terms)
            chunks.append(
                {
                    "id": f"{source['id']}-chunk-{chunk_index}",
                    "source_id": source["id"],
                    "source_title": source["title"],
                    "source_type": source["type"],
                    "source_state": source.get("source_state", "usable_text"),
                    "content_is_grounded": bool(source.get("content_is_grounded", True)),
                    "url": source.get("url", ""),
                    "start": "",
                    "end": "",
                    "text": chunk_text,
                    "terms": terms,
                    "objective_overlap": overlap,
                }
            )

    if not chunks:
        raise InputError("empty_content_set", "Content items did not contain usable text or transcript data.")
    return chunks


def _chunk_concepts(chunk: dict[str, Any], concept_names: list[str]) -> list[str]:
    if not chunk.get("content_is_grounded", True):
        return []
    lower = chunk["text"].lower()
    found = []
    for concept in concept_names:
        if concept.lower() in lower:
            found.append(concept)
    if found:
        return found[:5]
    return [_concept_name(token) for token, _count in _extract_phrases(chunk["text"]).most_common(3)]


def _prerequisites_for(concept: str, all_names: list[str]) -> list[str]:
    lower = concept.lower()
    prereqs: list[str] = []
    for key, values in KNOWN_CONFUSIONS.items():
        if key in lower:
            prereqs.extend([value for value in values if value.lower() != lower])
    for name in all_names:
        name_lower = name.lower()
        if name_lower == lower:
            continue
        if name_lower in lower or any(part in lower for part in name_lower.split()):
            prereqs.append(name)
    cleaned = []
    for item in prereqs:
        display = _concept_name(item)
        if display not in cleaned:
            cleaned.append(display)
    return cleaned[:4]


def _common_confusions_for(concept: str, all_names: list[str]) -> list[str]:
    lower = concept.lower()
    confusions = []
    for key, values in KNOWN_CONFUSIONS.items():
        if key in lower or lower in key:
            confusions.extend(values)
    parts = set(lower.split())
    for name in all_names:
        name_lower = name.lower()
        if name_lower == lower:
            continue
        if parts & set(name_lower.split()):
            confusions.append(name)
    cleaned = []
    for item in confusions:
        display = _concept_name(item)
        if display != concept and display not in cleaned:
            cleaned.append(display)
    return cleaned[:4]


def _build_concepts(objective: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = _extract_phrases(objective)
    objective_phrases = set(counts)
    explicit_objective_concepts = _objective_concepts(objective)
    for concept in explicit_objective_concepts:
        counts[concept] += 35
    for phrase in list(objective_phrases):
        if _phrase_quality(phrase) and " " in phrase:
            counts[phrase] += 8
    grounded_chunks = [chunk for chunk in chunks if chunk.get("content_is_grounded", True)]
    corpus = objective + " " + " ".join(chunk["text"] for chunk in grounded_chunks)
    corpus_lower = corpus.lower()
    known_present = {
        concept
        for concept in KNOWN_CONCEPTS
        if concept in corpus_lower and _known_concept_allowed(concept, corpus_lower)
    }
    priority_concepts = _domain_concepts(corpus)
    for concept in priority_concepts:
        counts[concept] += 40
        known_present.add(concept)

    for chunk in grounded_chunks:
        phrase_counts = _extract_phrases(chunk["text"])
        for phrase, count in phrase_counts.items():
            source_boost = 2 if phrase in " ".join(chunk["objective_overlap"]).lower() else 0
            counts[phrase] += count + source_boost

    candidates = [
        (phrase, count)
        for phrase, count in counts.items()
        if len(phrase) >= 4 and not phrase.isdigit()
    ]
    candidates.sort(key=lambda item: (item[1], len(item[0])), reverse=True)

    names: list[str] = []
    for concept in priority_concepts:
        if concept in counts and concept not in [name.lower() for name in names]:
            names.append(_concept_name(concept))
    for concept in explicit_objective_concepts:
        if concept in counts and concept not in [name.lower() for name in names]:
            names.append(_concept_name(concept))
    for phrase, _count in candidates:
        if len(names) >= 12:
            break
        if not _phrase_quality(phrase):
            continue
        if phrase not in objective_phrases and phrase not in known_present and phrase not in priority_concepts and counts[phrase] < 4:
            continue
        if len(known_present) >= 3 and phrase not in known_present:
            continue
        if any(phrase in existing.lower() or existing.lower() in phrase for existing in names):
            continue
        names.append(_concept_name(phrase))

    if not names:
        names = [_concept_name(word) for word in _tokens(objective)[:6]]

    concepts = []
    for index, name in enumerate(names, start=1):
        related_chunks = [chunk for chunk in grounded_chunks if name.lower() in chunk["text"].lower()]
        if not related_chunks and name.lower() in priority_concepts:
            related_chunks = [
                chunk for chunk in grounded_chunks
                if any(token in chunk["text"].lower() for token in _tokens(name))
            ][:3]
        text_basis = " ".join([objective] + [chunk["text"] for chunk in related_chunks[:3]])
        bloom = _infer_bloom_level(text_basis)
        concepts.append(
            {
                "id": f"concept-{index}",
                "name": name,
                "weight": round(max(0.15, min(1.0, counts[name.lower()] / max(1, counts.most_common(1)[0][1]))), 2),
                "bloom_level": bloom,
                "difficulty": _difficulty(text_basis, bloom),
                "source_ids": sorted({chunk["source_id"] for chunk in related_chunks})[:5],
                "chunk_ids": [chunk["id"] for chunk in related_chunks[:6]],
                "prerequisites": _prerequisites_for(name, names),
                "common_confusions": _common_confusions_for(name, names),
            }
        )
    return concepts


def build_content_graph(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")

    objective = _clean_text(payload.get("learning_objective") or payload.get("objective"))
    if not objective:
        raise InputError("missing_learning_objective", "Track B requires a learning objective.")

    sources = _normalize_content_set(payload)
    _validate_objective_source_alignment(objective, sources)
    chunks = _build_chunks(sources, objective)
    concepts = _build_concepts(objective, chunks)
    concept_names = [concept["name"] for concept in concepts]

    for chunk in chunks:
        chunk["concepts"] = _chunk_concepts(chunk, concept_names)
        chunk["bloom_level"] = _infer_bloom_level(chunk["text"])
        chunk["difficulty"] = _difficulty(chunk["text"], chunk["bloom_level"])
        chunk["preview"] = chunk["text"][:220] + ("..." if len(chunk["text"]) > 220 else "")
        chunk.pop("terms", None)

    edges = []
    for concept in concepts:
        for prereq in concept["prerequisites"]:
            edges.append(
                {
                    "from": prereq,
                    "to": concept["name"],
                    "type": "prerequisite",
                    "reason": f"{prereq} is useful before applying {concept['name']}.",
                }
            )

    warnings = [
        {
            "code": "url_metadata_only",
            "message": f"{source['title']} has URL metadata only; enable URL fetching, use Gemini video analysis, upload the PDF, or paste notes/transcript for factual grounding.",
        }
        for source in sources
        if source.get("warning") == "url_metadata_only"
    ]
    warnings.extend(
        {
            "code": "url_type_not_text_fetched",
            "message": f"{source['title']} could not be converted into text by URL fetch; use Gemini video analysis or paste/upload source text.",
        }
        for source in sources
        if source.get("warning") == "url_type_not_text_fetched"
    )
    warnings.extend(
        {
            "code": "url_fetch_failed",
            "message": f"{source['title']} could not be fetched: {source['fetch_error']}",
        }
        for source in sources
        if source.get("fetch_error")
    )
    warnings.extend(
        {
            "code": "document_parse_warning",
            "message": f"{source['title']} was only partially parsed: {source['parse_warning']}",
        }
        for source in sources
        if source.get("parse_warning")
    )
    grounded_chunks = [chunk for chunk in chunks if chunk.get("content_is_grounded", True)]
    grounded_token_count = sum(len(_tokens(chunk.get("text", ""))) for chunk in grounded_chunks)
    if grounded_chunks and grounded_token_count < 18:
        warnings.append(
            {
                "code": "thin_content_set",
                "message": "Grounded source text is too thin for reliable curation; add notes, transcript, or document content.",
            }
        )
    if grounded_chunks and not any(chunk.get("objective_overlap") for chunk in grounded_chunks):
        warnings.append(
            {
                "code": "low_objective_source_overlap",
                "message": "Grounded sources have little lexical overlap with the learning objective; review source relevance before trusting generated cases.",
            }
        )

    return {
        "learning_objective": objective,
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "sources": sources,
        "chunks": chunks,
        "concepts": concepts,
        "edges": edges,
        "warnings": warnings,
        "rag_index": {
            "method": "local_lexical_tfidf",
            "chunk_count": len(chunks),
            "embedding_store": "optional_runtime_openai_embeddings_and_pinecone",
            "production_upgrade": "supply OpenAI embedding key plus Pinecone API key and index host to enable vector retrieval",
        },
    }


def retrieve_chunks(
    graph: dict[str, Any],
    query: str,
    limit: int = 6,
    focus_terms: list[str] | None = None,
    retrieval_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieval_config = retrieval_config if isinstance(retrieval_config, dict) else {}
    semantic_reason = ""
    if retrieval_config.get("use_vector_rag"):
        semantic = _retrieve_chunks_semantic(graph, query, limit, focus_terms, retrieval_config)
        if semantic.get("selected_chunks"):
            return semantic
        semantic_reason = str(semantic.get("fallback_reason") or "Vector retrieval returned no chunks.")

    chunks = graph.get("chunks", [])
    if not chunks:
        return {"query": query, "strategy": "local_lexical_tfidf", "selected_chunks": [], "trace": []}

    query_terms = set(_tokens(query))
    focus = set(_tokens(" ".join(focus_terms or [])))
    all_docs = [set(_tokens(chunk.get("text", ""))) for chunk in chunks]
    doc_count = max(1, len(all_docs))
    document_frequency: Counter[str] = Counter()
    for terms in all_docs:
        for term in terms:
            document_frequency[term] += 1

    scored = []
    for chunk, terms in zip(chunks, all_docs):
        overlap = query_terms & terms
        focus_overlap = focus & terms
        score = 0.0
        for term in overlap:
            score += 1.0 + math.log((doc_count + 1) / (1 + document_frequency[term]))
        score += len(focus_overlap) * 1.8
        score += len(chunk.get("objective_overlap", [])) * 0.4
        score += max(0, 0.8 - float(chunk.get("difficulty", 0.5))) * 0.15
        if chunk.get("start") and chunk.get("end"):
            score += 0.25
        if not chunk.get("content_is_grounded", True):
            score -= 2.0
        scored.append((score, chunk, sorted(overlap | focus_overlap)))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    trace = []
    for score, chunk, matched_terms in scored[: max(1, limit)]:
        selected_chunk = {
            "id": chunk["id"],
            "source_id": chunk["source_id"],
            "source_title": chunk["source_title"],
            "source_type": chunk["source_type"],
            "source_state": chunk.get("source_state", "usable_text"),
            "content_is_grounded": bool(chunk.get("content_is_grounded", True)),
            "url": chunk.get("url", ""),
            "start": chunk.get("start", ""),
            "end": chunk.get("end", ""),
            "concepts": chunk.get("concepts", []),
            "bloom_level": chunk.get("bloom_level", "understand"),
            "difficulty": chunk.get("difficulty", 0.5),
            "score": round(score, 3),
            "matched_terms": matched_terms[:8],
            "text": chunk["text"],
            "selected_because": _selection_reason(chunk, matched_terms, score),
        }
        selected.append(selected_chunk)
        trace.append(
            {
                "chunk_id": chunk["id"],
                "score": round(score, 3),
                "matched_terms": matched_terms[:8],
                "source": chunk["source_title"],
            }
        )
    return {
        "query": query,
        "strategy": "local_lexical_tfidf",
        "selected_chunks": selected,
        "trace": trace,
        "fallback_used": bool(retrieval_config.get("use_vector_rag")),
        "fallback_reason": (
            f"Vector RAG was requested but unavailable; lexical retrieval was used. {semantic_reason}".strip()
            if retrieval_config.get("use_vector_rag")
            else ""
        ),
    }


def _retrieve_chunks_semantic(
    graph: dict[str, Any],
    query: str,
    limit: int,
    focus_terms: list[str] | None,
    retrieval_config: dict[str, Any],
) -> dict[str, Any]:
    chunks = graph.get("chunks", [])
    if not chunks:
        return {"query": query, "strategy": "semantic", "selected_chunks": [], "trace": [], "fallback_reason": "No chunks."}

    api_key = str(
        retrieval_config.get("openai_api_key")
        or retrieval_config.get("api_key")
        or os.getenv("OPENAI_API_KEY", "")
    ).strip()
    if not api_key:
        return {
            "query": query,
            "strategy": "semantic_openai_embeddings",
            "selected_chunks": [],
            "trace": [],
            "fallback_reason": "OpenAI API key is required for embedding RAG.",
        }

    embedding_model = str(
        retrieval_config.get("embedding_model")
        or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    ).strip()
    query_text = " ".join([query] + list(focus_terms or [])).strip()
    try:
        embeddings = embed_texts(
            [query_text] + [chunk["text"] for chunk in chunks],
            api_key=api_key,
            model=embedding_model,
        )
    except RagError as exc:
        return {
            "query": query,
            "strategy": "semantic_openai_embeddings",
            "selected_chunks": [],
            "trace": [],
            "fallback_reason": str(exc),
        }

    query_vector = embeddings[0]
    chunk_vectors = embeddings[1:]
    pinecone_key = str(retrieval_config.get("pinecone_api_key") or os.getenv("PINECONE_API_KEY", "")).strip()
    pinecone_host = str(retrieval_config.get("pinecone_index_host") or os.getenv("PINECONE_INDEX_HOST", "")).strip()
    namespace = str(retrieval_config.get("pinecone_namespace") or os.getenv("PINECONE_NAMESPACE", "proofloop-demo")).strip()

    if pinecone_key and pinecone_host:
        try:
            pinecone_result = pinecone_upsert_and_query(
                chunks=chunks,
                vectors=chunk_vectors,
                query_vector=query_vector,
                api_key=pinecone_key,
                index_host=pinecone_host,
                namespace=namespace,
                top_k=limit,
            )
            selected = [
                _selected_chunk_from_semantic(match["chunk"], match["score"], "pinecone_vector_search")
                for match in pinecone_result.get("matches", [])
            ]
            return {
                "query": query,
                "strategy": "pinecone_vector_rag",
                "embedding_model": embedding_model,
                "namespace": namespace,
                "selected_chunks": selected,
                "trace": [
                    {"chunk_id": chunk["id"], "score": chunk["score"], "source": chunk["source_title"]}
                    for chunk in selected
                ],
                "fallback_used": False,
                "fallback_reason": "",
            }
        except RagError as exc:
            pinecone_error = str(exc)
    else:
        pinecone_error = "Pinecone API key/index host not supplied; used in-memory vector retrieval."

    scored = [
        (cosine_similarity(query_vector, vector), chunk)
        for chunk, vector in zip(chunks, chunk_vectors)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [
        _selected_chunk_from_semantic(chunk, score, "local_in_memory_vector_search")
        for score, chunk in scored[: max(1, limit)]
    ]
    return {
        "query": query,
        "strategy": "local_vector_rag",
        "embedding_model": embedding_model,
        "selected_chunks": selected,
        "trace": [
            {"chunk_id": chunk["id"], "score": chunk["score"], "source": chunk["source_title"]}
            for chunk in selected
        ],
        "fallback_used": bool(pinecone_key or pinecone_host),
        "fallback_reason": pinecone_error,
    }


def _selected_chunk_from_semantic(chunk: dict[str, Any], score: float, strategy: str) -> dict[str, Any]:
    chunk_id = str(chunk.get("id") or chunk.get("source_id") or "pinecone-match")
    return {
        "id": chunk_id,
        "source_id": chunk.get("source_id", ""),
        "source_title": chunk.get("source_title", "Retrieved source"),
        "source_type": chunk.get("source_type", "source"),
        "source_state": chunk.get("source_state", "usable_text"),
        "content_is_grounded": bool(chunk.get("content_is_grounded", True)),
        "url": chunk.get("url", ""),
        "start": chunk.get("start", ""),
        "end": chunk.get("end", ""),
        "concepts": chunk.get("concepts", []),
        "bloom_level": chunk.get("bloom_level", "understand"),
        "difficulty": chunk.get("difficulty", 0.5),
        "score": round(float(score), 4),
        "matched_terms": [],
        "text": chunk.get("text", ""),
        "selected_because": f"Retrieved by {strategy} for semantic relevance to the objective and learner need.",
    }


def _selection_reason(chunk: dict[str, Any], matched_terms: list[str], score: float) -> str:
    if not chunk.get("content_is_grounded", True):
        return (
            "Metadata-only source included because page text was not fetched or parsed; "
            "do not use it as factual grounding until a transcript, notes, or parsed document is supplied."
        )
    concept_text = ", ".join(chunk.get("concepts", [])[:3]) or "the learning objective"
    match_text = ", ".join(matched_terms[:4]) if matched_terms else "source coverage"
    locator = ""
    if chunk.get("start") and chunk.get("end"):
        locator = f" at {chunk['start']}-{chunk['end']}"
    if score <= 0:
        return f"Included as baseline context for {concept_text}{locator}."
    return f"Retrieved for {concept_text}{locator}; matched {match_text}."


def source_coverage(graph: dict[str, Any]) -> list[dict[str, Any]]:
    concept_by_source: dict[str, set[str]] = defaultdict(set)
    for chunk in graph.get("chunks", []):
        for concept in chunk.get("concepts", []):
            concept_by_source[chunk["source_id"]].add(concept)
    rows = []
    for source in graph.get("sources", []):
        concepts = sorted(concept_by_source.get(source["id"], set()))
        rows.append(
            {
                "source_id": source["id"],
                "title": source["title"],
                "type": source["type"],
                "concepts": concepts,
                "coverage_count": len(concepts),
                "source_state": source.get("source_state", "usable_text"),
                "content_is_grounded": bool(source.get("content_is_grounded", True)),
                "warning": source.get("parse_warning") or source.get("warning", ""),
            }
        )
    rows.sort(key=lambda row: row["coverage_count"], reverse=True)
    return rows
