"""Population boundaries: identity, knowledge, atomic actions and old history."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from game.engine import LifeGame, RuleError
from game.population_report import population_counts, visibility_counts


FIXTURES = Path(__file__).parent / "fixtures"


class PopulationReportCountingTests(unittest.TestCase):
    def test_simulation_detail_and_tracking_do_not_create_friendships(self):
        def person(contact, closeness, detailed):
            return {"status": "alive", "detailed": detailed,
                    "knowledge": {"contact": contact, "closeness": closeness,
                                  "ever_close": contact == "direct" and closeness >= 60}}
        pop = {"people": {"stranger": person("none", 0, True),
                          "heard_of": person("indirect", 90, True),
                          "acquaintance": person("direct", 20, False),
                          "close": person("direct", 65, False)},
               "tracked": ["heard_of"]}
        counts = population_counts(pop)
        self.assertEqual(counts["discovered"], 3)
        self.assertEqual(counts["direct"], 2)
        self.assertEqual(counts["close"], 1, "间接听说不等于亲密关系")
        self.assertEqual(counts["focus"], 1)
        self.assertEqual(counts["detailed"], 2)

    def test_former_closeness_is_kept_without_counting_a_deceased_person_as_a_current_close_contact(self):
        pop = {"people": {"old_friend": {"status": "dead", "detailed": True,
                                          "knowledge": {"contact": "direct", "closeness": 80,
                                                        "ever_close": True}}}, "tracked": ["old_friend"]}
        counts = population_counts(pop)
        self.assertEqual(counts["close"], 0)
        self.assertEqual(counts["close_ever_count"], 1)
        self.assertEqual(counts["direct"], 1)

    def test_visibility_counts_preserve_unknown_truth_and_deduplicate_retained_records(self):
        visible = {"id": "e1", "visibility": "participants", "known": True}
        hidden = {"id": "e2", "visibility": "private", "known": False}
        unknown_public = {"id": "e3", "visibility": "public", "known": False}
        pop = {"people": {
            "known": {"knowledge": {"contact": "direct"}, "history": [visible, hidden], "recent": [visible]},
            "unknown": {"knowledge": {"contact": "none"}, "history": [], "recent": [unknown_public]},
        }}
        result = visibility_counts(pop)
        self.assertEqual(result["retained_records"], 3)
        self.assertEqual(result["public_records"], 1)
        self.assertEqual(result["hidden_records"], 2)
        self.assertEqual(result["public_share"], 1 / 3)


class PopulationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One real generated population reused by isolated save roundtrips. No
        # reduced population substitute hides integration or serialization bugs.
        cls.initial_save = LifeGame.new(seed=37).to_dict()

    def new_game(self):
        return LifeGame.from_dict(deepcopy(self.initial_save))

    def available_action(self, game, npc_id=None, action="talk"):
        if npc_id is None:
            for person in game.people(group="direct", limit=48)["people"]:
                if person["id"] in {"mother", "father", "friend", "partner"}:
                    continue
                options = game.person(person["id"])["actions"]
                if any(row["id"] == action and row["available"] for row in options):
                    npc_id = person["id"]
                    break
            self.assertIsNotNone(npc_id, "真实初始人际圈没有可用的非锚点联系对象")
        option = next(row for row in game.person(npc_id)["actions"] if row["id"] == action)
        self.assertTrue(option["available"], option["locked_reason"])
        return npc_id, option

    def test_population_keeps_four_legacy_identities_without_inventing_acquaintances(self):
        game = self.new_game()
        pop = game.state["population"]
        self.assertEqual(len(pop["people"]), 2000)
        self.assertEqual(set(game.state["npcs"]), {"mother", "father", "friend", "partner"})
        for npc_id, anchor in game.state["npcs"].items():
            person = pop["people"][npc_id]
            self.assertTrue(person["anchor"])
            self.assertEqual(person["name"], anchor["name"])
            self.assertEqual(person["status"] == "alive", anchor["alive"])
        counts = population_counts(pop)
        self.assertEqual(counts["detailed"], 200)
        self.assertLess(counts["direct"], counts["detailed"])
        self.assertLessEqual(counts["focus"], 200)
        self.assertEqual(pop["people"]["partner"]["knowledge"]["contact"], "none")

    def test_contact_pays_visible_cost_and_commits_once_without_advancing_the_life_slot(self):
        game = self.new_game()
        npc_id, option = self.available_action(game)
        before = game.to_dict()["state"]
        game.social(npc_id, "talk", before["revision"])
        after = game.state
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(after["slot_index"], before["slot_index"])
        self.assertEqual(after["year"], before["year"])
        self.assertEqual(after["current_event"], before["current_event"])
        self.assertEqual(after["stats"]["cash"], before["stats"]["cash"] - option["costs"]["cash"])
        self.assertEqual(after["stats"]["energy"], before["stats"]["energy"] - option["costs"]["energy"])
        records = after["timeline"][len(before["timeline"]):]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "social")
        self.assertIn(npc_id, records[0]["population_ids"])
        self.assertEqual(records[0]["year"], before["year"])

    def test_stale_contact_and_insufficient_energy_are_atomic(self):
        game = self.new_game()
        npc_id, _ = self.available_action(game)
        revision = game.state["revision"]
        game.social(npc_id, "talk", revision)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.social(npc_id, "talk", revision)
        self.assertEqual(game.to_dict(), before)
        game = self.new_game()
        npc_id, _ = self.available_action(game)
        game.state["stats"]["energy"] = 0
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.social(npc_id, "talk", game.state["revision"])
        self.assertEqual(game.to_dict(), before)

    def test_unknown_identity_and_private_records_are_not_exposed_by_public_queries(self):
        game = self.new_game()
        npc_id, _ = self.available_action(game)
        person = game.state["population"]["people"][npc_id]
        marker = "PRIVATE_RECORD_SHOULD_NOT_REACH_PLAYER_739"
        person["history"].append({"id": "test-private-record", "year": game.state["year"],
                                  "code": "crime", "title": marker, "text": marker,
                                  "visibility": "private", "known": False,
                                  "source": "测试内部事实", "confidence": "recorded"})
        person["flags"]["undisclosed_test_crime"] = True
        public = {"person": game.person(npc_id), "people": game.people(), "view": game.view()}
        serialized = json.dumps(public, ensure_ascii=False)
        self.assertNotIn(marker, serialized)
        self.assertNotIn("undisclosed_test_crime", serialized)
        unknown_id, unknown = next((pid, row) for pid, row in game.state["population"]["people"].items()
                                   if row["knowledge"]["contact"] == "none" and not row["anchor"])
        self.assertNotIn(unknown_id, [row["id"] for row in game.people(query=unknown["name"])["people"]])
        with self.assertRaises(RuleError):
            game.person(unknown_id)

    def test_cached_contact_cannot_execute_after_death_detention_or_departure(self):
        from game import population as rules

        base = self.new_game()
        npc_id, _ = self.available_action(base)
        for transition in ("death", "detention", "departure"):
            with self.subTest(transition=transition):
                pop = deepcopy(base.state["population"])
                person = pop["people"][npc_id]
                if transition == "death":
                    person.update(status="dead", death_year=pop["year"])
                elif transition == "detention":
                    person["flags"]["detained"] = True
                    person["detained_until"] = pop["year"] + 2
                else:
                    person["location"] = "外地"
                # These are narrow action-gate fixtures, not imported save files.
                # A cached action must reject before any full-state commit.
                before = deepcopy(pop)
                options = rules.interaction_options(pop, npc_id, base.state["age"], base.state["stats"])
                talk = next(row for row in options if row["id"] == "talk")
                self.assertFalse(talk["available"])
                with self.assertRaises(rules.PopulationError):
                    rules.interact(pop, npc_id, "talk", base.state["age"], base.state["stats"])
                self.assertEqual(pop, before)

    def test_annual_contact_limit_cannot_be_avoided_with_many_different_people(self):
        game = self.new_game()
        succeeded = 0
        targets = [row["id"] for row in game.people(group="direct", limit=48)["people"]
                   if row["id"] not in {"mother", "father", "friend", "partner"}]
        self.assertGreaterEqual(len(targets), 4)
        for npc_id in targets:
            before = game.to_dict()
            try:
                game.social(npc_id, "talk", game.state["revision"])
            except RuleError:
                self.assertEqual(game.to_dict(), before)
                break
            succeeded += 1
        self.assertEqual(succeeded, 3, "六岁时应执行年度三次上限，而不是按人物分别刷新")
        self.assertGreater(game.state["stats"]["energy"], 0, "应由年度额度而非精力耗尽阻止继续联系")

    def test_social_plan_is_recorded_and_cannot_be_replayed_with_old_revision(self):
        game = self.new_game()
        before = game.to_dict()["state"]
        game.set_social_plan("community", before["revision"])
        self.assertEqual(game.state["revision"], before["revision"] + 1)
        self.assertEqual(game.state["slot_index"], before["slot_index"])
        self.assertEqual(game.state["current_event"], before["current_event"])
        self.assertEqual(game.state["timeline"][-1]["kind"], "social_plan")
        committed = game.to_dict()
        with self.assertRaises(RuleError):
            game.set_social_plan("family", before["revision"])
        self.assertEqual(game.to_dict(), committed)

    def test_legacy_anchor_interaction_cannot_create_a_second_relationship_authority(self):
        game = self.new_game()
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.social("friend", "talk", game.state["revision"])
        self.assertEqual(game.to_dict(), before)

    def test_finished_life_cannot_submit_contacts_or_change_future_plans(self):
        game = self.new_game()
        npc_id, _ = self.available_action(game)
        game._finish("测试终局")
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.social(npc_id, "talk", game.state["revision"])
        with self.assertRaises(RuleError):
            game.set_social_plan("community", game.state["revision"])
        self.assertEqual(game.to_dict(), before)

    def test_old_save_migration_starts_population_now_and_preserves_the_old_life(self):
        old = json.loads((FIXTURES / "v04-save.json").read_text(encoding="utf-8"))
        pristine = deepcopy(old)
        game = LifeGame.from_dict(old)
        self.assertEqual(old, pristine, "导入不能改写调用者的原档")
        self.assertEqual(game.to_dict()["schema_version"], "1.3.0")
        for key in ("timeline", "npcs", "current_event", "random_counter", "revision", "loans", "world"):
            self.assertEqual(game.state[key], old["state"][key], key)
        self.assertTrue(game.state["migration_note"])
        for person in game.state["population"]["people"].values():
            for record in person["history"] + person["recent"]:
                self.assertGreaterEqual(record["year"], old["state"]["year"], "迁移补造了过去的人口经历")
        self.assertEqual(LifeGame.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_save_roundtrip_preserves_social_progress_and_next_choice(self):
        game = self.new_game()
        npc_id, _ = self.available_action(game)
        game.social(npc_id, "talk", game.state["revision"])
        save = json.loads(json.dumps(game.to_dict(), ensure_ascii=False))
        restored = LifeGame.from_dict(save)
        self.assertEqual(restored.to_dict(), game.to_dict())
        public = game.view()
        selected = next(choice["id"] for choice in public["event"]["choices"] if choice["available"])
        game.choose(selected, game.state["revision"])
        restored.choose(selected, restored.state["revision"])
        self.assertEqual(restored.to_dict(), game.to_dict())

    def test_save_cannot_mix_the_life_with_a_different_seed_population(self):
        game = self.new_game()
        bad = game.to_dict()
        bad["state"]["population"] = LifeGame.new(seed=38).state["population"]
        with self.assertRaises(RuleError):
            LifeGame.from_dict(bad)


if __name__ == "__main__":
    unittest.main()
