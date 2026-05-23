# Submission Proof Checklist

This document maps the Track B assignment requirements to the implementation, tests, and supporting references.

## Assignment Contract

Track B asks for:

```text
B) Content Curator + Dynamic Case Builder

Input:
- learning objective
- small content set: URLs, docs, notes

Generates:
- curated learning bundle
- dynamic challenge/case
- why inputs were chosen
- required output
```

## Requirement Coverage

| Requirement | Implementation proof | Status |
|---|---|---|
| Accept learning objective | `build_track_b_plan` in `src/proofmark/roadmap.py` validates `learning_objective`. | Done |
| Accept small content set | `build_content_graph` in `src/proofmark/content_graph.py` accepts `content_set`, `content`, or `resources`. | Done |
| Accept URLs | UI has `Source URLs`; backend preserves URL metadata in content source objects. | Done |
| Accept docs/notes | UI has `Docs / notes excerpts`; backend chunks pasted text. | Done |
| Accept uploaded files | UI accepts `.pdf`, `.md`, `.markdown`, `.txt`, `.tex`, and `.latex`; `src/proofmark/documents.py` parses request-time data URLs into text sources. | Done |
| Preserve/render math | Markdown/TeX/PDF extraction preserves LaTeX-style formulas; UI renders result panels with KaTeX auto-render for `$...$`, `$$...$$`, `\\(...\\)`, and `\\[...\\]`. | Done |
| Accept transcripts/video segments | UI has optional transcript fallback; backend supports timestamped `segments` when supplied, while Gemini can infer useful timestamps from supported video inputs. | Done |
| AI source/video analysis | `src/proofmark/source_analysis.py` optionally calls Gemini with a compact source manifest, RAG chunks, and public video URL parts; Gemini extracts only summary, concepts, facts, formulas, timestamps, mistakes, and source notes. | Done |
| Research-backed video learning plan | `src/proofmark/source_analysis.py` locally converts compact source extraction into `video_learning_plan` with pre-watch orientation, guided watch segments, pause/explain/check prompts, and after-watch tasks. | Done |
| Learner-facing video study page | `src/proofmark/source_analysis.py` locally normalizes compact extraction into `student_video_lesson`; `generation.py` can add an AI-generated `visual_artifact`; the split browser UI renders summary, facts, formula cards with KaTeX, shortcuts, useful timestamps, mind map, SVG-style generated diagram, draw-check evidence field, common mistakes, audio overview option, and one check. | Done |
| Simple voice overview | `src/proofmark/voice.py` exposes `/api/track-b/voice-summary` for backend-configured ElevenLabs TTS. The setup endpoints remain internal utilities, while the learner-facing UI no longer asks for provider keys, voice IDs, or model IDs. | Done |
| Learner-facing staged lesson graph | `src/proofmark/lesson_graph.py` returns guided source media lesson, notes, checkpoint, visual repair, mixed practice, final case, and revision loop. | Done |
| Curated learning bundle | `src/proofmark/curator.py` returns source rationale, concept map, notes, worked example, checkpoints, and evidence sequence. | Done |
| Dynamic challenge/case | `src/proofmark/case_builder.py` returns scenario, constraints, required output, rubric, and profile variants. | Done |
| Why inputs were chosen | `selected_sources` and `rag_context.trace` explain selected source/chunk rationale. | Done |
| Required learner output | `dynamic_case.required_output` defines response components and minimum evidence. | Done |
| Optional learner profile | `src/proofmark/learner_model.py` uses optional `learner_events`; cold start works without it. | Done |
| Personalized teaching methods | `case_builder.py` creates high-support, balanced, and advanced variants for notes, mind maps, source sections, hints, voice/roleplay, practice, and review. | Done |
| Learning and testing side by side | `curator.py` embeds visual, text, typed, quiz, voice/roleplay, hint, timing, and final-case evidence stages. | Done |
| RAG grounding | `content_graph.retrieve_chunks` routes retrieval through local lexical RAG by default, local embedding search when an OpenAI key is supplied, and Pinecone vector search when Pinecone key/index host are supplied. | Done |
| Embedding/Pinecone production path | Backend demo config accepts OpenAI embedding key, embedding model, Pinecone API key, index host, and namespace. `src/proofmark/rag.py` performs OpenAI embedding calls plus Pinecone `/vectors/upsert` and `/query`, then falls back to local vector or lexical retrieval if unavailable. | Wired |
| Live LLM generation | `src/proofmark/generation.py` optionally calls an OpenAI-compatible Responses endpoint when backend demo config enables it and supplies a key/model. | Done |
| Provider reliability | Full raw-context prompts are preserved. `src/proofmark/provider_runtime.py` adds retry/backoff and successful-response caching; `provider_notices` make 429/quota failures visible in the learner UI. | Done |
| No key leakage | `tests/test_track_b.py` checks runtime API keys are not echoed in responses. | Done |

## API Proof

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

Evidence sample:

```bash
curl http://127.0.0.1:8765/api/track-b/sample
```

Generate:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "learning_objective": "Understand electric potential.",
    "content_set": [
      {
        "type": "url",
        "title": "Example source",
        "url": "https://example.com/electrostatics",
        "text": "https://example.com/electrostatics"
      },
      {
        "type": "notes",
        "title": "Teacher notes",
        "text": "Electric potential is work done per unit charge. Electric field is a vector but potential is a scalar."
      }
    ]
  }'
```

Generate with optional vector RAG:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "learning_objective": "Understand electric potential.",
    "api_key": "runtime-openai-key",
    "pinecone_api_key": "runtime-pinecone-key",
    "pinecone_index_host": "your-index-host.svc.aped-4627-b74a.pinecone.io",
    "content_set": [{"type": "notes", "title": "Notes", "text": "Electric potential is work done per unit charge."}],
    "constraints": {
      "use_vector_rag": true,
      "embedding_model": "text-embedding-3-small",
      "pinecone_namespace": "proofloop-demo"
    }
  }'
```

Generate with optional Gemini source/video analysis:

```bash
curl -X POST http://127.0.0.1:8765/api/track-b/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "gemini_api_key": "runtime-gemini-key",
    "learning_objective": "Understand electric potential.",
    "content_set": [
      {"type": "video", "title": "Video lesson", "url": "https://www.youtube.com/watch?v=sGb3VLDvNRU", "text": "Electrostatic potential video lesson."},
      {"type": "notes", "title": "Notes", "text": "Electric potential is work done per unit charge."}
    ],
    "constraints": {
      "analyze_sources_with_gemini": true,
      "gemini_model": "<your-gemini-model-id>"
    }
  }'
```

For the product demo, provider keys are backend operator configuration only. They are used for Gemini/OpenAI/Pinecone/ElevenLabs calls and are not returned in `rag_pipeline`, `ai_source_analysis`, `lesson_graph`, `llm_generation_packet`, `model_generation`, or voice responses.

Expected proof fields in response:

- `contract.required_input`
- `content_graph.sources`
- `content_graph.chunks`
- `curated_learning_bundle.selected_sources`
- `curated_learning_bundle.concept_map`
- `ai_source_analysis`
- `ai_source_analysis.video_learning_plan`
- `ai_source_analysis.student_video_lesson`
- `lesson_graph.pages`
- `dynamic_case.required_output`
- `dynamic_case.rubric`
- `dynamic_case.personalized_variants`
- `rag_pipeline.retrieved_chunks`
- `llm_generation_packet`
- `model_generation`

## Test Proof

Run:

```bash
node --check web/static/app.js
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 eval/run_eval.py
PYTHONPATH=src python3 -m compileall -q src tests
```

Current expected results:

- JS syntax passes.
- Unit tests pass.
- Golden eval passes.
- Python compile passes.

## What We Should Not Overclaim

Current honest claims:

- The app has a working local Track B prototype.
- It accepts URLs, uploaded PDFs, Markdown, TeX, docs/notes, and transcript segments.
- It performs local RAG over supplied/extracted text.
- It can perform runtime vector RAG with OpenAI embeddings and Pinecone when keys and index host are supplied.
- It can perform runtime Gemini source/video analysis when a Gemini/Google key is supplied.
- It builds a grounded LLM packet.
- It can call a model at runtime if a key is supplied.
- It does not persist API keys.

Do not claim yet:

- URL pages are always crawled successfully.
- Pinecone vector retrieval is the default path.
- Hosted vector RAG was live-tested unless OpenAI/Pinecone keys and a compatible index were actually used during the demo.
- Live Gemini video analysis was used unless a Gemini/Google key was actually supplied and the call completed.
- Live model output was used unless the runtime model call was actually executed.

## Research And Technical References

Instructional design:

- Merrill, "First Principles of Instruction" - https://mdavidmerrill.files.wordpress.com/2019/04/firstprinciplesbymerrill.pdf
- van Merrienboer et al., "Four-Component Instructional Design" - https://www.4cid.org/wp-content/uploads/2021/04/vanmerrienboer-clark-croock-2002.pdf
- Kalyuga, "Expertise Reversal Effect and Its Implications for Learner-Tailored Instruction" - https://link.springer.com/article/10.1007/s10648-007-9054-3
- Chi and Wylie, "The ICAP Framework" - https://www.tandfonline.com/doi/full/10.1080/00461520.2014.965823
- Chi et al., "Eliciting self-explanations improves understanding" - https://asu.elsevierpure.com/en/publications/eliciting-self-explanations-improves-understanding/
- Mayer and Pilegard, multimedia learning principles - https://doi.org/10.1017/CBO9781139547369.016
- Ibrahim et al., segmenting/signaling/weeding in educational video - https://doi.org/10.1080/17439884.2011.585993
- Brame, "Effective Educational Videos" - https://academic.wlu.edu/wp-content/uploads/2020/04/Brame-2016-effective-videos.pdf
- Guo, Kim, and Rubin, "How Video Production Affects Student Engagement" - https://doi.org/10.1145/2556325.2566239
- Szpunar, Khan, and Schacter, interpolated tests in online lectures - https://scholar.harvard.edu/files/novallkhan/files/pnas_szpunar_khan_schacter.pdf
- Fiorella and Mayer, generative learning strategies - https://bootcampmilitaryfitnessinstitute.com/wp-content/uploads/2016/01/eight-ways-to-promote-generative-learning-fiorella-mayer-2015.pdf

Learner modeling:

- Pashler et al., "Learning Styles: Concepts and Evidence" - https://journals.sagepub.com/doi/full/10.1111/j.1539-6053.2009.01038.x
- CHC cognitive abilities overview - https://www.mdpi.com/2079-3200/11/2/32
- pyBKT - https://arxiv.org/abs/2105.00385
- NeuralCDM - https://ojs.aaai.org/index.php/AAAI/article/view/6080
- Contextual bandits for adaptive curriculum - https://arxiv.org/abs/2207.14003

Forgetting and review:

- Ebbinghaus, "Memory" - https://en.wikisource.org/wiki/Memory:_A_Contribution_to_Experimental_Psychology
- Murre and Dros, "Replication and Analysis of Ebbinghaus' Forgetting Curve" - https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644
- Settles and Meeder, "A Trainable Spaced Repetition Model for Language Learning" - https://aclanthology.org/P16-1174.pdf
- Adaptive Forgetting Curves - https://arxiv.org/abs/2004.11327

RAG and vector infrastructure:

- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" - https://arxiv.org/abs/2005.11401
- OpenAI embeddings guide - https://platform.openai.com/docs/guides/embeddings
- OpenAI `text-embedding-3-small` model - https://platform.openai.com/docs/models/text-embedding-3-small
- Pinecone upsert vectors API - https://docs.pinecone.io/reference/api/2026-04/data-plane/upsert
- Pinecone query/search with vector API - https://docs.pinecone.io/reference/api/2026-04/data-plane/query
- Gemini video understanding - https://ai.google.dev/gemini-api/docs/video-understanding
- Gemini structured output - https://ai.google.dev/gemini-api/docs/structured-output
