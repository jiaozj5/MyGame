"""Regressions for the actual v0.3 yearly economy and interruption boundary."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from game.engine import AGES, LifeGame, RECOVERY_COOLDOWN_YEARS, RuleError, VERSION


FIXTURE = Path(__file__).parent / "fixtures" / "v02-save.json"


def adult():
    game = LifeGame.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    game.state["status"]["job"] = "worker"
    game.state["stats"].update(cash=30000, energy=65, stress=36, health=85)
    game._update_budget()
    return game


def neutral_event(game):
    """A no-cost decision isolates the real across-year transaction."""
    game.state["current_event"] = {
        "id": f"test.continue.{game.state['slot_index']}", "title": "继续生活", "category": "日常", "scene": "town",
        "age_min": game.state["age"], "age_max": game.state["age"], "actors": [], "requires": [],
        "once": True, "_kind": "slot", "text": "按当前安排继续这一段生活。",
        "choices": [{"id": cid, "label": label, "requires": [], "effects": [], "observations": [], "outcome": "你继续当前的安排。"}
                    for cid, label in (("continue", "继续"), ("acknowledge", "记下近况"))]}


def next_year(game):
    game.state["age"] += 1
    game.state["year"] += 1
    game._annual()


class SurvivalV03Tests(unittest.TestCase):
    def test_paces_have_real_income_recovery_and_strain_tradeoffs(self):
        baseline = adult()
        results = {}
        for pace in ("steady", "push", "rest"):
            game = LifeGame.from_dict(baseline.to_dict())
            game.state["flags"]["work_pace"] = pace
            projection = game.view()["outlook"]
            before = deepcopy(game.state["stats"])
            next_year(game)
            annual = game.state["timeline"][-1]
            self.assertEqual(projection["income"], annual["accounting"]["income"])
            self.assertEqual(projection["expenses"], annual["accounting"]["expenses"])
            self.assertEqual(projection["energy_change"], game.state["stats"]["energy"] - before["energy"])
            self.assertEqual(projection["stress_change"], game.state["stats"]["stress"] - before["stress"])
            self.assertEqual(annual["stats_after"], game.state["stats"])
            results[pace] = projection
        self.assertGreater(results["push"]["income"], results["steady"]["income"])
        self.assertGreater(results["steady"]["income"], results["rest"]["income"])
        self.assertLess(results["push"]["energy_change"], results["steady"]["energy_change"])
        self.assertGreater(results["rest"]["energy_change"], results["steady"]["energy_change"])
        self.assertGreater(results["push"]["stress_change"], results["steady"]["stress_change"])
        self.assertLess(results["rest"]["stress_change"], results["steady"]["stress_change"])

    def test_steady_budget_and_resources_do_not_automatically_saturate(self):
        game = adult()
        for _ in range(8):
            next_year(game)
        self.assertGreater(game.state["stats"]["cash"], 30000)
        self.assertGreater(game.state["stats"]["energy"], 35)
        self.assertLess(game.state["stats"]["energy"], 90)
        self.assertGreater(game.state["stats"]["stress"], 15)
        self.assertLess(game.state["stats"]["stress"], 65)
        gig = adult()
        gig.state["status"]["job"] = "none"
        self.assertLess(gig.view()["outlook"]["balance"], 0)

    def test_push_history_records_completed_years_not_intentions(self):
        game = adult()
        game._apply({"op": "flag", "key": "work_pace", "value": "push"}, game.state["current_event"], [])
        self.assertEqual(game.state["flags"]["work_push_years"], 0)
        self.assertFalse(game.state["flags"]["work_push_seen"])
        for _ in range(3):
            next_year(game)
        self.assertEqual(game.state["flags"]["work_push_years"], 3)
        self.assertTrue(game.state["flags"]["work_push_seen"])
        self.assertLess(game.state["stats"]["health"], 85)
        with self.assertRaisesRegex(RuleError, "年度结算"):
            game._apply({"op": "flag", "key": "work_push_years", "value": 99}, game.state["current_event"], [])

    def test_danger_interrupts_between_slots_and_zero_cash_recovery_resumes(self):
        game = adult()
        game.state["flags"]["work_pace"] = "push"
        game.state["stats"].update(energy=30, stress=60, health=45)
        while AGES[game.state["slot_index"] + 1] == game.state["age"]:
            neutral_event(game)
            game.choose("continue", game.state["revision"])
        neutral_event(game)
        expected_slot = game.state["slot_index"] + 1
        target_age = AGES[expected_slot]
        game.choose("continue", game.state["revision"])
        self.assertEqual(game.state["current_event"]["_kind"], "recovery")
        self.assertLess(game.state["age"], target_age)
        self.assertEqual(game.state["slot_index"], expected_slot)
        crisis_year = game.state["year"]
        game.state["stats"]["cash"] = 0
        choices = {choice["id"]: choice for choice in game.view()["event"]["choices"]}
        self.assertTrue(choices["recovery_steady"]["available"])
        self.assertTrue(choices["recovery_rest"]["available"])
        self.assertFalse(choices["recovery_care"]["available"])
        saved = game.to_dict()
        game = LifeGame.from_dict(saved)
        game.choose("recovery_steady", game.state["revision"])
        self.assertEqual(game.state["slot_index"], expected_slot)
        self.assertEqual(game.state["age"], target_age)
        self.assertEqual(game.state["survival"]["adjustment_count"], 1)
        self.assertEqual(game.state["survival"]["cooldown_until"], crisis_year + RECOVERY_COOLDOWN_YEARS)
        self.assertNotEqual(game.state["current_event"]["_kind"], "recovery")

    def test_ignoring_a_recovery_opportunity_can_end_life_early(self):
        game = adult()
        game.state["stats"].update(health=7, energy=10, stress=95)
        game.state["flags"]["work_pace"] = "push"
        game._select_event()
        self.assertEqual(game.state["current_event"]["_kind"], "recovery")
        while not game.state["finished"]:
            if game.state["current_event"]["_kind"] == "recovery":
                game.choose("recovery_keep", game.state["revision"])
            else:
                neutral_event(game)
                game.choose("continue", game.state["revision"])
            self.assertLess(game.state["revision"], 20)
        self.assertLess(game.state["age"], 82)
        self.assertEqual(game.state["stats"]["health"], 0)
        self.assertIsNone(game.state["current_event"])
        self.assertEqual(game.state["timeline"][-1]["kind"], "death")
        self.assertIsNotNone(game.view()["biography"])

    def test_real_v02_save_migration_preserves_history_offer_and_random_progress(self):
        legacy = json.loads(FIXTURE.read_text(encoding="utf-8"))
        before = deepcopy(legacy)
        game = LifeGame.from_dict(legacy)
        for key in ("timeline", "current_event", "random_counter", "seed", "stats", "revision", "used_events"):
            self.assertEqual(game.state[key], legacy["state"][key], key)
        self.assertEqual(game.state["flags"]["work_pace"], "steady")
        self.assertEqual(game.state["flags"]["work_push_years"], 0)
        self.assertTrue(game.view()["migration_note"])
        self.assertEqual(game.to_dict()["schema_version"], VERSION)
        self.assertEqual(legacy, before)
        restored = LifeGame.from_dict(json.loads(json.dumps(game.to_dict())))
        self.assertEqual(restored.to_dict(), game.to_dict())
        selected = next(c["id"] for c in game.view()["event"]["choices"] if c["available"])
        game.choose(selected, game.state["revision"])
        restored.choose(selected, restored.state["revision"])
        self.assertEqual(restored.to_dict(), game.to_dict())

    def test_unsupported_versions_and_invalid_paces_are_rejected(self):
        legacy = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for target, key, value in (("save", "schema_version", "0.9.0"), ("state", "version", "0.9.0"),
                                   ("state", "content_version", "0.1.0"), ("state", "content_version", "0.3.0")):
            bad = deepcopy(legacy)
            (bad if target == "save" else bad["state"])[key] = value
            with self.assertRaises(RuleError):
                LifeGame.from_dict(bad)
        bad = adult().to_dict()
        bad["state"]["flags"]["work_pace"] = "unlimited"
        with self.assertRaises(RuleError):
            LifeGame.from_dict(bad)

    def test_causal_links_only_use_recorded_flag_effects(self):
        game = LifeGame.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
        legacy_flags = [key for key, value in game.state["flags"].items() if value is True]
        old = {"requires": [{"path": f"flags.{key}", "op": "eq", "value": True} for key in legacy_flags]}
        self.assertEqual(game._causes(old), [])
        neutral_event(game)
        game.state["current_event"]["choices"][0]["effects"] = [{"op": "flag", "key": "test_new_project", "value": True}]
        game.choose("continue", game.state["revision"])
        decision = next(row for row in reversed(game.state["timeline"]) if row["kind"] == "choice")
        self.assertEqual(decision["gained_flags"], {"test_new_project": True})
        causes = game._causes({"requires": [{"path": "flags.test_new_project", "op": "eq", "value": True}]})
        self.assertEqual([row["id"] for row in causes], [decision["id"]])


if __name__ == "__main__":
    unittest.main()
