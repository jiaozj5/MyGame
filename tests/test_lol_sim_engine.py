import copy
import unittest

from lol_sim.engine import LaneSimulation, ValidationError, optimize, simulate


def fixture_catalog():
    stats = {"hp": 650, "hpperlevel": 100, "mp": 300, "mpperlevel": 40,
             "attackdamage": 60, "attackdamageperlevel": 3, "armor": 35,
             "armorperlevel": 4, "spellblock": 32, "spellblockperlevel": 1.25,
             "attackspeed": .65, "attackspeedperlevel": 3, "hpregen": 8,
             "hpregenperlevel": .5, "mpregen": 7, "mpregenperlevel": .5,
             "attackrange": 125, "movespeed": 340}
    abilities = {
        "Q": {"damage": [10, 20, 30, 40, 50], "ad_ratio": [.5] * 5,
              "cooldown": [8] * 5, "cost": [0] * 5, "range": [250] * 5, "auto_reset": True},
        "W": {"damage": [0] * 5, "cooldown": [10] * 5, "cost": [0] * 5, "range": [250] * 5},
        "E": {"damage": [20, 30, 40, 50, 60], "ad_ratio": [.4] * 5,
              "cooldown": [10] * 5, "cost": [0] * 5, "range": [250] * 5},
        "R": {"damage": [100] * 3, "ad_ratio": [.5] * 3,
              "cooldown": [100] * 3, "cost": [0] * 3, "range": [500] * 3, "targeted": True},
    }
    return {"patch": "test", "champions": {
        name: {"stats": copy.deepcopy(stats), "abilities": copy.deepcopy(abilities), "sim_notes": []}
        for name in ("Garen", "Darius", "Jax", "Malphite")
    }, "items": {"1054": {"gold": {"total": 400}, "stats": {"hp": 80, "ap": 18}},
                    "2003": {"gold": {"total": 50}, "stats": {}}}}


class LaneEngineTests(unittest.TestCase):
    def config(self):
        return {"player": {"champion": "Garen", "items": ["1054", "2003"]},
                "opponent": {"champion": "Darius", "items": ["1054", "2003"]},
                "duration": 30, "seed": 3}

    def test_seeded_simulation_is_reproducible_and_inspectable(self):
        catalog = fixture_catalog()
        first = simulate(self.config(), catalog)
        second = simulate(self.config(), catalog)
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first["timeline"], second["timeline"])
        self.assertTrue(any(entry["event"] == "wave_spawn" for entry in first["timeline"]))
        self.assertGreaterEqual(len(first["snapshots"]), 1)
        self.assertIn("approximate", first["model"])

    def test_unknown_champion_is_rejected_instead_of_falling_back(self):
        config = self.config()
        config["player"]["champion"] = "Unknown"
        with self.assertRaises(ValidationError):
            simulate(config, fixture_catalog())

    def test_invalid_skill_order_is_rejected(self):
        config = self.config()
        config["player"]["skill_order"] = ["Q", "Q", "Q", "Q", "Q", "Q"]
        with self.assertRaises(ValidationError):
            simulate(config, fixture_catalog())

    def test_optimize_reports_all_seed_trials(self):
        catalog = fixture_catalog()
        config = self.config()
        config["search"] = {"runes": ["conqueror", "grasp"], "seeds": [3, 5]}
        result = optimize(config, catalog)
        self.assertEqual(result["search"]["candidates"], 2)
        self.assertEqual(result["search"]["trials"], 4)
        self.assertEqual(len(result["ranking"]), 2)
        self.assertEqual(result["best"], result["ranking"][0])

    def test_optimize_rejects_oversized_search(self):
        config = self.config()
        config["search"] = {"runes": ["conqueror"] * 257, "seeds": [1]}
        with self.assertRaises(ValidationError):
            optimize(config, fixture_catalog())

    def test_empty_catalog_does_not_silently_fallback_to_live_data(self):
        with self.assertRaises(ValidationError):
            simulate(self.config(), {})

    def test_empowered_attack_keeps_a_physical_basic_packet(self):
        catalog = fixture_catalog()
        config = self.config()
        config["mode"] = "duel"
        config["duration"] = 1
        config["player"]["skill_order"] = ["Q", "W", "Q", "E", "E", "R"]
        config["player"]["combo"] = ["Q"]
        sim = LaneSimulation(config, catalog)
        player, opponent = sim.fighters
        player.x, opponent.x = 500, 500
        player.ranks = {"Q": 1, "W": 0, "E": 0, "R": 0}
        sim._cast(player, opponent, "Q")
        packet_sources = [x["text"] for x in sim.timeline if x["event"] == "damage"]
        self.assertTrue(any("普攻" in x for x in packet_sources))
        self.assertTrue(any(x.startswith("Q ·") for x in packet_sources))

    def test_mirror_matchup_has_no_persistent_player_side_bias(self):
        config = self.config()
        config["opponent"] = copy.deepcopy(config["player"])
        config["duration"] = 30
        scores = []
        for seed in range(16):
            config["seed"] = seed
            scores.append(simulate(config, fixture_catalog())["summary"]["score"])
        self.assertLess(abs(sum(scores) / len(scores)), 40)


if __name__ == "__main__":
    unittest.main()
