from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from game.engine import LifeGame, _event_contract
from game.world import INITIAL_MODES, METRICS


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "content/society-events.json").read_text(encoding="utf-8"))


def fixture(event, *, cash=5000, energy=50):
    """Only the state surface used by eligibility and ordinary effects is needed."""
    state = {"age": event["age_min"], "year": event["age_min"] + 1, "origin": "ordinary",
             "stats": {"cash": cash, "energy": energy, "health": 60, "stress": 30,
                       "education": 20, "skill": 20}, "flags": {}, "loans": [],
             "status": {"job": "none", "income": 0, "expenses": 0},
             "npcs": {pid: {"id": pid, "name": pid, "alive": True, "met": True,
                             "closeness": 50, "cash": 1000} for pid in ("mother", "father", "friend", "partner")},
             "world": {"metrics": {key: 50 for key in METRICS}, "modes": dict(INITIAL_MODES)}}
    for condition in event["requires"]:
        parts = condition["path"].split(".")
        current = {"world": state["world"], "flags": state["flags"], "npc": state["npcs"]}
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = condition["value"]
    return LifeGame(state, {"events": [event]})


class SocietyContentTests(unittest.TestCase):
    def test_twenty_domains_have_three_scopes_and_valid_personal_contracts(self):
        domains = {item["id"] for item in json.loads((ROOT / "content/world-events.json").read_text(encoding="utf-8"))["domains"]}
        self.assertEqual(CATALOG["version"], "0.4.0")
        self.assertEqual(len(CATALOG["events"]), 60)
        self.assertEqual(Counter(event["world_domain"] for event in CATALOG["events"]), Counter({domain: 3 for domain in domains}))
        self.assertEqual(len({event["id"] for event in CATALOG["events"]}), 60)
        for domain in domains:
            self.assertEqual({event["response_scope"] for event in CATALOG["events"] if event["world_domain"] == domain},
                             {"personal", "family", "community"})
        for event in CATALOG["events"]:
            with self.subTest(event=event["id"]):
                _event_contract(event)
                self.assertEqual(len(event["choices"]), 3)
                self.assertGreaterEqual(event["age_min"], 6)
                self.assertLessEqual(event["age_max"], 82)

    def test_world_threshold_is_a_real_gate_and_not_a_fixed_year(self):
        for event in CATALOG["events"]:
            with self.subTest(event=event["id"]):
                game = fixture(event)
                self.assertTrue(game._eligible(event))
                gates = [condition for condition in event["requires"] if condition["path"].startswith(("world.metrics.", "world.modes."))]
                self.assertTrue(gates)
                self.assertFalse(any(condition["path"] == "year" for condition in event["requires"]))
                gate = gates[0]
                _, group, key = gate["path"].split(".")
                if gate["op"] == "gte":
                    game.state["world"][group][key] = gate["value"] - 1
                elif gate["op"] == "lte":
                    game.state["world"][group][key] = gate["value"] + 1
                else:
                    game.state["world"][group][key] = "a_different_mode"
                self.assertFalse(game._eligible(event))

    def test_each_event_has_an_executable_zero_cash_zero_energy_response(self):
        for event in CATALOG["events"]:
            with self.subTest(event=event["id"]):
                successful = []
                for choice in event["choices"]:
                    game = fixture(event, cash=0, energy=0)
                    if any(game._condition_reason(condition) is not None for condition in choice["requires"]):
                        continue
                    before_world = deepcopy(game.state["world"])
                    for effect in choice["effects"]:
                        game._apply(effect, event, [])
                    self.assertEqual(game.state["world"], before_world)
                    self.assertGreaterEqual(game.state["stats"]["cash"], 0)
                    self.assertGreaterEqual(game.state["stats"]["energy"], 0)
                    successful.append(choice["id"])
                self.assertTrue(successful)

    def test_named_npcs_require_life_and_acquaintance_and_cannot_act_after_death(self):
        for event in CATALOG["events"]:
            required = {(condition["path"], condition["op"], condition["value"]) for condition in event["requires"]}
            for npc_id in event["actors"]:
                with self.subTest(event=event["id"], npc=npc_id):
                    self.assertIn((f"npc.{npc_id}.alive", "eq", True), required)
                    self.assertIn((f"npc.{npc_id}.met", "eq", True), required)
                    game = fixture(event)
                    game.state["npcs"][npc_id]["alive"] = False
                    self.assertFalse(game._eligible(event))
            if "partner" in event["actors"]:
                self.assertIn(("flags.partnered", "eq", True), required)
            for choice in event["choices"]:
                for effect in choice["effects"]:
                    self.assertNotIn(effect["op"], {"world_metric", "world_mode"})
                    self.assertFalse(effect.get("key", "").startswith("world."))
                    if "npc" in effect:
                        self.assertIn(effect["npc"], event["actors"])


if __name__ == "__main__":
    unittest.main()
