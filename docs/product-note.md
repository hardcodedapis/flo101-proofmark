# Product Note

## Product Framing

ProofLoop Track B is a **Content Curator + Dynamic Case Builder**.

It accepts the required assignment input:

```text
learning objective + small content set
```

Then it generates:

- a curated learning bundle
- source/segment rationale
- source/video analysis
- staged learner-facing lesson graph
- concept map
- guided notes
- worked example
- dynamic case/challenge
- required learner output
- rubric
- personalized teaching variants after evidence exists

## Key Product Idea

The first pass should not ask the learner to take a giant diagnostic before learning. It should teach and measure at the same time.

```text
source media -> notes below media -> checkpoint -> visual repair -> mixed practice -> final case -> revision loop
```

Each stage emits useful telemetry. That evidence updates the learner model, then the next bundle becomes personalized.

For video-heavy content, the first page is not just a player or a source trace. Gemini or the local planner turns the video/source set into a student-facing study page: short summary, key facts, things to remember, tips and tricks, timestamp guide, mind map, diagram prompt, common mistakes, and one tiny check.

## Cold Start

With no learner profile, ProofLoop uses instructional design defaults:

- Gemini analysis of public videos/source material when a key is supplied
- research-backed guided video learning plan for the first media page
- source relevance
- prerequisite structure
- concept map
- guided notes
- worked example
- checkpoint questions
- dynamic case

This is a general learning bundle, not generic filler. It is built to produce the evidence needed for personalization.

## Personalization

After first-pass evidence, the same content can produce different methods:

High-support learner:

- prerequisite repair
- short notes
- visual contrast
- worked examples
- scaffolded hints
- earlier review

Balanced learner:

- structured notes
- concept-map completion
- teach-back
- mixed practice
- moderate review spacing

Advanced learner:

- compressed notes
- transfer challenge
- ambiguous roleplay
- minimal hints
- delayed review unless transfer fails

## RAG And Model Role

Gemini analyzes source/video structure when configured. RAG grounds the content. The learner engine grounds the personalization.

```text
source manifest + video URLs + retrieved chunks
  -> source analysis
  -> guided video/source learning plan + student study page
  -> lesson graph
  -> learner evidence
  -> content chunks + learner-state summary
  -> LLM generation packet
  -> next notes, mind map, roleplay, hints, quiz, review plan
```

The LLM does not decide learner mastery from raw logs. The engine compresses telemetry into a state summary first. The model then generates the actual learning assets under constraints.

RAG has three runtime modes:

- local lexical retrieval for no-key demos
- local vector retrieval when OpenAI embeddings are available but Pinecone is not configured
- Pinecone vector retrieval when OpenAI embeddings, Pinecone API key, index host, and namespace are supplied

## Primary Metric

Primary metric: **personalized repair rate**.

Definition: percentage of weak concept/skill signals that improve after the generated next learning method.

Supporting metrics:

- bundle completion rate
- source-grounded answer rate
- hint dependence reduction
- confidence calibration improvement
- typed/voice explanation improvement
- transfer-case success rate
- retention on delayed review

## Runtime Boundary

The demo can run locally without hosted storage, but the intended product includes source grounding, model generation, voice explanation, and spaced review as first-class parts of the flow. Runtime keys decide which paths are live:

```text
objective + content set
  -> lexical/vector RAG
  -> Gemini/local source analysis
  -> staged lesson graph
  -> cold-start bundle
  -> dynamic case
  -> optional learner evidence
  -> personalized next plan
```

If Gemini, OpenAI, Pinecone, or ElevenLabs are not configured, the app marks that path clearly and falls back only to keep the demo inspectable. The fallback is useful for local review, but live provider generation is the stronger path.
