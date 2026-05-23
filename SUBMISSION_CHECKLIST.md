# Submission Checklist

This repository targets Track B from the flo101 Applied AI Engineer Assessment:

```text
Content Curator + Dynamic Case Builder
Input: learning objective + small content set
Output: curated learning bundle, dynamic challenge/case, why inputs were chosen, required output
```

## Included Deliverables

| Assessment deliverable | Included file(s) |
|---|---|
| Code repository | `src/`, `web/`, `tests/`, `eval/`, `scripts/` |
| README with setup | `README.md` |
| Architecture note | `docs/architecture.md` |
| Product note | `docs/product-note.md` |
| Evaluation note | `docs/evaluation-note.md` |
| AI usage disclosure | `docs/ai-usage-disclosure.md` |
| Demo walkthrough script | `docs/demo-script.md` |
| Requirement proof map | `docs/submission-proof.md` |

## Requirement Coverage

- Accepts a learning objective and supplied content set.
- Supports pasted notes, URLs, transcripts, Markdown/text/TeX uploads, and text-based PDF uploads.
- Builds a content graph, selected source rationale, RAG trace, concept map, notes, checkpoints, practice, dynamic case, required output, and rubric.
- Handles cold start without a learner profile.
- Captures learner answers as evidence and regenerates learner state, relearn content, retests, and spaced review schedule.
- Includes explicit failure handling for empty/missing inputs, ungrounded URL-only sources, irrelevant/vague sources, objective-source mismatch, provider failures, malformed model output, request-size/rate limits, and missing provider keys.
- Includes evaluation through `eval/run_eval.py`, unit tests, and `scripts/smoke.sh`.
- Documents the cost/latency/reliability tradeoff in `docs/model-strategy.md`, `docs/architecture.md`, and `docs/product-note.md`.

## Verification Run

Verified locally on 2026-05-24:

```bash
node --check web/static/app.js
node --check web/static/renderLesson.js
node --check web/static/adaptiveEvents.js
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 eval/run_eval.py
PYTHONPATH=src python3 -m compileall -q src tests eval
bash scripts/smoke.sh
```

Result: 68 unit tests passed, Track B golden eval passed, smoke check passed.

## Submit Separately

The assessment also asks for a 3-5 minute demo video. This repository includes a demo script, but the recorded video should be attached separately if it is not already part of the submission message.
