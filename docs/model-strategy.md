# Model Strategy And Reliability Tradeoff

ProofLoop Track B uses models for source understanding and learning-asset generation, not as decorative chat on top of a static template.

## Runtime Strategy

```text
objective + content set
  -> source state validation
  -> RAG retrieval / Pinecone memory when configured
  -> Gemini source/video analysis when configured
  -> OpenAI-compatible learning asset generation
  -> ElevenLabs audio explanation when configured
  -> learner evidence + forgetting-curve review
```

The strongest live path uses provider calls. The local fallback exists so the reviewer can inspect the workflow shape when keys, quota, or network access fail.

## Why Page-Level Generation Is Better

Generating the entire lesson graph in one frontier-model call creates a token-per-minute spike and makes rate limits more likely. The better production path is staged:

1. Analyze sources and media.
2. Generate the curated bundle.
3. Generate the dynamic case.
4. Generate the page the learner is about to see.
5. Use the learner's checkpoint evidence to generate the next page.

This keeps AI central while letting each call react to the latest learner evidence.

## Reliability Controls

- runtime API keys are never written to source files
- provider responses are schema-validated
- successful provider responses are cached
- 429/5xx provider errors use retry/backoff
- failures are surfaced in the UI instead of silently pretending the model succeeded
- URL-only inputs are marked metadata-only unless fetched, analyzed, or paired with source text

## Tradeoff

Keeping full raw context improves grounding and gives the model enough detail to build better notes, diagrams, cases, and voice scripts. It also increases latency and rate-limit risk. The app keeps that tradeoff explicit instead of shrinking the prompt until the model output becomes generic.

## Caching

Application cache key:

```text
sha256(artifact + rubric_version + prompt_version + model_name)
```

Cache:

- individual judge result
- evidence map
- final selected result
- before/after comparison result

Provider prompt caching can reduce repeated static prompt/rubric costs. Application-level result caching is the larger product win because the same artifact/rubric/model combination does not need to be evaluated again.

## Tradeoff

We trade orchestration complexity for lower average cost, higher fault tolerance, and better calibration. Tail latency can increase if every judge is awaited, so the production version should use timeouts, quorum, cache hits, and early exit when two high-quality judges agree.
