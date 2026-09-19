import random
import unittest
from unittest.mock import patch

from game.balance import run_batch, run_life, select_choice


class BalanceTests(unittest.TestCase):
    def test_policy_cannot_take_locked_reward_and_respects_pace_preference(self):
        event = {"id": "pace", "choices": [
            {"id": "locked", "effects": [{"op": "stat", "key": "cash", "delta": 100000}]},
            {"id": "push", "effects": [{"op": "flag", "key": "work_pace", "value": "push"}]},
            {"id": "rest", "effects": [{"op": "flag", "key": "work_pace", "value": "rest"}]}]}
        public = {"stats": {"health": 40, "stress": 70}, "event": {"id": "pace", "choices": [
            {"id": "locked", "available": False}, {"id": "push", "available": True},
            {"id": "rest", "available": True}]}}
        self.assertEqual(select_choice(public, event, "cautious", random.Random(0)), "rest")
        self.assertEqual(select_choice(public, event, "overwork", random.Random(0)), "push")
        for seed in range(12):
            self.assertNotEqual(select_choice(public, event, "random", random.Random(seed)), "locked")

    def test_same_seed_has_identical_complete_trace(self):
        first = run_life(2, "struggling", "random")
        self.assertEqual(first, run_life(2, "struggling", "random"))
        self.assertGreater(first["steps"], 0)
        self.assertLessEqual(first["steps"], 150)
        self.assertTrue(first["death_reason"])

    def test_batch_has_comparable_groups_and_correct_rate_denominators(self):
        report = run_batch(1)
        self.assertEqual(report["total_runs"], 9)
        self.assertEqual(len(report["groups"]), 9)
        self.assertTrue(report["determinism_check"]["identical"])
        for run in report["runs"]:
            self.assertEqual(run["locked_rate"], run["locked_choices"] / run["offered_choices"])
            self.assertEqual(run["fallback_share"], run["fallback_count"] / run["steps"])
            self.assertEqual(run["steps"], len(run["trace"]))

    def test_loop_guard_fails_instead_of_fabricating_a_result(self):
        with patch("game.balance.MAX_STEPS", 0):
            with self.assertRaisesRegex(RuntimeError, "超过"):
                run_life(0, "ordinary", "cautious")


if __name__ == "__main__":
    unittest.main()
