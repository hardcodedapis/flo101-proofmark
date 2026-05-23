# Evaluation Note

## Evaluation Method

ProofLoop includes a golden-case evaluation harness in `eval/run_eval.py`.

It now tests two layers:

1. Internal proof-evaluator regression cases.
2. Track B content-curation cases that directly match the submitted assignment.

The internal cases test three sample artifacts:

- strong product brief
- weak vague artifact
- code artifact

Each case defines expected score bounds, confidence expectations, and a required gap fragment. This is intentionally simple but useful: it catches obvious regressions in scoring, confidence, and gap generation.

Run:

```bash
PYTHONPATH=src python3 eval/run_eval.py
```

Current output:

```text
Legacy proof-evaluator golden evaluation
- strong product brief: score=87, confidence=medium
- weak vague artifact: score=38, confidence=low
- code artifact: score=65, confidence=medium

Track B content-curation evaluation
- bayes medical test: score=100 (concepts 5/5; case fragments 3/3; no bad concepts)
- convex lens ray optics: score=100 (concepts 5/5; case fragments 3/3; no bad concepts)
- galvanic cell nernst: score=100 (concepts 5/5; case fragments 3/3; no bad concepts)
- url metadata honesty: score=100 (warning ok; source state ok; ungrounded flag ok)
- unseen technical domain transformer attention: score=100
- adversarial technical domain linux containers: score=100
- heldout payments idempotency keys: score>=80
- adversarial vague source warning: score>=75
- adversarial irrelevant source warning: score>=75

All golden checks passed.
```

## Unit Tests

Unit tests cover:

- Track B content graph builds chunks and concepts from the required input contract.
- URL-only inputs are marked metadata-only and are not silently treated as factual grounding.
- URL fetching rejects local/private/link-local hosts before `urlopen`, reducing SSRF risk for hosted use.
- URL fetching validates redirect targets before following redirects.
- Bayes theorem extraction avoids bad phrase concepts and keeps base rate, sensitivity, specificity, and posterior probability separate.
- ray optics and electrochemistry seeds produce domain-specific dynamic cases.
- uploaded Markdown, TeX, and text-based PDF files are parsed into usable source chunks.
- LaTeX-style math survives document parsing for downstream rendering.
- local RAG retrieves relevant source chunks and returns retrieval trace.
- vector RAG requests fall back cleanly when an embedding key is missing.
- embedding-backed retrieval uses local vector search when an OpenAI key is supplied and Pinecone is not configured.
- runtime OpenAI/Pinecone keys are not echoed in output payloads.
- cold-start Track B plan does not require learner profile data.
- optional learner telemetry changes the plan into personalized mode.
- live learner events can be posted through the adaptive path, scored by the backend rubric, persisted into local session state, deduped, audited, and used to regenerate the next plan.
- optional API token auth, request-size caps, rate-limit helpers, and structured log paths are test-covered.
- learner model tracks multidimensional signals such as typed explanation, hint independence, concept mastery, and misconceptions.
- model generation returns either provider-generated assets or deterministic fallback with the same output shape.
- strong artifact scores above weak artifact
- evidence map exists for each rubric dimension
- empty artifact rejection
- unsupported artifact type rejection
- oversized artifact rejection before provider call
- custom rubric dimension preservation
- malformed provider shape repair
- missing API key provider fallback
- revision comparison detects proof improvement
- identical revision comparison rejection
- skill ledger emits standards-shaped proof exports
- personalized review schedule changes with prior mastery
- vague or irrelevant grounded content emits source-quality warnings.
- held-out/adversarial Track B fixtures cover transformer attention, Linux containers, payment idempotency, thin notes, and irrelevant notes.

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Output Quality Checks

For Track B generation, ProofLoop checks:

- learning objective exists.
- content set exists and has usable text/transcript/document content or explicit metadata-only warnings.
- uploaded document payloads decode into readable text or emit a parse warning.
- source chunks are created with `content_is_grounded` state.
- concept graph is created with quality gates for bad phrase concepts.
- RAG retrieval returns grounded chunks.
- RAG retrieval reports which mode ran: lexical, local vector, or Pinecone vector.
- RAG retrieval records fallback status and reason.
- cold-start bundle includes source rationale, notes, concept map, worked example, and embedded evidence sequence.
- dynamic case includes required output, rubric, source rationale, and domain-specific challenge shape.
- learner evidence is optional.
- optional learner evidence updates anchor mix, weak signals, misconceptions, and next methods.
- LLM generation packet includes learner-state summary plus retrieved source chunks.

For each internal proof evaluation, ProofLoop checks:

- input was validated
- rubric dimensions were scored on a 1-5 scale
- weighted score was normalized to 0-100
- next step was selected from the weakest rubric dimension
- proof map contains a reviewer verification question for each dimension
- skill ledger contains a stable proof id, mastery update, and audit hash
- judge trace records strategy, candidate quality, cache keys, and fallback reason
- learning loop returns retention risk, next review timing, and an adaptive revision task
- warnings were attached when confidence is lower

For provider-generated output, `workflow.py` repairs the response back to the expected rubric dimensions and clamps scores to 1-5.

## Research-Informed Quality Controls

ProofMark uses research-backed evaluation patterns:

- G-Eval-style structured form filling: each dimension has score, evidence, feedback, and risk.
- Prometheus-style rubric conditioning: default and custom rubrics are explicit inputs.
- MT-Bench/Chatbot Arena bias mitigation: prompts tell the judge not to reward verbosity, polish, or confidence without evidence.
- Formative feedback: output includes feed-up, feedback, and feed-forward fields.

## Failure Modes

Empty artifact

Handled by returning `empty_artifact` before evaluation.

Unsupported artifact type

Handled by returning `unsupported_artifact_type` with valid options.

Oversized artifact

Artifacts above the hard character limit are rejected before any provider call. This prevents cost spikes and slow requests.

Long artifact

Artifacts above the evaluation limit are truncated with a warning. This keeps latency predictable.

Short artifact

Short artifacts are evaluated but marked lower confidence.

Identical revision comparison

Before/after comparison rejects identical artifacts because a no-op revision should not be counted as proof improvement.

Provider unavailable

OpenAI-compatible calls are the preferred path, but they require configuration and network access. If the provider fails, ProofMark falls back to local deterministic evaluation and records a warning.

Malformed provider output

Provider responses are repaired against the rubric. If repair is not possible, the deterministic baseline remains available.

## Known Limitations

- The local evaluator is heuristic and can miss nuance.
- It does not deeply parse code semantics.
- It does not compare submissions across multiple revisions.
- It compares one before/after revision pair, but does not yet persist a longitudinal history.
- It does not learn from reviewer corrections yet.
- It does not persist results or rubrics.

## Next Evaluation Improvements

The next version should add:

- reviewer calibration set
- pairwise comparison of before/after revisions
- rubric agreement checks against human reviewer labels
- score drift monitoring by provider/model version
- per-dimension precision/recall on known gap labels
- live multi-provider ensemble integration with quorum and circuit breakers
- learned forgetting-curve parameters from real learner histories
