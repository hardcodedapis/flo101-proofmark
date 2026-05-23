# Research Basis

ProofMark uses research as implementation guidance, not as decoration.

## Track B Product Research

The current product is Track B: content curation plus dynamic case generation. The earlier proof evaluator remains as an internal assessment layer.

### Cold-Start Instructional Structure

Cold start should not require a learner profile. It should use instructional-design defaults: activate the objective, show the concept structure, demonstrate with worked examples, ask embedded checks, then move to a dynamic case.

Design impact:

- `curator.py` generates concept map, guided notes, worked example, checkpoint questions, and embedded evidence sequence.
- The first pass teaches and collects evidence side by side.
- Personalization starts after evidence exists.

Sources:

- Merrill, "First Principles of Instruction" - https://mdavidmerrill.files.wordpress.com/2019/04/firstprinciplesbymerrill.pdf
- van Merrienboer et al., "Four-Component Instructional Design" - https://www.4cid.org/wp-content/uploads/2021/04/vanmerrienboer-clark-croock-2002.pdf

### Cognitive Load And Worked Examples

Novices often need worked examples and scaffolding before independent transfer. Support should fade as evidence improves.

Design impact:

- Cold-start bundle includes a worked example before the final case.
- High-support variants use shorter segments and hint ladders.
- Advanced variants move faster to transfer and ambiguity.

Source: Kalyuga, "Expertise Reversal Effect and Its Implications for Learner-Tailored Instruction" - https://link.springer.com/article/10.1007/s10648-007-9054-3

### ICAP, Self-Explanation, And Embedded Evidence

ICAP distinguishes passive, active, constructive, and interactive learning. Self-explanation research supports asking learners to explain reasoning, not only select answers.

Design impact:

- The first pass includes visual checks, micro quiz, typed explanation, and voice/roleplay probe.
- The engine captures evidence during learning instead of front-loading all diagnostics.

Sources:

- Chi and Wylie, "The ICAP Framework" - https://www.tandfonline.com/doi/full/10.1080/00461520.2014.965823
- Chi et al., "Eliciting self-explanations improves understanding" - https://asu.elsevierpure.com/en/publications/eliciting-self-explanations-improves-understanding/

### Readable Multimedia Lessons

Learner pages should not dump retrieved chunks. They should segment source material, signal the important idea, remove irrelevant boilerplate, and put checks near the content they assess.

Design impact:

- `source_analysis.py` asks the model for short, signposted sections instead of raw summaries.
- The UI renders one module at a time: video, source notes, checkpoint, visual repair, final case, revision.
- Raw RAG chunks now stay in the technical trace, not in the learner module.
- PDF URL fetches skip raw binary streams so learner pages do not show extraction artifacts.

Sources:

- Mayer, "Applying the Science of Learning: Evidence-Based Principles for the Design of Multimedia Instruction" - https://pubmed.ncbi.nlm.nih.gov/19014238/
- Mayer, "Research-Based Guidelines for Multimedia Instruction" - https://journals.sagepub.com/doi/pdf/10.1518/155723408x299861
- Cognitive load/worked examples review - https://link.springer.com/article/10.1007/s10648-010-9145-4
- Dunlosky et al., "Improving Students' Learning With Effective Learning Techniques" - https://journals.sagepub.com/doi/full/10.1177/1529100612453266

### Video Learning And Source Breakdowns

Video should not be treated as a passive embed. The first learner page should extract the useful ideas before asking the learner to inspect the original video. The source-analysis call asks Gemini only for compact source-backed extraction: summary, concepts, facts, formulas, timestamps, mistakes, and source notes.

Design impact:

- `source_analysis.py` locally converts compact source extraction into a `video_learning_plan` with pre-watch orientation, segment watch goals, what to notice, what to ignore, pause prompts, self-explanation prompts, retrieval checks, and after-watch generative tasks.
- `source_analysis.py` also locally returns `student_video_lesson`: summary, facts, formula cards, remember/tips, shortcuts, timestamp guide, mind map, diagram prompts, mistakes, voice script, and a tiny check.
- `lesson_graph.py` attaches the plan to the learner-facing source breakdown.
- The UI renders Module 1 as a student-facing video breakdown before notes, checkpoint, visual repair, final case, and revision.
- The plan uses video as source material plus evidence capture: learners extract, explain, map, retrieve, and only open the video when needed.

Sources:

- Mayer and Pilegard, multimedia learning principles including segmenting, pre-training, modality, signaling, and weeding - https://doi.org/10.1017/CBO9781139547369.016
- Ibrahim et al., "Effects of segmenting, signalling, and weeding on learning from educational video" - https://doi.org/10.1080/17439884.2011.585993
- Brame, "Effective Educational Videos" - https://academic.wlu.edu/wp-content/uploads/2020/04/Brame-2016-effective-videos.pdf
- Guo, Kim, and Rubin, "How Video Production Affects Student Engagement" - https://doi.org/10.1145/2556325.2566239
- Szpunar, Khan, and Schacter, interpolated tests improve online lecture learning - https://scholar.harvard.edu/files/novallkhan/files/pnas_szpunar_khan_schacter.pdf
- Fiorella and Mayer, "Eight Ways to Promote Generative Learning" - https://bootcampmilitaryfitnessinstitute.com/wp-content/uploads/2016/01/eight-ways-to-promote-generative-learning-fiorella-mayer-2015.pdf

### Concept Maps And Visual Organization

Concept maps and graphic organizers help make knowledge structure visible. They are useful as a cold-start scaffold and as a diagnostic task.

Design impact:

- `content_graph.py` builds prerequisite/confusion edges.
- `curator.py` turns those edges into a concept-map task.
- Visual evidence is measured as one signal, not treated as a fixed learning style.

Source: Schroeder et al., "Studying and Constructing Concept Maps: A Meta-Analysis" - https://www.sciencedirect.com/science/article/pii/S1747938X17300106

### Learning Styles Caution

The product should not classify users into fixed visual/audio/text types. It should route teaching methods based on measured evidence and update over time.

Design impact:

- `learner_model.py` stores skill dimensions and intervention effectiveness.
- `case_builder.py` shows teaching variants as evidence-driven routes.
- The LLM prompt explicitly forbids fixed learning-style labels.

Source: Pashler et al., "Learning Styles: Concepts and Evidence" - https://journals.sagepub.com/doi/full/10.1111/j.1539-6053.2009.01038.x

### Learner Modeling And Adaptive Method Routing

Learner state should include concept mastery, cognitive/behavioral signals, confidence calibration, hint dependence, and intervention response.

Design impact:

- `learner_model.py` consumes rich telemetry events.
- `roadmap.py` uses the profile to select visual contrast, teach-back, voice rehearsal, roleplay, mixed practice, or transfer challenge.
- Model generation receives a compressed learner-state summary, not raw unstructured logs.

Sources:

- CHC cognitive ability overview - https://www.mdpi.com/2079-3200/11/2/32
- pyBKT - https://arxiv.org/abs/2105.00385
- Neural Cognitive Diagnosis - https://ojs.aaai.org/index.php/AAAI/article/view/6080
- Contextual bandits for adaptive curriculum - https://arxiv.org/abs/2207.14003

### Forgetting Curve And Review Scheduling

Review should be personalized per concept and learner, not a fixed day 1/3/7 template for everyone.

Design impact:

- Existing `learning_loop.py` remains available for artifact/revision scheduling.
- Track B roadmap returns per-concept review rows.
- Future production version should learn half-life/stability from repeated retrieval data.

Sources:

- Ebbinghaus, "Memory" - https://en.wikisource.org/wiki/Memory:_A_Contribution_to_Experimental_Psychology
- Murre and Dros, "Replication and Analysis of Ebbinghaus' Forgetting Curve" - https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644
- Settles and Meeder, "A Trainable Spaced Repetition Model for Language Learning" - https://aclanthology.org/P16-1174.pdf
- Adaptive Forgetting Curves - https://arxiv.org/abs/2004.11327

### RAG And LLM Generation

RAG should ground content generation. It should not replace the learner model.

Design impact:

- `content_graph.py` retrieves source chunks.
- `source_analysis.py` can call Gemini for source/video understanding and otherwise returns a deterministic source-analysis structure.
- `lesson_graph.py` turns source analysis into learner-facing pages before the later personalization call.
- `learner_model.py` compresses learner evidence.
- `generation.py` sends retrieved chunks plus learner-state summary to a model, or returns a deterministic fallback.
- The model generates concrete notes, mind-map changes, source sections, roleplay/voice tasks, hint ladders, and micro-assessments.

Sources:

- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" - https://arxiv.org/abs/2005.11401
- Gemini video understanding docs - https://ai.google.dev/gemini-api/docs/video-understanding
- Gemini structured output docs - https://ai.google.dev/gemini-api/docs/structured-output

## Internal Evaluator Research

## 1. Rubric Form-Filling

G-Eval proposes using strong LLMs with an explicit evaluation procedure and a form-filling paradigm for text evaluation. It also highlights that LLM evaluators need behavioral analysis, not blind trust.

Design impact in ProofMark:

- Evaluate each rubric dimension separately.
- Require structured JSON output.
- Keep evidence and feedback attached to each score.
- Treat the final verdict as a synthesis, not the first judgment.

Source: Liu et al., "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment" - https://arxiv.org/abs/2303.16634

## 2. Custom Rubrics And Reference Material

Prometheus shows the value of evaluator models that use customized score rubrics and reference material for fine-grained evaluation.

Design impact in ProofMark:

- Default rubric is explicit and weighted.
- Users can provide custom rubric dimensions.
- The deterministic baseline is passed to the model as calibration material.
- Provider output is repaired back to the expected rubric dimensions.

Source: Kim et al., "Prometheus: Inducing Fine-grained Evaluation Capability in Language Models" - https://arxiv.org/abs/2310.08491

## 3. LLM Judge Bias Mitigation

The MT-Bench and Chatbot Arena paper supports LLM-as-judge as a scalable approximation of human preference, while also identifying limitations such as position bias, verbosity bias, self-enhancement bias, and limited reasoning.

Design impact in ProofMark:

- Prompt explicitly says not to reward verbosity, polish, or confidence unless it proves a rubric dimension.
- Output includes `judge_diagnostics`.
- Golden cases check that weak short artifacts do not pass just because they sound plausible.
- High-stakes certification is not treated as fully automated.

Source: Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" - https://arxiv.org/abs/2306.05685

## 4. Formative Feedback Loop

Hattie and Timperley's feedback model says effective feedback should answer: Where am I going? How am I going? Where to next?

Design impact in ProofMark:

- Output includes `feedback_loop`.
- `feed_up_goal` states what good work must prove.
- `feed_back_current_state` summarizes current evidence.
- `feed_forward_next_action` gives the next concrete improvement.

Source: Hattie & Timperley, "The Power of Feedback" - https://assess.ucr.edu/sites/default/files/2019-02/hattietimperley_2007.pdf

## 5. Self-Regulated Learning

Nicol and Macfarlane-Dick argue that formative feedback should support learners in self-regulating their own work, not only receiving teacher judgment.

Design impact in ProofMark:

- Next steps include acceptance criteria the learner can use before resubmitting.
- Feedback emphasizes task/process/self-regulation behavior.
- The system avoids generic praise and pushes toward inspectable revision.

Source: Nicol & Macfarlane-Dick, "Formative assessment and self-regulated learning" - https://doi.org/10.1080/03075070600572090

## 6. Evidence-Centered Assessment Design

Evidence-Centered Design frames assessment around what claims are being made about a learner, what evidence supports those claims, and what tasks elicit that evidence.

Design impact in ProofMark:

- Output includes an `evidence_map`.
- Each dimension has a claim, status, visible evidence, missing proof, and reviewer question.
- The evaluator is positioned as evidence interpretation, not only scoring.

Source: Almond, Steinberg, and Mislevy, "Enhancing the Design and Delivery of Assessment Systems: A Four-Process Architecture" - https://ejournals.bc.edu/index.php/jtla/article/view/1671

## 7. Learning Records And Evidence Portability

Open Badges includes evidence that supports an achievement claim, and xAPI/LRS systems store learning activity statements.

Design impact in ProofMark:

- Output includes a `skill_ledger`.
- The ledger contains an Open Badges-inspired evidence assertion and xAPI-style statement.
- The implementation is standards-shaped but does not claim full compliance.

Sources:

- Open Badges 3.0 - https://www.imsglobal.org/spec/ob/v3p0/
- Learning Locker / xAPI LRS - https://learninglocker.atlassian.net/wiki/spaces/DOCS/overview

## 8. Knowledge Tracing

Bayesian Knowledge Tracing estimates evolving mastery from learner observations; pyBKT makes this family of models accessible and reproducible.

Design impact in ProofMark:

- The skill ledger includes `prior_mastery`, `evidence_strength`, and `updated_mastery`.
- Revision comparison measures change over time instead of treating artifacts as isolated events.

Source: Badrinath, Wang, and Pardos, "pyBKT: An Accessible Python Library of Bayesian Knowledge Tracing Models" - https://arxiv.org/abs/2105.00385

## 9. Personalized Spaced Repetition

Duolingo's half-life regression models memory as a personalized half-life that changes with practice history. FSRS similarly tracks stability/retrievability and is used in open-source spaced repetition workflows. MEMORIZE frames scheduling as an optimization problem over retention and review load.

Design impact in ProofMark:

- Output includes `learning_loop`.
- Review timing is based on prior mastery, evidence strength, score delta, confidence, days since last review, and dimension weakness.
- The system schedules proof-of-work re-challenges, not passive flashcard recall.

Sources:

- Settles and Meeder, "A Trainable Spaced Repetition Model for Language Learning" - https://aclanthology.org/P16-1174.pdf
- Duolingo half-life regression code - https://github.com/duolingo/halflife-regression
- FSRS / Open Spaced Repetition - https://github.com/open-spaced-repetition
- Tabibian et al., "Enhancing human learning via spaced repetition optimization" - https://pubmed.ncbi.nlm.nih.gov/30670661/

## 10. Adaptive Forgetting By Skill

Adaptive forgetting-curve work argues that retention should be modeled per learner and per knowledge component, not as one global decay curve. DAS3H extends this idea to distributed practice over skills, and concept-driven knowledge tracing adds a personalized forgetting mechanism.

Design impact in ProofLoop PCM:

- The review plan is attached to weak subject/chapter/subtopic tags, not just the whole test score.
- The next revision test mixes repeated items with fresh variants so the system checks recall and transfer.
- Later attempts can update the learner's stability estimate differently for Physics, Chemistry, and Mathematics.

Sources:

- "Adaptive Forgetting Curves for Spaced Repetition Language Learning" - https://arxiv.org/abs/2004.11327
- "DAS3H: Modeling Student Learning and Forgetting for Optimally Scheduling Distributed Practice of Skills" - https://arxiv.org/abs/1905.06873
- "Personalized Forgetting Mechanism with Concept-Driven Knowledge Tracing" - https://arxiv.org/abs/2404.12127

## 11. JEE/PCM Topic Basis

JEE Paper 1 preparation is inherently PCM. NTA public material frames engineering preparation around Physics, Chemistry, and Mathematics, and NTA's IIT-PAL content provides subject expert lectures in those three subjects. Public previous-paper analyses are not official blueprints, but they are useful for product prioritization: they consistently highlight modern physics/current electricity/electrostatics/optics, coordination and chemical bonding/equilibrium/electrochemistry, and mathematics clusters such as calculus, algebra, coordinate geometry, vectors/3D, and probability.

Design impact in ProofLoop PCM:

- The diagnostic moved from Chemistry-only to balanced Physics, Chemistry, and Mathematics.
- Mathematics is not one bucket; it is split into algebra, calculus, coordinate geometry, vectors/3D, trigonometry, and probability/statistics.
- JEE-readiness is a separate analysis layer, so high-yield gaps are visible even when the overall score looks acceptable.

Sources:

- NTA Engineering exam information - https://nta.ac.in/Engineeringexam
- NTA IIT-PAL subject lectures - https://nta.ac.in/lecturesContent
- NTA public JEE Main exam paper archive example - https://www.nta.ac.in/Download/ExamPaper/Paper_20230322132210.pdf
- Collegedunia chapter-wise JEE Main analysis - https://collegedunia.com/exams/jee-main/chapter-wise-weightage

## 12. Model Ensembles And Operational Reliability

The open-source evaluation ecosystem treats evaluation as a reproducible system: prompts, scorers, assertions, logs, and model outputs must be inspected. In production, model providers can fail, rate-limit, or drift.

Design impact in ProofMark:

- Output includes `judge_trace`.
- Candidate outputs are scored for grounding, rubric coverage, actionability, calibration, and operational health.
- The preferred architecture is a small-model ensemble with frontier escalation only on disagreement.

Sources:

- OpenAI Evals - https://github.com/openai/evals
- Inspect AI - https://inspect.aisi.org.uk/
- Promptfoo - https://github.com/promptfoo/promptfoo
- Ragas - https://arxiv.org/abs/2309.15217
