from __future__ import annotations

import unittest
from pathlib import Path

from proofmark.compare import compare_revisions
from proofmark.schema import InputError
from proofmark.rubric import build_rubric
from proofmark.schema import validate_payload
from proofmark.heuristics import evaluate_with_heuristics
from proofmark.workflow import _repair_result, evaluate_artifact


ROOT = Path(__file__).resolve().parents[1]


def read_example(name: str) -> str:
    return (ROOT / "examples" / name).read_text(encoding="utf-8")


class WorkflowTest(unittest.TestCase):
    def test_strong_artifact_scores_higher_than_weak_artifact(self) -> None:
        shared = {
            "learner_goal": "Demonstrate product judgment by designing a reliable AI workflow for skill evaluation.",
            "output_goal": "A concrete artifact that can be reviewed as proof-of-work.",
            "artifact_type": "brief",
            "level": "intermediate",
        }
        strong = evaluate_artifact({**shared, "artifact": read_example("strong_artifact.txt")}, provider="local")
        weak = evaluate_artifact({**shared, "artifact": read_example("weak_artifact.txt")}, provider="local")

        self.assertGreater(strong["overall_score"], weak["overall_score"])
        self.assertTrue(strong["next_best_step"]["acceptance_criteria"])
        self.assertIn("feedback_loop", strong)
        self.assertIn("judge_diagnostics", strong)
        self.assertIn("evidence_map", strong)
        self.assertIn("skill_ledger", strong)
        self.assertIn("learning_loop", strong)
        self.assertIn("next_learning_action", strong)
        self.assertIn("judge_trace", strong)
        self.assertTrue(strong["next_learning_action"]["success_criteria"])
        self.assertEqual(len(strong["evidence_map"]), len(strong["rubric"]))
        self.assertIn("xapi_statement", strong["skill_ledger"]["standards_shaped_exports"])
        self.assertGreaterEqual(strong["learning_loop"]["next_review_in_days"], 1)
        self.assertEqual(weak["reliability"]["warnings"][0]["code"], "short_artifact")

    def test_empty_artifact_is_rejected(self) -> None:
        with self.assertRaises(InputError) as exc:
            evaluate_artifact({"artifact": "", "artifact_type": "brief"}, provider="local")

        self.assertEqual(exc.exception.code, "empty_artifact")

    def test_unsupported_artifact_type_is_rejected(self) -> None:
        with self.assertRaises(InputError) as exc:
            evaluate_artifact({"artifact": "This has some content.", "artifact_type": "video"}, provider="local")

        self.assertEqual(exc.exception.code, "unsupported_artifact_type")

    def test_oversized_artifact_is_rejected_before_provider_call(self) -> None:
        huge = "word " * 90_000
        with self.assertRaises(InputError) as exc:
            evaluate_artifact({"artifact": huge, "artifact_type": "brief"}, provider="openai")

        self.assertEqual(exc.exception.code, "artifact_too_large")

    def test_custom_rubric_preserves_dimensions(self) -> None:
        result = evaluate_artifact(
            {
                "artifact": read_example("strong_artifact.txt"),
                "artifact_type": "brief",
                "learner_goal": "Show AI workflow design judgment.",
                "custom_rubric": ["Specificity", "Verification", "User value"],
            },
            provider="local",
        )

        self.assertEqual(
            [item["name"] for item in result["rubric"]],
            ["Specificity", "Verification", "User value"],
        )
        self.assertGreaterEqual(result["overall_score"], 0)
        self.assertLessEqual(result["overall_score"], 100)

    def test_malformed_provider_shape_repairs_to_baseline(self) -> None:
        request = validate_payload(
            {
                "artifact": read_example("strong_artifact.txt"),
                "artifact_type": "brief",
                "learner_goal": "Show AI workflow design judgment.",
            }
        )
        rubric = build_rubric(request)
        baseline = evaluate_with_heuristics(request, rubric)

        repaired = _repair_result(
            {
                "overall_score": 999,
                "rubric": [{"name": "Goal fit", "score": 12}],
                "reliability": "not a dictionary",
            },
            request,
            rubric,
            baseline,
        )

        self.assertLessEqual(repaired["overall_score"], 100)
        self.assertIsInstance(repaired["reliability"], dict)
        self.assertEqual(repaired["rubric"][0]["score"], 5)
        self.assertIn("skill_ledger", repaired)
        self.assertIn("next_learning_action", repaired)

    def test_openai_provider_without_key_falls_back_locally(self) -> None:
        result = evaluate_artifact(
            {
                "artifact": read_example("strong_artifact.txt"),
                "artifact_type": "brief",
                "learner_goal": "Show AI workflow design judgment.",
            },
            provider="openai",
        )

        self.assertTrue(result["metadata"]["fallback_used"])
        self.assertEqual(result["metadata"]["provider"], "local-heuristic")
        self.assertTrue(
            any(warning["code"] == "provider_fallback" for warning in result["reliability"]["warnings"])
        )

    def test_revision_comparison_detects_proof_improvement(self) -> None:
        result = compare_revisions(
            {
                "before_artifact": read_example("weak_artifact.txt"),
                "after_artifact": read_example("strong_artifact.txt"),
                "artifact_type": "brief",
                "learner_goal": "Demonstrate product judgment by designing a reliable AI workflow for skill evaluation.",
                "output_goal": "A concrete artifact that can be reviewed as proof-of-work.",
            },
            provider="local",
        )

        self.assertGreater(result["score_delta"], 0)
        self.assertGreater(result["after"]["overall_score"], result["before"]["overall_score"])
        self.assertTrue(result["dimension_deltas"])
        self.assertTrue(result["improved_dimensions"])
        self.assertIn("learning_loop", result)
        self.assertIn("next_learning_action", result)
        self.assertGreater(
            result["after"]["skill_ledger"]["updated_mastery"],
            result["before"]["skill_ledger"]["updated_mastery"],
        )

    def test_revision_comparison_rejects_identical_artifacts(self) -> None:
        with self.assertRaises(InputError) as exc:
            compare_revisions(
                {
                    "before_artifact": "same artifact",
                    "after_artifact": "same artifact",
                    "artifact_type": "brief",
                },
                provider="local",
            )

        self.assertEqual(exc.exception.code, "unchanged_revision")

    def test_personalized_review_schedule_changes_with_prior_mastery(self) -> None:
        shared = {
            "artifact": read_example("strong_artifact.txt"),
            "artifact_type": "brief",
            "learner_goal": "Demonstrate product judgment by designing a reliable AI workflow for skill evaluation.",
            "output_goal": "A concrete artifact that can be reviewed as proof-of-work.",
            "days_since_last_review": 4,
        }
        low_prior = evaluate_artifact({**shared, "prior_mastery": 0.2}, provider="local")
        high_prior = evaluate_artifact({**shared, "prior_mastery": 0.8}, provider="local")

        self.assertLessEqual(
            low_prior["learning_loop"]["next_review_in_days"],
            high_prior["learning_loop"]["next_review_in_days"],
        )


if __name__ == "__main__":
    unittest.main()
