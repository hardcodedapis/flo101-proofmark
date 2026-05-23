from __future__ import annotations

import unittest

from proofmark.chemistry import initial_pcm_test, submit_pcm_attempt
from proofmark.schema import InputError


class PcmEngineTest(unittest.TestCase):
    def test_initial_test_has_balanced_cbse_jee_coverage(self) -> None:
        test = initial_pcm_test()

        self.assertEqual(test["attempt_number"], 1)
        self.assertEqual(test["question_count"], 18)
        self.assertEqual(test["mix"]["mcq"], 9)
        self.assertEqual(test["mix"]["written"], 9)
        self.assertEqual(
            set(test["coverage"]),
            {"Chemistry", "Mathematics", "Physics"},
        )
        self.assertIn("Calculus", set(test["domain_coverage"]))
        self.assertIn("Electrodynamics", set(test["domain_coverage"]))

    def test_attempt_returns_domain_proof_and_revision_test(self) -> None:
        test = initial_pcm_test()
        responses = {}
        for question in test["questions"]:
            if question["type"] == "mcq":
                responses[question["id"]] = "A"
            else:
                responses[question["id"]] = "I know this chapter but cannot explain the exact concept yet."

        result = submit_pcm_attempt(
            {
                "attempt_number": test["attempt_number"],
                "question_ids": [question["id"] for question in test["questions"]],
                "responses": responses,
            }
        )

        self.assertIn("subject_analysis", result)
        self.assertIn("domain_analysis", result)
        self.assertIn("chapter_analysis", result)
        self.assertIn("subtopic_analysis", result)
        self.assertIn("proof_analysis", result)
        self.assertIn("jee_readiness", result)
        self.assertIn("next_learning_action", result)
        self.assertIn("review_plan", result)
        self.assertIn("next_test", result)
        self.assertIn(
            result["next_learning_action"]["recommended_mode"],
            {"tutor_drill", "teach_back", "scenario_practice", "micro_retest", "transfer_challenge"},
        )
        self.assertEqual(result["next_test"]["attempt_number"], 2)
        self.assertEqual(result["next_test"]["question_count"], 13)
        policy = result["next_test"]["selection_policy"]
        self.assertGreaterEqual(policy["actual_repeat_ratio"], 0.40)
        self.assertLessEqual(policy["actual_repeat_ratio"], 0.60)
        fresh_weak_questions = [
            question for question in result["next_test"]["questions"]
            if question.get("selection_reason") == "fresh variant from missed concept"
        ]
        self.assertGreaterEqual(len(fresh_weak_questions), 4)

    def test_missing_responses_are_rejected(self) -> None:
        test = initial_pcm_test()

        with self.assertRaises(InputError) as exc:
            submit_pcm_attempt(
                {
                    "attempt_number": 1,
                    "question_ids": [question["id"] for question in test["questions"]],
                    "responses": {},
                }
            )

        self.assertEqual(exc.exception.code, "missing_responses")

    def test_revision_policy_uses_attempt_history(self) -> None:
        test = initial_pcm_test()
        current_questions = test["questions"][6:]
        history_questions = test["questions"][:6]
        responses = {
            question["id"]: ("A" if question["type"] == "mcq" else "unsure")
            for question in current_questions
        }

        result = submit_pcm_attempt(
            {
                "attempt_number": 2,
                "question_ids": [question["id"] for question in current_questions],
                "responses": responses,
                "history": [
                    {
                        "attempt_number": 1,
                        "overall_score": 20,
                        "wrong_question_ids": [question["id"] for question in history_questions[:4]],
                        "correct_question_ids": [question["id"] for question in history_questions[4:]],
                    }
                ],
            }
        )

        policy = result["next_test"]["selection_policy"]
        self.assertGreater(policy["history_questions_considered"], len(current_questions))
        self.assertGreaterEqual(policy["actual_repeat_ratio"], 0.40)
        self.assertLessEqual(policy["actual_repeat_ratio"], 0.60)


if __name__ == "__main__":
    unittest.main()
