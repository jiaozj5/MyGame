from copy import deepcopy
import json
import random
import unittest

from prototype.engine import Engine, ROOT, RuleError, digest, load_engine, replay, validate_world


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = load_engine()
        self.initial = deepcopy(self.engine.state)
        self.catalog = deepcopy(self.engine.catalog)

    def request(self, engine=None):
        return (engine or self.engine).offer("friend.loan_request", {"player":"p", "friend":"f"})

    def loan(self, engine=None):
        return next(iter((engine or self.engine).state["loans"].values()))

    def test_transfer_creates_debt_and_preserves_total_cash(self):
        before = sum(p["cash"] for p in self.initial["persons"].values())
        self.engine.choose(self.request(), "lend_full")
        self.assertEqual(self.engine.state["persons"]["p"]["cash"], 200)
        self.assertEqual(self.engine.state["persons"]["f"]["cash"], 450)
        self.assertEqual(self.loan()["amount"], 400)
        self.assertEqual(sum(p["cash"] for p in self.engine.state["persons"].values()), before)
        self.assertTrue(self.engine.log[-1]["payload"]["below_housing_reserve_after"])

    def test_insufficient_money_locks_only_unaffordable_options(self):
        self.initial["persons"]["p"]["cash"] = 150
        engine = Engine(self.initial, self.catalog)
        options = {x["id"]:x for x in engine.choices(self.request(engine))}
        self.assertFalse(options["lend_full"]["available"])
        self.assertIn("150", options["lend_full"]["locked_reason"])
        self.assertTrue(options["lend_partial"]["available"])

    def test_failed_later_effect_rolls_back_whole_transaction(self):
        choice = self.catalog["events"][0]["choices"][0]
        choice["effects"].append({"op":"adjust", "actor":"player", "field":"energy", "delta":-100})
        engine = Engine(self.initial, self.catalog)
        before = deepcopy(engine.state)
        with self.assertRaises(RuleError):
            engine.choose(self.request(engine), "lend_full")
        self.assertEqual(engine.state, before)
        self.assertEqual(engine.log, [])

    def test_reward_cannot_finance_earlier_unaffordable_energy_cost(self):
        choice = self.catalog["events"][0]["choices"][2]
        choice["requirements"] = []
        choice["effects"] = [{"op":"adjust", "actor":"player", "field":"energy", "delta":-80}, {"op":"adjust", "actor":"player", "field":"energy", "delta":80}]
        engine = Engine(self.initial, self.catalog)
        with self.assertRaises(RuleError):
            engine.choose(self.request(engine), "help_search")
        self.assertEqual(engine.state, self.initial)

    def test_death_invalidates_cached_offer_and_cancels_plan(self):
        self.engine.choose(self.request(), "lend_full")
        self.engine.advance(30)
        stale = self.engine.available_events()[0]
        self.engine.mark_dead("f", "independent test event")
        with self.assertRaises(RuleError):
            self.engine.choose(stale, "accept_repayment")
        self.assertEqual(self.loan()["status"], "deceased_pending")
        self.assertEqual(self.engine.state["tasks"][0]["status"], "cancelled")
        self.assertEqual(self.engine.state["persons"]["p"]["cash"], 200)
        self.assertEqual([o.event_id for o in self.engine.available_events()], ["friend.old_letter"])

    def test_repaid_loan_stays_repaid_after_death(self):
        self.engine.choose(self.request(), "lend_partial")
        self.engine.advance(30)
        self.engine.choose(self.engine.available_events()[0], "accept_repayment")
        self.engine.mark_dead("f", "independent test event")
        self.assertEqual(self.loan()["status"], "repaid")

    def test_incorrect_life_dependency_is_rejected_when_loading(self):
        self.engine.choose(self.request(), "lend_full")
        state = deepcopy(self.engine.state)
        state["tasks"][0]["requires_alive"] = ["p", "m"]
        with self.assertRaises(RuleError):
            Engine(state, self.catalog)

    def test_keeping_letter_does_not_mark_it_read(self):
        self.engine.mark_dead("f", "test event")
        self.engine.choose(self.engine.available_events()[0], "keep")
        self.assertFalse(self.engine.state["facts"]["letter_read"])
        self.assertTrue(self.engine.state["facts"]["letter_handled"])

    def test_letter_cannot_contain_knowledge_acquired_after_writing(self):
        self.initial["persons"]["f"]["knowledge"]["shared_walk"] = 0
        with self.assertRaises(RuleError):
            Engine(self.initial, self.catalog)

    def test_relationships_have_inverse_edges_not_equal_trust(self):
        self.assertNotEqual(self.initial["relationships"][0]["trust"], self.initial["relationships"][1]["trust"])
        self.initial["relationships"].pop(1)
        with self.assertRaises(RuleError):
            Engine(self.initial, self.catalog)

    def test_scheduled_event_cannot_run_early_or_skip_due_date(self):
        self.engine.choose(self.request(), "lend_full")
        task = self.engine.state["tasks"][0]
        with self.assertRaises(RuleError):
            self.engine.offer("friend.loan_due", task["bindings"], task["id"])
        self.engine.advance(365)
        self.assertEqual(self.engine.state["day"], 30)
        with self.assertRaises(RuleError):
            self.engine.advance(1)

    def test_repayment_respects_npc_willingness(self):
        self.initial["persons"]["f"]["repayment_willing"] = False
        engine = Engine(self.initial, self.catalog)
        engine.choose(self.request(engine), "lend_full")
        engine.advance(30)
        offer = engine.available_events()[0]
        with self.assertRaises(RuleError):
            engine.choose(offer, "accept_repayment")
        engine.choose(offer, "extend")
        self.assertEqual(self.loan(engine)["due_day"], 37)
        self.assertEqual(engine.state["tasks"][0]["status"], "pending")

    def test_expired_age_condition_cancels_due_plan_without_erasing_debt(self):
        self.initial["persons"]["p"]["birth_day"] = -(25 * 365 - 15)
        self.catalog["events"][1]["age_range"] = [18, 24]
        engine = Engine(self.initial, self.catalog)
        engine.choose(self.request(engine), "lend_full")
        engine.advance(30)
        self.assertEqual(engine.state["tasks"][0]["status"], "cancelled")
        self.assertEqual(self.loan(engine)["status"], "outstanding")
        engine.advance(1)
        self.assertEqual(engine.state["day"], 31)

    def test_loaded_overdue_invalid_task_does_not_deadlock(self):
        self.engine.choose(self.request(), "lend_full")
        self.engine.advance(30)
        state = deepcopy(self.engine.state)
        self.catalog["events"][1]["age_range"] = [18, 20]
        engine = Engine(state, self.catalog)
        engine.advance(1)
        self.assertEqual(engine.state["tasks"][0]["status"], "cancelled")

    def test_missing_followup_dependency_is_rejected(self):
        self.catalog["events"].pop(1)
        with self.assertRaises(RuleError):
            Engine(self.initial, self.catalog)

    def test_only_one_feasible_choice_is_not_personality_evidence(self):
        self.initial["persons"]["p"].update(cash=0, energy=0)
        engine = Engine(self.initial, self.catalog)
        engine.choose(self.request(engine), "decline")
        self.assertFalse(engine.log[-1]["payload"]["opportunity"])
        self.assertEqual(engine.observations(), [])
        self.assertEqual(len([o for o in engine.log[-1]["payload"]["options"] if not o["available"]]), 3)

    def test_evidence_measures_actual_dynamic_transfer_cost(self):
        choice = self.catalog["events"][0]["choices"][0]
        choice["effects"][0]["amount"] = {"ref":"friend.cash"}
        choice["effects"][1]["amount"] = 50
        engine = Engine(self.initial, self.catalog)
        engine.choose(self.request(engine), "lend_full")
        self.assertEqual(engine.log[0]["payload"]["cash_cost"], 50)
        self.assertAlmostEqual(engine.log[0]["payload"]["cash_cost_share"], 50 / 600)

    def test_repeated_submit_cannot_charge_twice(self):
        offer = self.request()
        self.engine.choose(offer, "lend_full")
        before = deepcopy(self.engine.state)
        with self.assertRaises(RuleError):
            self.engine.choose(offer, "lend_full")
        self.assertEqual(self.engine.state, before)

    def test_replay_exactly_restores_and_detects_payload_change(self):
        self.engine.choose(self.request(), "lend_full")
        self.engine.advance(5)
        self.engine.mark_dead("f", "test event")
        self.assertEqual(replay(self.initial, self.engine.log), self.engine.state)
        corrupted = deepcopy(self.engine.log)
        corrupted[0]["payload"]["choice_id"] = "decline"
        with self.assertRaises(RuleError):
            replay(self.initial, corrupted)

    def test_template_resolves_bound_name_and_current_resources(self):
        self.initial["persons"]["f"]["name"] = "陈安"
        self.initial["persons"]["p"]["cash"] = 150
        engine = Engine(self.initial, self.catalog)
        description = engine.description(self.request(engine))
        self.assertIn("陈安", description)
        self.assertIn("150", description)
        self.assertNotIn("周远", description)

    def test_no_arbitrary_code_action_in_catalog(self):
        self.catalog["events"][0]["choices"][0]["effects"].append({"op":"execute_python", "code":"pass"})
        with self.assertRaises(RuleError):
            Engine(self.initial, self.catalog)

    def test_catalog_observations_have_documented_adapter(self):
        dimensions = json.loads((ROOT / "content/personality-dimensions.json").read_text(encoding="utf-8"))
        self.assertEqual(len({d["id"] for d in dimensions["dimensions"]}), 8)
        self.assertFalse(dimensions["output_policy"]["psychometric_scores"])
        categories = {d["id"]:set(d["behavior_categories"]) for d in dimensions["dimensions"]}
        adapter = dimensions["prototype_adapter"]
        mappings = next(value for value in adapter.values() if isinstance(value, list) and value and isinstance(value[0], dict) and "prototype_behavior" in value[0])
        lookup = {(m["dimension_id"],m["prototype_behavior"]):m["candidate_category"] for m in mappings}
        for event in self.catalog["events"]:
            for choice in event["choices"]:
                for observation in choice["evidence"]:
                    category = lookup[(observation["dimension_id"], observation["behavior"])]
                    self.assertIn(category, categories[observation["dimension_id"]])

    def test_300_seeded_paths_preserve_invariants_and_replay(self):
        for seed in range(300):
            rng = random.Random(seed)
            state = deepcopy(self.initial)
            state["persons"]["p"].update(cash=rng.randrange(901), energy=rng.randrange(101))
            state["persons"]["f"]["repayment_willing"] = rng.choice([True, False])
            engine = Engine(state, self.catalog)
            initial_total = sum(p["cash"] for p in state["persons"].values())
            for step in range(8):
                if step == 2 and rng.random() < 0.3 and engine.state["persons"]["f"]["alive"]:
                    engine.mark_dead("f", "seeded boundary test")
                offers = engine.available_events()
                if offers:
                    offer = rng.choice(offers)
                    choices = [c["id"] for c in engine.choices(offer) if c["available"]]
                    self.assertTrue(choices)
                    engine.choose(offer, rng.choice(choices))
                else:
                    engine.advance(rng.randint(1, 40))
                validate_world(engine.state)
                self.assertEqual(sum(p["cash"] for p in engine.state["persons"].values()), initial_total)
            self.assertEqual(digest(replay(state, engine.log)), digest(engine.state))


if __name__ == "__main__":
    unittest.main()
