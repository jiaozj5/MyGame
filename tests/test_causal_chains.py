"""Local contracts for the sixteen v0.3 content additions.

The scenarios below state their history flags explicitly. They do not simulate
that history and cannot prove the scheduler will reach every branch in a run.
"""

import unittest

from game.engine import LifeGame, _event_contract
from game.population import new_population, sync_anchors
from game.world import advance_world


# Independent authored scenarios, not flags inferred from each event's rules.
SCENARIOS = {
    "teen.repair_request": (18, {"repair_interest": True}),
    "adult.repair_referral": (30, {"repair_project_completed": True}),
    "teen.reading_circle": (18, {"library_card": True, "school_interest": True}),
    "adult.study_recommendation": (30, {"reading_project": True, "qualification": True}),
    "adult.returned_support": (34, {"friend_support": True}),
    "adult.friend_boundary": (42, {"mutual_support": True}),
    "adult.home_check": (38, {"home_goal": True, "settled_home": False}),
    "adult.shared_budget": (46, {"settled_home": True, "budget_reviewed": True, "partnered": True}),
    "adult.work_pace": (26, {"work_pace_chosen": False}),
    "adult.pace_reflection": (38, {"work_pace": "push", "work_push_seen": True, "work_push_years": 4}),
    "later.mentor_return": (65, {"mentor": True}),
    "later.single_network": (65, {"emergency_fund": True, "partnered": False, "has_child": False}),
    "later.neighbor_checkin": (70, {"support_circle_confirmed": True}),
    "later.river_notebook": (70, {"shared_notes": True}),
    "later.community_handover": (65, {"community_participant": True}),
    "later.quiet_accounts": (75, {"retirement_planned": True, "budget_reviewed": True}),
}

PREDECESSORS = {
    "teen.repair_request": "repair_interest",
    "adult.repair_referral": "repair_project_completed",
    "teen.reading_circle": "library_card",
    "adult.study_recommendation": "reading_project",
    "adult.returned_support": "friend_support",
    "adult.friend_boundary": "mutual_support",
    "adult.home_check": "home_goal",
    "adult.shared_budget": "budget_reviewed",
    "adult.pace_reflection": "work_push_seen",
    "later.mentor_return": "mentor",
    "later.single_network": "emergency_fund",
    "later.neighbor_checkin": "support_circle_confirmed",
    "later.river_notebook": "shared_notes",
    "later.community_handover": "community_participant",
    "later.quiet_accounts": "retirement_planned",
}


class CausalContentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = LifeGame.new(seed=303)
        catalog = {event["id"]: event for event in cls.base.catalog["events"]}
        cls.events = {event_id: catalog[event_id] for event_id in SCENARIOS}

    def scenario(self, event_id):
        age, flags = SCENARIOS[event_id]
        game = LifeGame(self.base.state, self.base.catalog)
        state = game.state
        state.update(age=age, year=state["born_year"] + age)
        state["world"] = advance_world(state["world"], state["year"], game.catalog["world_catalog"])
        state["stats"].update(cash=100000, energy=90, health=90, stress=35,
                              education=90, skill=90)
        state["status"]["job"] = "retired" if age >= 65 else "worker"
        state["flags"].update(flags)
        for npc in state["npcs"].values():
            npc["age"] = state["year"] - npc["birth_year"]
        if state["flags"].get("partnered"):
            state["flags"]["partner_met"] = True
            state["npcs"]["partner"]["met"] = True
        # This fixture intentionally jumps to a local authored scenario. Start
        # its population there; do not fabricate intervening NPC histories.
        # Only the four actors are needed for this content-contract test.
        state["population"] = new_population(state["seed"], state["year"], state["npcs"],
                                             size=4, focus_limit=4)
        game._update_budget()
        game._validate(check_event=False)
        return game

    def test_the_authored_subset_has_sixteen_events_and_forty_eight_choices(self):
        self.assertEqual(len(self.events), 16)
        self.assertEqual(sum(len(e["choices"]) for e in self.events.values()), 48)
        for event_id, event in self.events.items():
            with self.subTest(event=event_id):
                _event_contract(event)
                self.assertEqual(len(event["choices"]), 3)
                self.assertTrue(all(len(c.get("observations", [])) <= 2
                                    for c in event["choices"]))

    def test_sufficient_local_resources_allow_all_forty_eight_choices(self):
        tried = 0
        for event_id, event in self.events.items():
            game = self.scenario(event_id)
            with self.subTest(event=event_id):
                self.assertTrue(game._eligible(event))
            available = 0
            for choice in event["choices"]:
                with self.subTest(event=event_id, choice=choice["id"]):
                    candidate, result = game._choice_result(event, choice)
                    self.assertIsNotNone(candidate, result)
                    available += candidate is not None
                    tried += 1
            self.assertGreater(available, 0, event_id)
        self.assertEqual(tried, 48)

    def test_zero_cash_and_energy_still_leave_an_executable_option(self):
        for event_id, event in self.events.items():
            with self.subTest(event=event_id):
                game = self.scenario(event_id)
                game.state["stats"].update(cash=0, energy=0)
                self.assertTrue(game._eligible(event))
                self.assertTrue(any(game._choice_result(event, choice)[0] is not None
                                    for choice in event["choices"]))

    def test_missing_predecessors_block_fifteen_followups(self):
        self.assertEqual(set(PREDECESSORS), set(SCENARIOS) - {"adult.work_pace"})
        for event_id, flag in PREDECESSORS.items():
            with self.subTest(event=event_id, missing=flag):
                game = self.scenario(event_id)
                event = self.events[event_id]
                self.assertTrue(game._eligible(event))
                game.state["flags"].pop(flag)
                self.assertFalse(game._eligible(event))

    def test_deceased_required_actors_cannot_participate(self):
        checked = 0
        for event_id, event in self.events.items():
            for actor_id in event["actors"]:
                with self.subTest(event=event_id, deceased=actor_id):
                    game = self.scenario(event_id)
                    self.assertTrue(game._eligible(event))
                    game._npc_death(actor_id)
                    game.state["population"] = sync_anchors(game.state["population"], game.state["npcs"], game.state["year"])
                    self.assertFalse(game._eligible(event))
                    self.assertTrue(all(game._choice_result(event, choice)[0] is None
                                        for choice in event["choices"]))
                    checked += 1
        self.assertEqual(checked, 3)


if __name__ == "__main__":
    unittest.main()
