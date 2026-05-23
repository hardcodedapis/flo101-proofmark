# AI Usage Disclosure

AI assistance was used to help create this take-home submission.

## Generated Or AI-Assisted

- Initial project structure
- Track B content-curation and dynamic-case implementation
- Web UI code
- Sample artifacts
- Unit tests
- Track B and internal evaluation harnesses
- README and documentation drafts
- Research-basis notes and citation organization
- flo101-inspired UI adaptation using public website assets and visible public design language

## Human Direction

The product direction is Track B: **Content Curator + Dynamic Case Builder**. The required input is a learning objective plus a small content set. The required output is a curated bundle, dynamic challenge, explanation of why inputs were chosen, and required learner output.

The human contribution was not limited to prompt entry. The broad product shape, adaptive-learning workflow, system boundaries, and review bar were human-directed: source-grounded lesson generation, learner evidence capture, server-side grading, persistent learner state, evaluation pressure tests, security hardening, and the final assessment narrative were all selected and iterated through human critique. AI was used as an implementation and drafting accelerator under that direction.

The earlier proof/evaluator code remains only as internal assessment infrastructure for checking learner artifacts after a dynamic case. It is not the submitted product direction.

## Review And Validation

The generated implementation was reviewed and adjusted for:

- source-grounded Track B generation with local fallback reliability
- dependency-light setup
- explicit failure handling
- deterministic evaluation path
- required Track B assessment deliverables

Verification commands were run locally:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 eval/run_eval.py
PYTHONPATH=src python3 -m compileall -q src eval tests
```

## Boundaries

No proprietary flo101 code or private data was used. The sample artifacts are synthetic examples created for this assessment.

The browser UI uses public flo101 website assets for assessment-context branding:

- `https://flo101.com/`
- `https://flo101.com/icon.svg`
- `https://flo101.com/brand/Flo%20Logo%20Hi-Res.png`
