# Demo Script

Target length: 4-5 minutes.

## 0:00 - 0:30: Frame The Product

"This is Track B: Content Curator plus Dynamic Case Builder. The required input is only a learning objective and a small content set. Learner profile data is optional."

Show the landing page and the input panel.

## 0:30 - 1:15: Cold Start

Click "Physics diagram seed", then "Build learning bundle."

Show:

- required input contract
- embedded source/video cards
- learner-facing video page with summary, key facts, remember/tips, timestamps, mind map, and a small check
- notes directly under the media
- quick checks
- visual map and flowchart
- revision schedule

"When we do not have learner data, we do not pretend to personalize. The system builds a structured first lesson from the sources and embeds small evidence captures inside the learning flow."

## 1:15 - 2:00: Dynamic Case

Open the adaptive quiz/final case step.

Show:

- scenario
- constraints
- required learner output
- rubric

"The output is not just notes. It creates a challenge and tells the learner what artifact or response they must produce. That gives the platform something to evaluate."

## 2:00 - 3:00: Source Analysis And Visual Repair

Open the diagram/flowchart step, then the technical trace at the bottom.

Show:

- page sequence
- source insights
- video/source timeline
- visual cues
- RAG chunks

"Gemini can make the first source-analysis call when configured. Without the key, the local planner returns the same structure. RAG grounds the facts; the lesson graph decides what the learner sees next."

## 3:00 - 3:45: Evidence Sample

Answer one checkpoint or drawing prompt. The browser POSTs that learner event to `/api/track-b/adapt`, and the backend regenerates the learner profile, roadmap, revision timing, and next mode. Then click "Evidence sample" to show the preloaded multi-event path.

Show:

- learner state changes from unknown to evidence-derived
- active variant
- weakest signals
- adaptive roadmap
- personalized review schedule

"Learning and testing happen side by side. Visual checks, quiz answers, typed explanations, voice/roleplay, hint behavior, confidence, timing, and memory all become learner telemetry. The UI no longer only says this would happen; it sends the event and receives an updated plan."

## 3:45 - 4:30: RAG And Model Boundary

Open "Sources/debug."

Show:

- AI source analysis status
- retrieved chunks
- lesson graph
- LLM generation packet
- model generation fallback or model-generated assets

"Gemini handles source/video understanding when configured. RAG grounds the content. The engine summarizes the learner. The LLM receives both and generates the next notes, mind map, roleplay, hints, micro-assessment, and evidence plan. If no provider key exists, local fallbacks return the same shapes."

## 4:30 - 5:00: Reliability

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 eval/run_eval.py
```

"The earlier proof evaluator and PCM retest engine remain underneath as assessment infrastructure, but the main product is now the Track B curator and dynamic case builder."
