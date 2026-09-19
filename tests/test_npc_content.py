"""Local v0.5 NPC content contracts, not natural population coverage.

These authored fixtures state their occupations, resources and prior facts
explicitly. They do not replay the history that produced a pending case, and
cannot prove the ordinary population scheduler reaches all 32 interactions.
"""

from copy import deepcopy
import unittest

from game import population as rules
from game.world import BASE_METRICS


AXES = {
    "honesty", "empathy", "aggression", "dominance", "cooperativeness", "trust",
    "caution", "impulsivity", "sociability", "persistence", "openness", "fairness",
}
ACTOR, TARGET, OTHER = "npc-0001", "npc-0002", "npc-0003"

# Independent scenario inputs: changing an asset requirement does not silently
# change these fixtures to satisfy it.
SCENARIOS = {
    "bridge_expenses": {"actor": {"traits": {"empathy": 60}}, "target": {"stats": {"cash": 200}}},
    "care_respite": {"actor": {"stats": {"stress": 40}},
                     "target": {"occupation": "unpaid_caregiver", "stats": {"stress": 65}}},
    "learning_help": {"actor": {"occupation": "teacher", "stats": {"stress": 40}},
                      "target": {"occupation": "student", "age": 16}},
    "accompany_request": {"actor": {"stats": {"stress": 40}, "traits": {"cooperativeness": 60}},
                          "target": {"stats": {"stress": 70}}},
    "purchase_fulfilled": {"actor": {"occupation": "bookkeeper", "stats": {"cash": 600}},
                           "target": {"occupation": "cooperative_member"},
                           "edge": {"flags": {"entrusted_fund": True}}},
    "entrusted_purchase": {"actor": {"occupation": "bookkeeper"},
                           "target": {"occupation": "cooperative_member", "stats": {"cash": 800}}},
    "peer_study": {"actor": {"occupation": "student", "age": 16, "stats": {"stress": 40}},
                   "target": {"occupation": "student", "age": 16}},
    "delivery_handoff": {"actor": {"occupation": "delivery_worker", "stats": {"stress": 40}},
                         "target": {"occupation": "freight_dispatcher", "stats": {"cash": 200}}},
    "public_argument": {"actor": {"traits": {"aggression": 70}}, "edge": {"tension": 50}},
    "competing_shift": {"actor": {"stats": {"cash": 500}}, "target": {"stats": {"cash": 500}}},
    "favor_refused": {"actor": {"traits": {"dominance": 70}},
                      "target": {"stats": {"stress": 70}}, "edge": {"trust": 50}},
    "decision_boundary": {"actor": {"traits": {"aggression": 40}},
                          "target": {"traits": {"dominance": 75}}, "edge": {"affinity": 40}},
    "concealed_defect": {"actor": {"traits": {"honesty": 20}}, "target": {"stats": {"cash": 1000}}},
    "promise_betrayal": {"actor": {"traits": {"honesty": 25}},
                         "target": {"stats": {"cash": 500}}, "edge": {"affinity": 60}},
    "credit_stealing": {"actor": {"occupation": "project_coordinator",
                                   "traits": {"honesty": 30, "dominance": 70}}},
    "false_rumor": {"actor": {"traits": {"honesty": 20}},
                    "target": {"stats": {"reputation": 60}}, "edge": {"tension": 45}},
    "withheld_wages": {"actor": {"occupation": "business_owner", "traits": {"fairness": 20},
                                   "stats": {"cash": 300}}, "target": {"stats": {"cash": 100}}},
    "conditional_help": {"actor": {"traits": {"dominance": 85}},
                         "target": {"stats": {"cash": 300}},
                         "edge": {"flags": {"assistance_given": True}}},
    "humiliation": {"actor": {"traits": {"aggression": 75, "dominance": 75}},
                    "edge": {"affinity": 20}},
    "diverted_funds": {"actor": {"occupation": "bookkeeper", "traits": {"honesty": 20},
                                   "stats": {"cash": 800}},
                       "target": {"occupation": "cooperative_member"},
                       "edge": {"flags": {"entrusted_fund": True}}},
    "coerced_payment": {"actor": {"occupation": "public_clerk",
                                    "traits": {"honesty": 20, "dominance": 65}},
                        "target": {"occupation": "business_owner", "stats": {"cash": 600}}},
    "threat": {"actor": {"traits": {"aggression": 85, "dominance": 70}},
               "edge": {"tension": 50}},
    "physical_harm": {"actor": {"traits": {"aggression": 90, "impulsivity": 80}},
                      "target": {"stats": {"health": 70}},
                      "edge": {"flags": {"threat_pending": True}}},
    "false_corroboration": {"actor": {"traits": {"honesty": 20}},
                            "target": {"flags": {"under_review": True}}, "edge": {"affinity": 60}},
    "defect_refund": {"actor": {"stats": {"cash": 600}},
                      "edge": {"flags": {"fraud_pending": True}}},
    "promise_repayment": {"actor": {"stats": {"cash": 400}},
                          "edge": {"flags": {"promise_pending": True}}},
    "credit_correction": {"edge": {"flags": {"credit_claim_pending": True}}},
    "rumor_correction": {"edge": {"flags": {"rumor_pending": True}},
                         "world": {"knowledge_access": 60}},
    "wages_settled": {"actor": {"stats": {"cash": 500}}, "edge": {"flags": {"wages_pending": True}}},
    "funds_audited": {"actor": {"stats": {"cash": 1000}},
                      "edge": {"flags": {"fund_misappropriation_pending": True}},
                      "world": {"institutional_capacity": 60}},
    "coercion_boundary": {"edge": {"flags": {"coercion_pending": True}}},
    "harm_protection": {"edge": {"flags": {"injury_pending": True}},
                        "world": {"institutional_capacity": 60}},
}

PRIOR_FACTS = {
    "purchase_fulfilled": "entrusted_fund", "conditional_help": "assistance_given",
    "diverted_funds": "entrusted_fund", "physical_harm": "threat_pending",
    "defect_refund": "fraud_pending", "promise_repayment": "promise_pending",
    "credit_correction": "credit_claim_pending", "rumor_correction": "rumor_pending",
    "wages_settled": "wages_pending", "funds_audited": "fund_misappropriation_pending",
    "coercion_boundary": "coercion_pending", "harm_protection": "injury_pending",
}


def anchors():
    return {key: {"name": key, "birth_year": 1 if key in {"friend", "partner"} else -25,
                  "alive": True, "cash": 1000, "met": True, "closeness": 50, "role": key}
            for key in rules.ANCHORS}


class NpcContentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = rules.load_library()
        cls.events = {event["id"].removeprefix("npc."): event for event in cls.library["interactions"]}
        cls.jobs = {job["id"]: job for job in cls.library["occupations"]}
        cls.base = rules.new_population(17, 31, anchors(), library=cls.library, size=7, focus_limit=7)

    def fixture(self, event_id):
        pop = deepcopy(self.base)
        pop["_edited"] = set()
        for pid in (ACTOR, TARGET, OTHER):
            row = pop["people"][pid]
            row.update(status="alive", birth_year=1, death_year=None, occupation="shopkeeper",
                       event_years={}, flags={}, relations={})
            row["stats"] = {"cash": 3000, "health": 80, "stress": 50, "reputation": 50}
            row["traits"] = {axis: 50 for axis in AXES}
        edge = {"trust": 40, "affinity": 35, "tension": 10, "flags": {}, "last_event": None,
                "last_year": 31, "known": False, "known_label": "局部场景中的相识"}
        scenario = SCENARIOS[event_id]
        for role, pid in (("actor", ACTOR), ("target", TARGET)):
            row = pop["people"][pid]
            for key, value in scenario.get(role, {}).items():
                if key == "age":
                    row["birth_year"] = pop["year"] - value
                elif isinstance(value, dict):
                    row[key].update(value)
                else:
                    row[key] = value
            job = self.jobs[row["occupation"]]
            age = pop["year"] - row["birth_year"]
            self.assertLessEqual(job["min_age"], age)
            self.assertLessEqual(age, job["max_age"])
        edge.update(deepcopy(scenario.get("edge", {})))
        pop["people"][ACTOR]["relations"][TARGET] = edge
        metrics = dict(BASE_METRICS)
        metrics.update(scenario.get("world", {}))
        return pop, metrics

    def test_dictionary_shape_and_occupations_do_not_supply_moral_defaults(self):
        rules.validate_library(self.library)
        for group, size in (("occupations", 128), ("identities", 32), ("personality_axes", 12),
                            ("motivations", 12), ("interactions", 32)):
            with self.subTest(group=group):
                self.assertEqual(len(self.library[group]), size)
                self.assertEqual(len({row["id"] for row in self.library[group]}), size)
        self.assertEqual({axis["id"] for axis in self.library["personality_axes"]}, AXES)
        self.assertEqual(set(self.events), set(SCENARIOS))
        allowed = {"id", "label", "sector", "min_age", "max_age", "description", "income", "retirable"}
        for job in self.library["occupations"]:
            with self.subTest(occupation=job["id"]):
                self.assertLessEqual(set(job), allowed, "职业只提供经历和资源元数据，不能附带道德轴默认值")
                self.assertTrue(0 <= job["min_age"] <= job["max_age"] <= 120)
                self.assertGreaterEqual(job["income"], 0)
        self.assertTrue(self.library["names"]["family"])
        self.assertTrue(self.library["names"]["given"])

    def test_initial_traits_do_not_change_when_occupation_assignment_changes(self):
        alternate = deepcopy(self.library)
        alternate["occupations"].reverse()
        original = rules.new_population(91, 31, anchors(), library=self.library, size=64, focus_limit=64)
        reordered = rules.new_population(91, 31, anchors(), library=alternate, size=64, focus_limit=64)
        self.assertTrue(any(original["people"][pid]["occupation"] != reordered["people"][pid]["occupation"]
                            for pid in original["people"] if not original["people"][pid]["anchor"]),
                        "此反例必须实际改变至少一人的初始职业")
        for pid in original["people"]:
            with self.subTest(person=pid):
                self.assertEqual(original["people"][pid]["traits"], reordered["people"][pid]["traits"])

    def test_all_thirty_two_authored_local_interactions_execute(self):
        for event_id, event in self.events.items():
            with self.subTest(event=event_id):
                pop, metrics = self.fixture(event_id)
                before = pop["counters"]["interactions"]
                self.assertTrue(rules._eligible_interaction(pop, ACTOR, TARGET, event, metrics, self.library))
                self.assertTrue(rules._apply_interaction(pop, ACTOR, TARGET, event, metrics, self.library))
                self.assertEqual(pop["counters"]["interactions"], before + 1)
                for pid in (ACTOR, TARGET):
                    row = pop["people"][pid]
                    self.assertGreaterEqual(row["stats"]["cash"], 0)
                    self.assertTrue(all(0 <= row["stats"][key] <= 100 for key in ("health", "stress", "reputation")))
                    self.assertTrue(any(record.get("event_id") == event["id"]
                                        for record in row["history"] + row["recent"]))

    def test_twelve_directed_predecessors_reject_removal_role_reversal_and_another_target(self):
        self.assertEqual(len(PRIOR_FACTS), 12)
        for event_id, flag in PRIOR_FACTS.items():
            event = self.events[event_id]
            with self.subTest(event=event_id):
                pop, metrics = self.fixture(event_id)
                self.assertTrue(rules._eligible_interaction(pop, ACTOR, TARGET, event, metrics, self.library))
                original_edge = deepcopy(pop["people"][ACTOR]["relations"][TARGET])
                missing = deepcopy(pop)
                missing["people"][ACTOR]["relations"][TARGET]["flags"].pop(flag)
                self.assertFalse(rules._eligible_interaction(missing, ACTOR, TARGET, event, metrics, self.library))
                self.assertFalse(rules._eligible_interaction(pop, TARGET, ACTOR, event, metrics, self.library))
                # The substitute has the same age, job, resources and personal
                # flags. Only the specific directed prior fact is absent.
                other = deepcopy(pop)
                other["people"][OTHER] = deepcopy(other["people"][TARGET])
                other["people"][OTHER]["id"] = OTHER
                other["people"][ACTOR]["relations"][OTHER] = dict(original_edge, flags={})
                self.assertFalse(rules._eligible_interaction(other, ACTOR, OTHER, event, metrics, self.library))

    def test_every_interaction_rejects_a_dead_target_without_mutation(self):
        for event_id, event in self.events.items():
            with self.subTest(event=event_id):
                pop, metrics = self.fixture(event_id)
                pop["people"][TARGET].update(status="dead", death_year=30)
                before = deepcopy(pop)
                self.assertFalse(rules._eligible_interaction(pop, ACTOR, TARGET, event, metrics, self.library))
                self.assertFalse(rules._apply_interaction(pop, ACTOR, TARGET, event, metrics, self.library))
                self.assertEqual(pop, before)


if __name__ == "__main__":
    unittest.main()
