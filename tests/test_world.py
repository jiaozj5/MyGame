"""World history, independent randomness, migration and life integration."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from game import world
from game.engine import LifeGame, RuleError, VERSION, _event_contract


def event(eid="test.growth", requires=None, effects=None, cooldown=0, once=False):
    return {"id": eid, "domain": "economy", "scope": "national", "title": eid,
            "text": "地方之间达成了一项新安排。", "requires": requires or [], "weight": 1,
            "cooldown": cooldown, "once": once, "severity": 1, "tags": [],
            "effects": effects if effects is not None else [{"op": "metric", "key": "prosperity", "delta": 3}]}


def catalog(*events):
    return {"version": world.VERSION, "domains": [{"id": "economy", "label": "经济", "scope": "national", "description": "经济活动"}],
            "events": list(events)}


class WorldRuleTests(unittest.TestCase):
    def test_derived_seeds_are_safe_javascript_integers(self):
        for seed in [*range(100), -(2**53 - 1), 2**53 - 1, 1988]:
            derived = world.new_world(seed, 1)["seed"]
            self.assertLessEqual(derived, 2**53 - 1)
            self.assertEqual(int(float(derived)), derived)

    def test_batched_stepped_and_json_resumed_worlds_match(self):
        data = catalog(event("a"), event("b", effects=[{"op": "metric", "key": "cost_pressure", "delta": -2}]))
        start = world.new_world(18, 1)
        direct = world.advance_world(start, 83, data)
        step = start
        for year in range(2, 84):
            step = world.advance_world(step, year, data)
        resumed = json.loads(json.dumps(world.advance_world(start, 30, data)))
        self.assertEqual(direct, world.advance_world(resumed, 83, data))
        self.assertEqual(direct, world.advance_world(start, 83, {**data, "events": list(reversed(data["events"]))}))
        self.assertEqual(direct, step)
        self.assertEqual(start["history"], [])
        self.assertEqual(start["year"], 1)
        self.assertEqual(len(direct["history"]), 41)
        self.assertTrue(all(row["year"] <= direct["year"] for row in direct["history"]))

    def test_cooldown_once_and_rechecked_facility_state(self):
        built = {"path": "world.flags.grid_alive", "op": "eq", "value": True}
        destroyed = {"path": "world.flags.destroyed", "op": "eq", "value": True}
        data = catalog(
            event("build", [{"path": "world.flags.grid_alive", "op": "ne", "value": True}],
                  [{"op": "flag", "key": "grid_alive", "value": True}], once=True),
            event("destroy", [built], [{"op": "flag", "key": "grid_alive", "value": False},
                                      {"op": "flag", "key": "destroyed", "value": True}], once=True),
            event("after", [destroyed], cooldown=6))
        state = world.advance_world(world.new_world(2, 1), 17, data)
        ids = [row["event_id"] for row in state["history"]]
        self.assertEqual(ids, ["build", "destroy", "after", "after"])
        self.assertEqual([row["year"] for row in state["history"]], [3, 5, 7, 13])
        self.assertFalse(state["flags"]["grid_alive"])
        self.assertEqual(state["history"][1]["causes"], ["world-1"])
        world.validate_world(state, data)

    def test_metrics_clip_actual_change_and_modes_remain_exclusive(self):
        data = catalog(event(effects=[{"op": "metric", "key": "prosperity", "delta": 30},
                                     {"op": "mode", "key": "energy", "value": "distributed"}]))
        state = world.advance_world(world.new_world(7, 1), 11, data)
        self.assertEqual(state["metrics"]["prosperity"], 100)
        self.assertEqual(state["history"][-1]["changes"][0], "经济活力 +0")
        self.assertEqual(state["modes"]["energy"], "distributed")
        self.assertEqual(set(state["modes"]), set(world.MODES))

    def test_invalid_catalog_and_world_rejected_without_mutation(self):
        data = catalog(event())
        state = world.advance_world(world.new_world(3, 1), 9, data)
        original = deepcopy(state)
        with self.assertRaises(world.WorldError):
            world.advance_world(state, 8, data)
        self.assertEqual(state, original)
        for mutate in (lambda s: s["metrics"].update(prosperity=101),
                       lambda s: s["metrics"].update(prosperity=s["metrics"]["prosperity"] - 1),
                       lambda s: s["history"][0].update(year=11),
                       lambda s: s["history"][0].update(causes=["world-2"]),
                       lambda s: s.update(random_counter=99),
                       lambda s: s["modes"].update(energy="unknown")):
            bad = deepcopy(state)
            mutate(bad)
            with self.assertRaises(world.WorldError):
                world.validate_world(bad, data)
        for invalid in (event(effects=[{"op": "metric", "key": "prosperity", "delta": 31}]),
                        event(requires=[{"path": "world.flags.misspelled", "op": "eq", "value": True}]),
                        event(effects=[{"op": "mode", "key": "energy", "value": "future"}])):
            with self.assertRaises(world.WorldError):
                world.advance_world(state, 11, catalog(invalid))
        self.assertEqual(state, original)

    def test_modifiers_bounded_and_view_has_only_past(self):
        state = world.new_world(4, 1)
        for _ in range(100):
            state["metrics"] = {key: random.Random(f"{_}:{key}").randint(0, 100) for key in world.METRICS}
            modifiers = world.modifiers(state)
            self.assertTrue(80 <= modifiers["income_percent"] <= 120)
            self.assertTrue(82 <= modifiers["expense_percent"] <= 125)
        state = world.advance_world(world.new_world(4, 1), 6, catalog(event()))
        public = world.world_view(state, catalog(event()))
        self.assertEqual([row["year"] for row in public["history"]], [3, 5])
        self.assertNotIn("contract", public["history"][0])
        self.assertEqual(len(public["metrics"]), 20)
        self.assertEqual({m["direction"] for m in public["metrics"]}, {"positive", "negative"})
        public["history"][0]["title"] = "外部改写"
        self.assertNotEqual(public["history"][0]["title"], state["history"][0]["title"])


class WorldLifeTests(unittest.TestCase):
    def test_browser_number_roundtrip_can_resume_and_continue(self):
        for seed in (0, 66, 1988, 2**53 - 1):
            original = LifeGame.new(seed=seed)
            # JS numbers use binary64 even when JSON contains integer tokens.
            browser_save = json.loads(json.dumps(original.to_dict()), parse_int=lambda value: int(float(value)))
            restored = LifeGame.from_dict(browser_save)
            self.assertEqual(restored.to_dict(), original.to_dict())
            choice = next(item["id"] for item in original.view()["event"]["choices"] if item["available"])
            for game in (original, restored):
                game.choose(choice, game.state["revision"])
            self.assertEqual(restored.to_dict(), original.to_dict())

    def test_old_real_saves_keep_history_current_choice_and_rng(self):
        for filename in ("v02-save.json", "v03-save.json"):
            save = json.loads((Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8"))
            before = deepcopy(save)
            game = LifeGame.from_dict(save)
            self.assertEqual(save, before)
            self.assertEqual(game.state["timeline"], save["state"]["timeline"])
            self.assertEqual(game.state["current_event"], save["state"]["current_event"])
            self.assertEqual(game.state["random_counter"], save["state"]["random_counter"])
            self.assertEqual(game.state["year"], save["state"]["year"])
            self.assertEqual(game.state["world"]["start_year"], game.state["year"])
            self.assertEqual(game.state["world"]["history"], [])
            self.assertEqual(game.view()["world"]["calendar"], "旧档纪年")
            self.assertEqual(game.to_dict()["schema_version"], VERSION)
            self.assertEqual(LifeGame.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_new_calendar_relative_npcs_and_readonly_view(self):
        game = LifeGame.new(seed=66)
        self.assertEqual(game.state["born_year"], 1)
        self.assertEqual(game.state["year"], 7)
        self.assertEqual([game.state["npcs"][pid]["age"] for pid in ("mother", "father", "friend", "partner")], [30, 33, 6, 5])
        before = game.to_dict()
        self.assertEqual(game.view()["world"]["calendar"], "新历")
        game.view()
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(LifeGame.from_dict(before).to_dict(), before)

    def test_player_random_calls_do_not_change_macro_history(self):
        a = LifeGame.new(seed=91)
        b = LifeGame.new(seed=91)
        for _ in range(200):
            b._draw()
        for game in (a, b):
            game.state["world"] = world.advance_world(game.state["world"], 45, game.catalog["world_catalog"])
        self.assertEqual(a.state["world"], b.state["world"])

    def test_actual_different_lives_share_world_prefix(self):
        lives = []
        for reverse in (False, True):
            game = LifeGame.new(seed=31)
            for _ in range(85):
                if game.state["finished"]:
                    break
                available = [choice for choice in game.state["current_event"]["choices"]
                             if game._choice_result(game.state["current_event"], choice)[0] is not None]
                choice = available[-1 if reverse else 0]
                game.choose(choice["id"], game.state["revision"])
            self.assertTrue(game.state["finished"])
            if game.state["age"] == 82 and game.state["death_reason"] != "健康耗尽":
                self.assertIn("later.life_review", game.state["used_events"])
            lives.append(game)
        horizon = min(game.state["year"] for game in lives)
        prefixes = [[row for row in game.state["world"]["history"] if row["year"] <= horizon] for game in lives]
        self.assertEqual(*prefixes)
        self.assertTrue(all(row["year"] <= horizon for row in prefixes[0]))

    def test_world_conditions_and_player_write_boundary(self):
        game = LifeGame.new(seed=4)
        self.assertEqual(game._path("world.metrics.prosperity"), game.state["world"]["metrics"]["prosperity"])
        self.assertFalse(game._path("world.flags.unknown"))
        event_copy = deepcopy(game.state["current_event"])
        event_copy["choices"][0]["effects"] = [{"op": "flag", "key": "world.metrics.prosperity", "value": 100}]
        with self.assertRaises(RuleError):
            _event_contract(event_copy)
        before = deepcopy(game.state["world"])
        self.assertIsNone(game._choice_result(event_copy, event_copy["choices"][0])[0])
        self.assertEqual(game.state["world"], before)

    def test_annual_settlement_uses_current_macro_forecast_function(self):
        save = json.loads((Path(__file__).parent / "fixtures" / "v03-save.json").read_text(encoding="utf-8"))
        game = LifeGame.from_dict(save)
        game.state["stats"].update(cash=100000, health=85, energy=65, stress=35)
        game.state["status"]["job"] = "worker"
        before = game._annual_plan(game.state["age"] + 1)
        game.state["age"] += 1
        game.state["year"] += 1
        game._annual()
        row = game.state["timeline"][-1]
        self.assertEqual(row["accounting"]["income"], before["income"])
        self.assertEqual(row["accounting"]["expenses"], before["expenses"])
        self.assertEqual(row["annual_plan"]["world_modifiers"], world.modifiers(game.state["world"]))
        self.assertTrue(any("未来世界变化" in warning for warning in game.view()["outlook"]["warnings"]))

    def test_every_third_slot_prefers_society_but_preserves_first_job(self):
        game = LifeGame.new(seed=5)
        while game.state["slot_index"] < 2:
            current = game.state["current_event"]
            chosen = next(choice for choice in current["choices"] if game._choice_result(current, choice)[0] is not None)
            game.choose(chosen["id"], game.state["revision"])
        template = deepcopy(game.state["current_event"])
        template.update(age_min=0, age_max=82, actors=[], requires=[])
        template.pop("world_domain", None)
        for choice in template["choices"]:
            choice.update(requires=[], effects=[], observations=[])
        ordinary = deepcopy(template)
        ordinary["id"] = "test.ordinary"
        society = deepcopy(template)
        society.update(id="test.society", world_domain="economy")
        society["requires"] = [{"path": "world.metrics.prosperity", "op": "gte", "value": 0}]
        game.catalog = {**game.catalog, "events": [ordinary, society]}
        game._select_event()
        self.assertEqual(game.state["current_event"]["id"], "test.society")
        job = deepcopy(template)
        job["id"] = "youth.career_entry"
        game.catalog["events"].append(job)
        game._select_event()
        self.assertEqual(game.state["current_event"]["id"], "youth.career_entry")

    def test_world_context_contains_related_facts_but_never_future(self):
        data = catalog(event(effects=[{"op": "flag", "key": "grid_alive", "value": True}]))
        state = world.advance_world(world.new_world(8, 1), 7, data)
        relevant = world.event_context(state, "energy", requires=[{"path": "world.flags.grid_alive", "op": "eq", "value": True}])
        self.assertEqual([row["year"] for row in relevant], [7, 5, 3])
        self.assertTrue(all(set(row) == {"id", "title", "year"} for row in relevant))
        self.assertEqual(world.event_context(state, "other"), [])


if __name__ == "__main__":
    unittest.main()
