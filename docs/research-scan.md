# Research And Open-Source Scan

This scan changed the product direction. The initial version was a rubric-based critic. The current version is Track B: a content curator and dynamic case builder that uses RAG for source grounding and a learner engine for personalization after evidence exists.

## What I Looked At

### Track B: Cold-Start Content Curation

- Merrill's first principles and 4C/ID suggest the first bundle should activate the task, show structure, demonstrate, apply, and integrate.
- Cognitive load and worked-example research supports starting with guided examples before open transfer.
- ICAP and self-explanation support embedding evidence capture throughout learning instead of forcing one diagnostic upfront.
- Concept-map research supports visual structure as both scaffold and evidence source.

Product implication: cold start should generate a structured bundle from content, not ask for learner data that does not exist yet.

### Adaptive Teaching Method Selection

- Learning-styles research warns against fixed visual/audio/text labels.
- CHC/cognitive ability work suggests richer learner state dimensions.
- Knowledge tracing and cognitive diagnosis support concept-level mastery rather than a single score.
- Contextual bandits and adaptive curriculum research frame teaching methods as interventions whose effects can be measured.

Product implication: roleplay, voice, visual cues, notes, hints, mind maps, and quizzes should be selected from evidence and updated over time.

### RAG For Grounded Generation

- RAG is useful for grounding generated notes, cases, hints, and questions in the supplied content set.
- RAG should not determine learner mastery; that comes from telemetry and the learner model.

Product implication: the system sends retrieved chunks plus learner-state summary to the model. The model generates assets under engine constraints.

### Learning From Video

- Multimedia learning research supports segmenting video into learner-paced chunks instead of presenting a long passive watch task.
- Signaling and weeding reduce cognitive load by telling the learner what to attend to and what source noise to ignore.
- Pre-training/orientation helps the learner recognize key terms before the main explanation.
- Interpolated retrieval checks during video improve attention and later recall.
- Generative learning strategies such as self-explanation, summarizing, mapping, drawing, and teaching back help learners actively build the concept.

Product implication: Module 1 should be a video breakdown, not a passive watch page. The model should extract the important ideas, formulas, timestamps, visual cues, self-explanation prompts, retrieval checks, and after-source tasks, then convert them into a student-facing page with summary, facts, formula cards, shortcuts, mind map, rendered diagram, common mistakes, optional voice overview, and one tiny check.

### LLM-As-Judge And Rubric Evaluation

- G-Eval uses a structured evaluation procedure and form-filling paradigm for LLM evaluation.
- Prometheus focuses on custom score rubrics and reference materials for fine-grained evaluation.
- MT-Bench / Chatbot Arena popularized LLM-as-judge while documenting bias risks.
- JudgeLM studies judge bias mitigation such as position, knowledge, and format bias.

Product implication: ProofMark should not return a naked score. It needs structured dimensions, visible evidence, judge diagnostics, calibration, and a fallback path.

### Open-Source Eval Tooling

- OpenAI Evals treats evals as reusable assets and supports model-graded evaluation.
- Inspect AI emphasizes composable eval tasks, scorers, logging, and reproducibility.
- Promptfoo shows that eval tooling needs adversarial testing, assertions, and CI-style workflows.
- DeepEval and Ragas show that evaluation frameworks become useful when they produce repeatable test cases, not only one-off outputs.

Product implication: ProofMark needs golden cases, repeatable checks, and exportable results. The evaluation should feel like an inspectable record, not a chat response.

### Model Routing, Cost, And Reliability

- LLM evaluation systems should treat model calls as unreliable external services.
- Smaller models can be run in parallel and selected by evidence quality instead of always calling the largest model.
- Provider diversity reduces exposure to one vendor's rate limits, outages, and output drift.

Product implication: ProofMark should expose a `judge_trace`: candidate models, quality score, cache key, fallback reason, and escalation policy.

### Educational Assessment And Feedback

- Evidence-Centered Design frames assessment around claims, evidence, and warrants.
- Hattie and Timperley frame useful feedback as feed up, feedback, and feed forward.
- Nicol and Macfarlane-Dick connect formative feedback to self-regulated learning.
- Automated essay scoring research argues against relying only on holistic scores; trait-based/rubric-aligned feedback is more pedagogically useful.

Product implication: ProofMark needs a proof map. Every score should answer: what claim is being made, what evidence supports it, what proof is missing, and what should be observed next?

### Learning Records, Credentials, And Portfolios

- Open Badges includes evidence that supports an achievement claim, such as a URL or artifact produced by the learner.
- xAPI/LRS systems store learning activity statements across online and offline learning.
- Mahara-style e-portfolios let learners collect artifacts, reflections, competencies, and context.

Product implication: ProofMark should produce a proof passport / skill ledger, not just feedback. This makes the result portable into a future flo101 learner record, credential, or reviewer workflow.

### Learner Modeling And Knowledge Tracing

- Bayesian Knowledge Tracing estimates evolving mastery from learner observations.
- pyBKT is an open-source implementation meant to make knowledge tracing reproducible and accessible.
- Deep Knowledge Tracing and related work extend learner modeling over temporal activity traces.
- Duolingo half-life regression personalizes forgetting curves from learner practice history.
- FSRS models difficulty, stability, and retrievability for open-source spaced repetition scheduling.
- MEMORIZE frames spaced repetition as an optimization problem over retention and review cost.

Product implication: A single artifact score is weak. A revision sequence is stronger. ProofMark should estimate mastery from prior state plus new evidence, and compare before/after revisions.

### JEE/PCM Public Source Scan

- NTA public engineering/JEE material frames the preparation context around Physics, Chemistry, and Mathematics.
- NTA IIT-PAL publishes subject-expert lecture categories for Physics, Mathematics, and Chemistry.
- Public JEE paper analysis is not an official question guarantee, but it is useful for product prioritization and broader diagnostic coverage.
- Recent chapter-weightage analyses consistently point to modern physics/current electricity/electrostatics/optics, coordination/chemical bonding/equilibrium/electrochemistry, and mathematics clusters like calculus, algebra, coordinate geometry, vectors/3D, and probability.

Product implication: the product should not be Chemistry-only. It should diagnose PCM, split Mathematics into meaningful subdivisions, and surface high-yield JEE gaps separately from the raw score.

### Agent Benchmarks And Execution Traces

- SWE-bench evaluates agents on real GitHub issues, emphasizing executable proof rather than self-report.
- OpenHands and OSWorld stress trajectories, logs, environments, and reproducible task outcomes.

Product implication: For flo101, the artifact should be treated like a task trace: inspectable, replayable where possible, and tied to a concrete evidence standard.

## What I Implemented From This

- `content_graph`: content normalization, chunking, concept/prerequisite graph, local lexical RAG, source coverage.
- `source_analysis`: optional compact Gemini source/video extraction for source-backed summary, concepts, facts, formulas, timestamps, mistakes, and source notes; the local planner turns that into source insights plus `video_learning_plan` and `student_video_lesson` grounded in multimedia learning research.
- `lesson_graph`: learner-facing guided video/source page before notes, checkpoint, visual repair, practice, final case, and revision.
- `curator`: cold-start bundle with source rationale, concept map, notes, worked example, checkpoints, and embedded evidence sequence.
- `case_builder`: dynamic case, required output, rubric, and three teaching variants.
- `learner_model`: rich telemetry schema and multidimensional profile from correctness, reasoning, confidence, timing, hints, modality, voice, visual, affective, and memory signals.
- `roadmap`: Track B orchestration, cold-start plan, personalized after-evidence plan, and review schedule.
- `generation`: optional OpenAI-compatible model call after RAG plus deterministic fallback with the same asset shape.
- `evidence_map`: claim, status, evidence, missing proof, and reviewer question per rubric dimension.
- `compare_revisions`: before/after revision scoring with dimension deltas and proof improvement summary.
- `skill_ledger`: proof id, mastery update, weakest dimensions, xAPI-style statement, Open Badges-inspired evidence assertion, and audit hash.
- `learning_loop`: personalized half-life-inspired review schedule and adaptive proof challenge.
- `subject_analysis` and `jee_readiness`: PCM subject breakdown and high-yield JEE gap analysis.
- adaptive revision selector: variable test length, 80/20 weak/retained split, 40-60% repeats, and fresh concept variants.
- `next_learning_action`: product-neutral routing from evidence to tutor drill, teach-back, scenario practice, micro-retest, transfer challenge, or artifact revision.
- `judge_trace`: small-model ensemble strategy, candidate quality scoring, cache keys, and fallback/escalation reason.
- `feedback_loop`: feed-up, feedback, and feed-forward fields.
- `judge_diagnostics`: bias and calibration notes.
- Golden evals and unit tests for repeatable evaluation behavior.

## Why This Is More Unique

Most take-home submissions will build a prompt wrapper that gives feedback. ProofLoop is positioned as an adaptive learning-generation system:

```text
objective + content -> RAG grounded bundle -> dynamic case -> embedded evidence -> learner model -> personalized next assets
```

That is closer to what flo101 appears to care about: guided execution, feedback, dynamic learning flows, and verifiable proof-of-work.

## Sources

- G-Eval: https://arxiv.org/abs/2303.16634
- Merrill first principles: https://mdavidmerrill.files.wordpress.com/2019/04/firstprinciplesbymerrill.pdf
- 4C/ID: https://www.4cid.org/wp-content/uploads/2021/04/vanmerrienboer-clark-croock-2002.pdf
- Expertise reversal / cognitive load: https://link.springer.com/article/10.1007/s10648-007-9054-3
- ICAP: https://www.tandfonline.com/doi/full/10.1080/00461520.2014.965823
- Self-explanation: https://asu.elsevierpure.com/en/publications/eliciting-self-explanations-improves-understanding/
- Concept maps meta-analysis: https://www.sciencedirect.com/science/article/pii/S1747938X17300106
- Learning styles evidence: https://journals.sagepub.com/doi/full/10.1111/j.1539-6053.2009.01038.x
- CHC cognitive abilities: https://www.mdpi.com/2079-3200/11/2/32
- NeuralCDM: https://ojs.aaai.org/index.php/AAAI/article/view/6080
- Contextual bandits for adaptive curriculum: https://arxiv.org/abs/2207.14003
- RAG: https://arxiv.org/abs/2005.11401
- Mayer and Pilegard, multimedia learning principles: https://doi.org/10.1017/CBO9781139547369.016
- Ibrahim et al., segmenting/signaling/weeding in educational video: https://doi.org/10.1080/17439884.2011.585993
- Brame, Effective Educational Videos: https://academic.wlu.edu/wp-content/uploads/2020/04/Brame-2016-effective-videos.pdf
- Guo, Kim, and Rubin, MOOC video engagement: https://doi.org/10.1145/2556325.2566239
- Szpunar, Khan, and Schacter, interpolated tests in online lectures: https://scholar.harvard.edu/files/novallkhan/files/pnas_szpunar_khan_schacter.pdf
- Fiorella and Mayer, generative learning strategies: https://bootcampmilitaryfitnessinstitute.com/wp-content/uploads/2016/01/eight-ways-to-promote-generative-learning-fiorella-mayer-2015.pdf
- Prometheus: https://arxiv.org/abs/2310.08491
- MT-Bench / Chatbot Arena: https://arxiv.org/abs/2306.05685
- JudgeLM: https://arxiv.org/abs/2310.17631
- OpenAI Evals: https://github.com/openai/evals
- Inspect AI: https://inspect.aisi.org.uk/
- Promptfoo: https://github.com/promptfoo/promptfoo
- Ragas: https://arxiv.org/abs/2309.15217
- OpenAI pricing: https://openai.com/api/pricing/
- Anthropic pricing: https://www.anthropic.com/pricing
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Evidence-Centered Design four-process architecture: https://ejournals.bc.edu/index.php/jtla/article/view/1671
- Hattie & Timperley, The Power of Feedback: https://assess.ucr.edu/sites/default/files/2019-02/hattietimperley_2007.pdf
- Nicol & Macfarlane-Dick: https://doi.org/10.1080/03075070600572090
- Open Badges 3.0: https://www.imsglobal.org/spec/ob/v3p0/
- Learning Locker / xAPI LRS: https://learninglocker.atlassian.net/wiki/spaces/DOCS/overview
- Mahara ePortfolio: https://mahara.org/view/view.php?id=6
- pyBKT: https://arxiv.org/abs/2105.00385
- Duolingo half-life regression: https://aclanthology.org/P16-1174.pdf
- Duolingo HLR code: https://github.com/duolingo/halflife-regression
- FSRS / Open Spaced Repetition: https://github.com/open-spaced-repetition
- MEMORIZE spaced repetition optimization: https://pubmed.ncbi.nlm.nih.gov/30670661/
- Deep Knowledge Tracing: https://arxiv.org/abs/1506.05908
- Adaptive Forgetting Curves: https://arxiv.org/abs/2004.11327
- DAS3H: https://arxiv.org/abs/1905.06873
- Personalized Forgetting Mechanism: https://arxiv.org/abs/2404.12127
- NTA Engineering exam information: https://nta.ac.in/Engineeringexam
- NTA IIT-PAL lectures: https://nta.ac.in/lecturesContent
- NTA JEE Main exam paper archive example: https://www.nta.ac.in/Download/ExamPaper/Paper_20230322132210.pdf
- JEE Main chapter-wise analysis: https://collegedunia.com/exams/jee-main/chapter-wise-weightage
- SWE-bench: https://github.com/swe-bench
- OpenHands: https://arxiv.org/abs/2407.16741
- OSWorld: https://arxiv.org/abs/2404.07972
