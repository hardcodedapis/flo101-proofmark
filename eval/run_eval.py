from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from proofmark.workflow import evaluate_artifact
from proofmark.roadmap import build_track_b_plan


def load_cases() -> list[dict]:
    return json.loads((ROOT / "eval" / "golden_cases.json").read_text(encoding="utf-8"))


def load_track_b_cases() -> list[dict]:
    path = ROOT / "eval" / "track_b_cases.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def contains_gap(result: dict, fragment: str) -> bool:
    haystack = " ".join(result.get("missing_gaps", [])).lower()
    haystack += " " + json.dumps(result.get("next_best_step", {})).lower()
    return fragment.lower() in haystack


def run() -> int:
    failures: list[str] = []
    rows: list[tuple[str, int, str]] = []
    track_b_rows: list[tuple[str, int, str]] = []

    for case in load_cases():
        artifact = (ROOT / case["artifact_file"]).read_text(encoding="utf-8")
        result = evaluate_artifact(
            {
                "artifact": artifact,
                "artifact_type": case["artifact_type"],
                "learner_goal": case["learner_goal"],
                "output_goal": case["output_goal"],
                "level": "intermediate",
            },
            provider="local",
        )
        score = result["overall_score"]
        confidence = result["reliability"]["confidence"]
        rows.append((case["name"], score, confidence))

        if "min_score" in case and score < case["min_score"]:
            failures.append(f"{case['name']}: expected score >= {case['min_score']}, got {score}")
        if "max_score" in case and score > case["max_score"]:
            failures.append(f"{case['name']}: expected score <= {case['max_score']}, got {score}")
        if confidence not in case["expected_confidence"]:
            failures.append(
                f"{case['name']}: expected confidence in {case['expected_confidence']}, got {confidence}"
            )
        if not contains_gap(result, case["must_include_gap_fragment"]):
            failures.append(
                f"{case['name']}: expected gap fragment '{case['must_include_gap_fragment']}'"
            )

    for case in load_track_b_cases():
        result = build_track_b_plan(
            {
                "learning_objective": case["learning_objective"],
                "content_set": case["content_set"],
                "constraints": {"generate_with_model": False, "analyze_sources_with_gemini": False},
            }
        )
        score, notes = score_track_b_output(result, case)
        track_b_rows.append((case["name"], score, "; ".join(notes)))
        if score < case.get("min_score", 80):
            failures.append(f"{case['name']}: expected Track B score >= {case.get('min_score', 80)}, got {score}")

    print("Legacy proof-evaluator golden evaluation")
    for name, score, confidence in rows:
        print(f"- {name}: score={score}, confidence={confidence}")

    print("\nTrack B content-curation evaluation")
    for name, score, notes in track_b_rows:
        print(f"- {name}: score={score} ({notes})")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nAll golden checks passed.")
    return 0


def score_track_b_output(result: dict, case: dict) -> tuple[int, list[str]]:
    score = 0
    notes: list[str] = []
    concepts = [concept.get("name", "").lower() for concept in result.get("content_graph", {}).get("concepts", [])]
    case_text = json.dumps(result.get("dynamic_case", {}), sort_keys=True).lower()
    warnings = [warning.get("code") for warning in result.get("content_graph", {}).get("warnings", [])]
    sources = result.get("content_graph", {}).get("sources", [])
    required_warnings = [item.lower() for item in case.get("required_warnings", [])]

    expected_warning = case.get("expected_warning")
    if expected_warning:
        if expected_warning in warnings:
            score += 35
            notes.append("warning ok")
        else:
            notes.append(f"missing warning {expected_warning}")
        expected_state = case.get("expected_source_state")
        if expected_state and any(source.get("source_state") == expected_state for source in sources):
            score += 35
            notes.append("source state ok")
        else:
            notes.append(f"missing source state {expected_state}")
        if any(not source.get("content_is_grounded", True) for source in sources):
            score += 30
            notes.append("ungrounded flag ok")
        else:
            notes.append("missing ungrounded flag")
        return score, notes

    expected_groups = [_as_match_group(item) for item in case.get("expected_concepts", [])]
    matched = [group for group in expected_groups if any(candidate in concepts for candidate in group)]
    concept_score = int(30 * len(matched) / max(1, len(expected_groups)))
    score += concept_score
    notes.append(f"concepts {len(matched)}/{len(expected_groups)}")

    fragments = [item.lower() for item in case.get("case_fragments", [])]
    matched_fragments = [item for item in fragments if item in case_text]
    case_score = int(20 * len(matched_fragments) / max(1, len(fragments)))
    score += case_score
    notes.append(f"case fragments {len(matched_fragments)}/{len(fragments)}")

    forbidden = [item.lower() for item in case.get("forbidden_concepts", [])]
    bad = [item for item in forbidden if item in concepts]
    if not bad:
        score += 15
        notes.append("no bad concepts")
    else:
        notes.append(f"bad concepts: {', '.join(bad)}")

    quality_score, quality_notes = _track_b_quality_score(result)
    score += quality_score
    notes.extend(quality_notes)
    source_claim_score, source_claim_notes = _source_claim_score(result, case)
    score += source_claim_score
    notes.extend(source_claim_notes)
    if required_warnings:
        warning_hits = [warning for warning in required_warnings if warning in warnings]
        notes.append(f"required warnings {len(warning_hits)}/{len(required_warnings)}")
        if len(warning_hits) != len(required_warnings):
            score -= 25
    return score, notes


def _source_claim_score(result: dict, case: dict) -> tuple[int, list[str]]:
    expected = [item.lower() for item in case.get("source_claim_fragments", [])]
    if not expected:
        return 10, ["source claim check n/a"]
    claims = result.get("dynamic_case", {}).get("grounding", {}).get("source_claims", [])
    claim_text = json.dumps(claims, sort_keys=True).lower()
    matched = [item for item in expected if item in claim_text]
    score = int(10 * len(matched) / max(1, len(expected)))
    return score, [f"source claims {len(matched)}/{len(expected)}"]


def _as_match_group(item: object) -> list[str]:
    if isinstance(item, list):
        return [str(value).lower() for value in item if str(value).strip()]
    return [str(item).lower()]


def _track_b_quality_score(result: dict) -> tuple[int, list[str]]:
    score = 0
    notes: list[str] = []
    dynamic_case = result.get("dynamic_case", {})
    bundle = result.get("curated_learning_bundle", {})
    graph = result.get("content_graph", {})
    case_text = json.dumps(dynamic_case, sort_keys=True).lower()

    grounding = dynamic_case.get("grounding", {}) if isinstance(dynamic_case.get("grounding"), dict) else {}
    source_requirements = dynamic_case.get("source_requirements", [])
    if grounding.get("must_cite") or source_requirements:
        score += 5
        notes.append("case grounding ok")
    else:
        notes.append("case missing explicit grounding")

    required = dynamic_case.get("required_output", {})
    components = required.get("components", []) if isinstance(required, dict) else []
    minimum = str(required.get("minimum_evidence", "")) if isinstance(required, dict) else ""
    if len(components) >= 4 and minimum:
        score += 5
        notes.append("required output concrete")
    else:
        notes.append("required output too thin")

    generic_markers = [
        "where the main concept and a prerequisite concept interact",
        "apply x and y interact",
        "prove you can use",
        "realistic task where",
    ]
    if not any(marker in case_text for marker in generic_markers):
        score += 5
        notes.append("case not generic")
    else:
        notes.append("case still generic")

    selected_sources = bundle.get("selected_sources", [])
    if selected_sources and any(source.get("source_id") for source in selected_sources):
        score += 5
        notes.append("selected sources present")
    else:
        notes.append("missing selected sources")

    supported_concepts = [
        concept
        for concept in graph.get("concepts", [])
        if concept.get("source_ids") or concept.get("chunk_ids")
    ]
    if len(supported_concepts) >= min(2, len(graph.get("concepts", []))):
        score += 5
        notes.append("concept source support ok")
    else:
        notes.append("concepts lack source support")

    return score, notes


if __name__ == "__main__":
    raise SystemExit(run())
