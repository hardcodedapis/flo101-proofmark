# ProofLoop Track B

ProofLoop is a Track B implementation for the flo101 Applied AI assessment:

**Content Curator + Dynamic Case Builder**

Required input:

```text
learning objective + small content set
URLs, PDFs, Markdown, TeX, docs, notes, transcripts, or pasted source text
```

Generated output:

```text
curated learning bundle
dynamic challenge/case
why each input/source was chosen
required learner output
rubric and evaluation criteria
personalized teaching variants after learner evidence exists
```

The system does not require a learner profile at the beginning. Cold start is content-driven and pedagogy-driven. After the learner interacts with the first bundle, embedded visual, quiz, typed, voice/roleplay, hint, timing, confidence, and memory signals feed the learner engine. The next bundle is then personalized by sending compressed engine analytics plus RAG-grounded source chunks to the LLM generation layer.

## Product Wedge

```text
objective + content set
  -> RAG + concept graph
  -> Gemini source/video analysis when configured
  -> staged lesson graph
  -> cold-start learning bundle
  -> dynamic case + required output
  -> embedded evidence capture during learning
  -> learner model update
  -> personalized next notes, mind map, hints, roleplay, quiz, and review plan
```

This keeps the assignment's Track B contract intact while adding the adaptive engine as the differentiator.

## What It Does

- Accepts a learning objective and small content set.
- Parses URLs, pasted notes, transcript segments, Markdown/text/TeX files, and text-based PDFs into source states, source chunks, concepts, prerequisites, difficulty, Bloom level, and source coverage.
- Treats URL-only inputs honestly: a URL is metadata until it is fetched, analyzed by Gemini, or paired with pasted/uploaded text. Metadata-only sources are flagged so the system does not silently pretend a raw URL is grounded content. URL fetching only permits public `http`/`https` hosts, blocks local/private/link-local targets, and validates redirect targets before following them.
- Preserves LaTeX-style math delimiters for retrieval and renders them in the UI with KaTeX.
- Uses local lexical RAG by default, and upgrades to runtime OpenAI embeddings plus Pinecone vector retrieval when keys/index host are configured.
- Can make an AI-first source/video extraction call through Gemini when a runtime Gemini/Google key is supplied. Public YouTube URLs are passed as Gemini video parts; optional transcripts, notes, PDFs, and RAG chunks are sent as compact text context. Gemini returns only source-backed summary, concepts, facts, formulas, timestamps, mistakes, and source notes; the local backend turns that into `student_video_lesson`, diagrams, checks, and adaptive flow.
- Generates a cold-start bundle with concept map, guided notes, worked example, checkpoint questions, and embedded evidence sequence.
- Generates a learner-facing lesson graph: guided source/video page, notes under media, checkpoint, visual repair, mixed practice, final dynamic case, and revision loop.
- Generates a dynamic case/challenge, required learner output, and rubric. Local fallback cases are domain-specific for Bayes/probability, ray optics, electrochemistry, and electric potential instead of generic "prove you can use X" templates.
- Shows how the same content changes for high-support, balanced, and advanced learner profiles.
- Supports optional learner telemetry/profile input. If missing, the first bundle collects the evidence needed to infer it. Embedded quiz, typed, and drawing checks POST raw learner events to `/api/track-b/adapt`; the backend scores them with `track-b-evidence-rubric-v1`, persists deduped session evidence, writes an audit record, and regenerates the learner model, roadmap, next mode, and revision timing.
- Builds a multidimensional learner model from correctness, reasoning, confidence, time, hint behavior, modality signals, voice signals, visual interaction, affective behavior, and memory state.
- Produces an LLM generation packet: learner state summary + retrieved source chunks + constraints + required output schema.
- Optionally calls an OpenAI-compatible Responses endpoint to generate the actual next learning assets, including a `student_study_pack`, renderable `visual_artifact`, draw-check prompt, and voice-over script. If disabled or unconfigured, the local deterministic fallback returns the same output shape. Full-context model calls are intentionally kept large; provider retry/backoff, response caching, and visible rate-limit notices handle the latency/quota tradeoff.
- Optionally calls ElevenLabs text-to-speech from backend demo configuration to turn the source-grounded voice-over script into a short spoken explanation. Full live voice conversation is intentionally left as future scope because it needs streaming speech recognition, interruption handling, and an agent session layer.
- Keeps the earlier proof evaluator, action router, forgetting scheduler, and PCM diagnostic as internal assessment/retest modules. The submitted product direction remains Track B.

## Runtime Paths

Core visible systems:

- source grounding through local RAG or Pinecone vector RAG when configured
- Gemini source/video analysis when backend demo config supplies a Gemini key and model id
- OpenAI-compatible generation when backend demo config supplies a provider key and model id
- ElevenLabs audio explanation when backend demo config supplies an ElevenLabs key; voice/model are selected from env or account defaults
- forgetting-curve review and retest planning after learner evidence

When keys or quota are missing, the app marks the path clearly and uses deterministic fallback only to keep the demo inspectable. The fallback is lower quality than live model generation and is not presented as equivalent.

## Runtime Safety

- Optional API token: set `PROOFMARK_API_TOKEN` and send `Authorization: Bearer <token>` or `X-Proofmark-Token`.
- Request cap: POST bodies above `1,000,000` bytes are rejected before read.
- Rate limit: `PROOFMARK_RATE_LIMIT_PER_MINUTE` and `PROOFMARK_RATE_LIMIT_WINDOW_SECONDS` control per-client/path throttling.
- Local state: adaptive sessions, learner events, and audit snapshots are stored in `.proofmark_state/proofmark.sqlite3` by default. Override the directory with `PROOFMARK_STATE_DIR`.
- Local demo providers: copy `.proofmark_demo.env.example` to `.proofmark_demo.env`. That file is gitignored and intentionally reserved for restricted/low-balance demo keys used to avoid typing provider setup into the end-user UI.
- Structured logs: JSON request logs go to stderr with request id, path, status, duration, byte count, and client. Payloads and secrets are not logged.

## Local Setup

ProofLoop has no runtime dependencies outside Python 3.10+.

```bash
cd /Users/himanshuyadav/developer/flo101-proofmark
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Run the web app:

```bash
PYTHONPATH=src python3 -m proofmark.app --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## API

Cold-start sample:

```bash
curl http://127.0.0.1:8765/api/track-b/sample-cold
```

Diagram-friendly physics seed:

```bash
curl http://127.0.0.1:8765/api/track-b/sample-physics
```

Chemistry seed:

```bash
curl http://127.0.0.1:8765/api/track-b/sample-chemistry
```

Sample with optional first-pass learner telemetry:

```bash
curl http://127.0.0.1:8765/api/track-b/sample
```

Generate a Track B plan:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "learning_objective": "Understand electric potential and solve CBSE/JEE-style electrostatics transfer problems.",
    "content_set": [
      {
        "type": "notes",
        "title": "Teacher notes",
        "text": "Electric potential is work done per unit charge. It is scalar; electric field is vector."
      }
    ]
  }'
```

For a local product demo, configure providers once:

```bash
cp .proofmark_demo.env.example .proofmark_demo.env
# Fill restricted/low-balance demo keys in .proofmark_demo.env.
# The learner-facing UI intentionally does not expose provider/API fields.
```

Then run the same product API without passing secrets in the request:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "learning_objective": "Understand electric potential.",
    "content_set": [{"type": "notes", "title": "Notes", "text": "Electric potential is work per unit charge."}]
  }'
```

Generate the simple voice overview from an already-produced script. The backend chooses the configured ElevenLabs voice/model:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/voice-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Electric potential means work done per unit positive test charge. First understand the meaning, then choose the formula, then check the trap."
  }'
```

Existing internal endpoints are still available:

- `GET /api/pcm/test`
- `POST /api/pcm/submit`
- `POST /api/evaluate`
- `POST /api/compare`

## Verification

Run the full smoke suite:

```bash
bash scripts/smoke.sh
```

Run unit tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run evaluation cases for both the internal proof evaluator and the Track B content-curation output:

```bash
PYTHONPATH=src python3 eval/run_eval.py
```

The Track B eval checks clean concept extraction, source-grounded dynamic cases, URL metadata honesty, held-out technical domains, source-claim grounding, vague source warnings, irrelevant source warnings, and the Linux-container regression where `Limit` must not become the primary concept.

## Repository Map

```text
src/proofmark/content_graph.py  Content normalization, concept graph, lexical/vector RAG routing
src/proofmark/rag.py            URL extraction, OpenAI embeddings, and Pinecone REST helpers
src/proofmark/source_analysis.py Optional Gemini source/video analysis plus local fallback
src/proofmark/lesson_graph.py   Learner-facing staged lesson graph
src/proofmark/curator.py        Cold-start bundle generation and embedded evidence sequence
src/proofmark/case_builder.py   Dynamic case, required output, rubric, profile variants
src/proofmark/learner_model.py  Rich telemetry schema and multidimensional learner profile
src/proofmark/evidence_grader.py Backend learner-evidence scoring rubric and misconception signals
src/proofmark/session_store.py  Local adaptive session persistence, dedupe, and audit trail
src/proofmark/generation.py     Optional model call and deterministic generation fallback
src/proofmark/runtime_config.py Gitignored local demo provider config loader
src/proofmark/roadmap.py        Track B orchestration, adaptive roadmap, LLM packet
src/proofmark/app.py            Dependency-free local web/API server

src/proofmark/actions.py        Internal next-learning-action router
src/proofmark/chemistry.py      Internal PCM diagnostic and adaptive retest prototype
src/proofmark/learning_loop.py  Internal forgetting-curve scheduler
src/proofmark/workflow.py       Internal artifact/proof evaluator
src/proofmark/compare.py        Internal before/after revision comparison

web/                            Browser demo for Track B; static JS/CSS split by API, rendering, adaptive events, layout, and components
tests/test_track_b.py           Track B content/RAG/learner-model tests
tests/test_chemistry.py         Existing PCM/retest tests
tests/test_workflow.py          Existing proof-evaluator tests
docs/                           Submission notes
```

## Research Basis

The architecture is grounded in:

- Merrill first principles and 4C/ID for cold-start instructional structure.
- Cognitive load theory and worked-example fading for novice support.
- ICAP and self-explanation for embedded evidence during learning.
- Multimedia/video learning research for segmenting, signaling, pre-training, weeding, interpolated retrieval checks, and generative after-watch tasks.
- Concept maps/graphic organizers for visual structure.
- Learning-styles caution: do not assign fixed visual/audio/text identities.
- CHC learner dimensions, knowledge tracing, cognitive diagnosis, and adaptive forgetting for learner state.
- Contextual bandits/intervention routing for selecting notes, visual cues, voice, roleplay, hints, quizzes, and transfer cases.
- RAG for grounding generated notes, cases, mind maps, and questions in the supplied content set.
- Gemini video understanding for public YouTube/source analysis when a runtime key is supplied.

See [research-basis.md](docs/research-basis.md), [research-scan.md](docs/research-scan.md), and [submission-proof.md](docs/submission-proof.md).

## Submission Notes

- [Architecture note](docs/architecture.md)
- [Product note](docs/product-note.md)
- [Evaluation note](docs/evaluation-note.md)
- [Model strategy](docs/model-strategy.md)
- [Research basis](docs/research-basis.md)
- [Research and open-source scan](docs/research-scan.md)
- [Submission proof checklist](docs/submission-proof.md)
- [AI usage disclosure](docs/ai-usage-disclosure.md)
- [Demo script](docs/demo-script.md)
