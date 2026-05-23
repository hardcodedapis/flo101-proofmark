# Architecture Note

## Goal

ProofLoop implements Track B: **Content Curator + Dynamic Case Builder**.

The required assignment input is:

```text
learning objective + small content set
```

The required output is:

```text
curated learning bundle
dynamic challenge/case
why inputs were chosen
required learner output
```

ProofLoop adds an adaptive layer: if learner evidence is provided, the system personalizes the bundle and next plan. If no learner evidence exists, the first bundle collects it through embedded checks.

## System Flow

```text
1. Assignment intake
   learning objective + URLs/PDFs/Markdown/TeX/docs/notes/transcripts

2. Content graph + RAG
   chunks -> concepts -> prerequisites -> selected source chunks

3. Optional AI source/video analysis
   Gemini can analyze public YouTube URLs plus source manifest/RAG chunks

4. Staged lesson graph
   guided media lesson -> notes -> checkpoint -> visual repair -> practice -> final case -> revision

5. Cold-start bundle
   concept map -> guided notes -> worked example -> embedded checks

6. Dynamic case
   challenge -> required learner output -> rubric

7. Evidence capture during learning
   visual, quiz, typed, voice/roleplay, hints, timing, confidence, memory

8. Learner model
   concept mastery, skill dimensions, misconceptions, intervention response

9. Session state and audit trail
   deduped server-scored events -> persisted local session -> versioned audit record

10. LLM generation packet
   learner state summary + retrieved source chunks + mode constraints

11. Model generation
   optional OpenAI-compatible call, deterministic fallback when disabled

12. Personalized next plan
   notes, mind map, video/source sections, roleplay, hints, tests, review schedule
```

## Main Components

`content_graph.py`

Normalizes the content set, chunks parsed documents/notes/transcripts, extracts candidate concepts, estimates Bloom level and difficulty, builds prerequisite/confusion edges, and routes retrieval. Lexical RAG is the dependency-free default. When runtime OpenAI and Pinecone settings are supplied, it uses embeddings and Pinecone vector search through `rag.py`; if that path fails, it falls back to local vector or lexical retrieval.

`documents.py`

Parses request-time uploads into text sources. It supports Markdown/text/TeX files directly and best-effort text extraction from text-based PDFs. It preserves LaTeX-style math delimiters so symbols/formulas can be used by retrieval and rendered by KaTeX in the UI.

`rag.py`

Owns external retrieval integration: optional URL extraction, OpenAI embeddings, cosine similarity fallback, and Pinecone vector upsert/query. In the product demo, provider keys are backend operator config from `.proofmark_demo.env`; the learner UI does not expose provider setup, and keys are never returned in the response.

`curator.py`

Builds the cold-start learning bundle:

- source rationale
- concept map
- guided notes
- worked example
- checkpoint questions
- embedded evidence sequence

Cold start is not fake personalization. It uses instructional design defaults and captures learner data while teaching.

`source_analysis.py`

Owns the first AI source-analysis boundary. When `analyze_sources_with_gemini` is true and a runtime Gemini/Google API key is supplied, it calls Gemini with a compact source manifest, selected RAG chunks, and public video URL parts where available. Gemini returns only source-backed summary, key concepts, facts, formulas, useful timestamps, mistakes, and source notes. The local planner then normalizes that compact extraction into source insights, video timeline, visual cues, page sequence, checkpoint questions, a research-backed `video_learning_plan`, and a learner-facing `student_video_lesson`. If no key is supplied or the provider fails, the deterministic local planner returns the same final structure.

`lesson_graph.py`

Turns source analysis, the curated bundle, the dynamic case, learner profile, roadmap, and model-generation output into the learner-facing product flow:

- source/video breakdown with extracted summary, formula cards, diagrams, mind map, useful timestamps, optional audio overview, and one check
- notes under media
- checkpoint
- visual repair
- mixed practice
- final dynamic case
- revision loop

`case_builder.py`

Generates the dynamic case/challenge, required learner output, rubric, source requirements, and profile variants. The same content can become different teaching experiences for high-support, balanced, and advanced learner states.

`learner_model.py`

Defines the rich telemetry schema and multidimensional learner model. It tracks:

- concept mastery
- visual/text/typed/spoken/symbolic/numeric performance
- reasoning depth
- confidence calibration
- hint dependence
- persistence/dropoff risk
- intervention effectiveness
- retention stability

The model avoids fixed learning-style labels. Modes are treated as interventions whose effectiveness must be measured.

`evidence_grader.py`

Converts browser evidence into server-owned learner signals. The browser can submit raw answer text, selected choices, selected drawing features, expected drawing features, prompt, mode, and concept context, but it cannot set trusted correctness or mastery. The backend assigns `score`, `correctness`, rubric evidence, misconception, next intervention hint, and memory fields using `track-b-evidence-rubric-v1`.

`session_store.py`

Persists adaptive state locally in SQLite at `.proofmark_state/proofmark.sqlite3` or inside `PROOFMARK_STATE_DIR`. It maintains separate `sessions`, `events`, and `audit_log` tables, deduplicates event ids, redacts runtime secrets, stores server-scored learner events, and appends a versioned audit record with event count, latest score, dominant anchor, next mode, target concepts, and duplicate event ids.

`roadmap.py`

Orchestrates Track B end-to-end. It returns the content graph, curated bundle, dynamic case, learner model, adaptive roadmap, RAG trace, and LLM generation packet. It also owns `adapt_track_b_plan`, which accepts a live learner event from the browser, grades it server-side, merges it with persisted session evidence, deduplicates repeated events, and regenerates the learner model, roadmap, review schedule, and next mode.

`generation.py`

Owns the model-call boundary. It takes the LLM generation packet and either:

- calls an OpenAI-compatible Responses API when backend demo config enables generation and supplies a runtime key plus model id, or
- returns a deterministic fallback with the same output shape.

The model is asked to generate concrete notes, a `student_study_pack`, renderable `visual_artifact`, mind-map changes, video/source sections, roleplay or voice task, hint ladder, micro-assessment, and evidence to collect next. It is constrained to use the retrieved chunks and learner-state summary.

`provider_runtime.py`

Adds provider retry/backoff and successful-response caching. The product intentionally keeps full raw-context prompts for quality; when providers return 429/quota errors, the app records `provider_notices` so the learner UI explains the fallback instead of silently pretending the model succeeded.

`voice.py`

Provides the simple audio layer. `/api/track-b/voice-summary` accepts a short source-grounded script and uses backend ElevenLabs demo config. If a voice/model is not explicitly set in env, the backend picks an available account voice and a supported TTS model. This is intentionally not a full conversation agent; live voice would add streaming speech recognition, interruption handling, and session memory.

`app.py`

Serves the local web app and API endpoints:

- `GET /api/track-b/sample-cold`
- `GET /api/track-b/sample-physics`
- `GET /api/track-b/sample-chemistry`
- `GET /api/track-b/sample`
- `POST /api/track-b/generate`
- `POST /api/track-b/adapt`
- `POST /api/track-b/elevenlabs-voices`
- `POST /api/track-b/elevenlabs-models`
- `POST /api/track-b/voice-summary`

Existing internal endpoints remain:

- `GET /api/pcm/test`
- `POST /api/pcm/submit`
- `POST /api/evaluate`
- `POST /api/compare`

## Data Contract

Input:

```json
{
  "learning_objective": "Understand electric potential and solve CBSE/JEE-style electrostatics transfer problems.",
  "content_set": [
    {
      "type": "video_transcript",
      "title": "Electrostatics lecture transcript",
      "segments": [
        {
          "start": "03:15",
          "end": "04:20",
          "text": "Electric potential is defined as work done per unit positive test charge..."
        }
      ]
    }
  ],
  "learner_events": []
}
```

`learner_events` is optional.

Output:

- `content_graph`: concepts, chunks, prerequisites, source coverage.
- `ai_source_analysis`: source/video insights, timeline, visual cues, page sequence, checkpoint questions, `video_learning_plan`, and `student_video_lesson`.
- `lesson_graph`: staged learner-facing pages.
- `curated_learning_bundle`: selected sources, concept map, notes, worked example, evidence sequence.
- `dynamic_case`: scenario, constraints, required output, rubric, profile variants.
- `learner_model`: cold-start prior or evidence-derived multidimensional profile.
- `adaptive_roadmap`: first-pass flow or personalized next plan.
- `rag_pipeline`: retrieved chunks and trace.
- `llm_generation_packet`: compact prompt payload for generating the next learning assets.
- `model_generation`: model-generated or fallback learning assets.

## Cold Start

When no learner profile exists, the system still produces a complete bundle. It uses:

- objective relevance
- source coverage
- concept prerequisites
- worked examples
- concept maps
- micro checks
- typed explanation
- voice/roleplay probe
- final dynamic case

The learner experiences learning, but the engine captures evidence at each stage.

## RAG Design

RAG is used for content grounding:

- selected source chunks
- notes
- mind maps
- video/source section recommendations
- dynamic cases
- hints
- quiz variants

RAG is not used as the learner model. Mastery, confidence, hint dependence, forgetting curve, and intervention effectiveness are computed by the engine.

Retrieval modes:

- `local_lexical_tfidf`: default, no external calls.
- `local_vector_rag`: OpenAI embeddings are available, but Pinecone is not configured or fails.
- `pinecone_vector_rag`: OpenAI embeddings plus Pinecone upsert/query are configured for the request.

Each response includes `rag_pipeline.type`, `vector_rag_requested`, `pinecone_enabled`, `fallback_used`, and `fallback_reason` so the demo can honestly show which path ran.

The model call comes after RAG and learner modeling:

```text
retrieved chunks + learner-state summary + mode constraints
  -> generation.py
  -> notes, mind map, voice/roleplay task, hints, micro-assessment, evidence plan
```

Gemini source/video analysis can run before the learner-facing graph is assembled:

```text
source manifest + retrieved chunks + public video URL parts
  -> source_analysis.py
  -> source insights, timeline, visual cues, page sequence, video_learning_plan, student_video_lesson
  -> lesson_graph.py
```

## Existing System Fit

Earlier evaluator/PCM work remains useful as internal infrastructure:

- `workflow.py`: artifact/written-output evaluator.
- `compare.py`: revision and progress comparison.
- `actions.py`: action router.
- `learning_loop.py`: forgetting-curve scheduler.
- `chemistry.py`: PCM diagnostic/retest prototype.

Track B now sits above these modules as the main product.

## Tradeoffs

The default path still avoids external dependencies, databases, queues, and hosted vector stores. This keeps the demo easy to run and test. The tradeoff is lower semantic recall than hosted vector retrieval and less rich video understanding than Gemini. The keyed Gemini, Pinecone, OpenAI, and ElevenLabs paths are core product paths when configured, but they add API cost, latency, provider limits, index-dimension compatibility requirements, and another failure mode. The product response records the chosen path and fallback reason so the system can be evaluated honestly.
