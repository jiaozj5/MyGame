"""Population invariants and bounded, observable social simulation."""
from copy import deepcopy
import json
import unittest

from game import population as p


def anchors(year=7):
    return {pid: {"id": pid, "name": name, "birth_year": birth, "alive": True, "death_year": None,
                  "death_age": None, "age": year - birth, "cash": 20000, "closeness": close,
                  "met": pid != "partner", "role": role}
            for pid, name, birth, close, role in (("mother", "许岚", -23, 76, "母亲"), ("father", "林川", -26, 70, "父亲"),
                                                 ("friend", "周远", 1, 48, "朋友"), ("partner", "陈安", 2, 15, "相识的人"))}


def interaction(eid="test.theft", kind="crime", requirements=None, effects=None, visibility="private"):
    return {"id": eid, "title": "一次有后果的事件", "kind": kind, "min_age": 18, "requires": requirements or [],
            "effects": effects or [], "visibility": visibility, "text": "{actor}与{target}之间发生了一件事。", "weight": 1, "cooldown": 0, "tags": []}


class PopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = p.load_library()
        cls.base = p.new_population(39, 7, anchors(), cls.library)

    def adult_pair(self):
        ids = [pid for pid, row in self.base["people"].items() if not row["anchor"] and row["status"] == "alive" and p._age(self.base, row) >= 18]
        return ids[:2]

    def test_capacity_hidden_births_and_safe_integer_roundtrip(self):
        pop = self.base
        self.assertEqual(len(pop["people"]), 2000)
        self.assertEqual(sum(person["detailed"] for person in pop["people"].values()), 200)
        view = p.population_view(pop)
        self.assertLess(view["known_count"], 20)
        future = next(pid for pid, person in pop["people"].items() if person["status"] == "unborn")
        with self.assertRaises(p.PopulationError):
            p.person_view(pop, future)
        restored = json.loads(json.dumps(pop), parse_int=lambda token: int(float(token)))
        self.assertEqual(restored, pop)
        p.validate_population(restored, anchors(), 7, True)

    def test_copy_on_write_does_not_clone_or_mutate_untouched_people(self):
        pop = self.base
        pid = next(pid for pid, row in pop["people"].items() if not row["anchor"] and row["knowledge"]["contact"] == "direct")
        untouched = next(key for key in pop["people"] if key != pid and key not in p.ANCHORS)
        before = deepcopy(pop)
        changed, result = p.interact(pop, pid, "talk", 6, {"cash": 1000, "energy": 50})
        self.assertEqual(pop, before)
        self.assertIs(changed["people"][untouched], pop["people"][untouched])
        self.assertIsNot(changed["people"][pid], pop["people"][pid])
        self.assertEqual(result["costs"], {"cash": 0, "energy": 4})
        self.assertNotIn("energy", result["stat_deltas"])

    def test_batch_step_and_json_continuation_have_same_real_history(self):
        direct = p.advance_population(self.base, 13, anchors(13), {}, library=self.library)
        step = self.base
        for year in range(8, 14):
            step = p.advance_population(step, year, anchors(year), {}, library=self.library)
        restored = json.loads(json.dumps(p.advance_population(self.base, 10, anchors(10), {}, library=self.library)))
        restored = p.advance_population(restored, 13, anchors(13), {}, library=self.library)
        self.assertEqual(direct, step)
        self.assertEqual(direct, restored)
        p.validate_population(direct, anchors(13), 13, True)

    def test_pending_case_belongs_to_its_directed_pair_and_is_atomic(self):
        actor, target = self.adult_pair()
        working = p._copy(self.base)
        theft = interaction(effects=[{"op": "transfer", "from": "target", "to": "actor", "amount": 100},
                                     {"op": "edge_flag", "direction": "actor_target", "key": "fraud_pending", "value": True}])
        self.assertTrue(p._apply_interaction(working, actor, target, theft, {}, self.library))
        followup = interaction("test.resolve", "repair", [{"path": "edge.flags.fraud_pending", "op": "eq", "value": True}])
        self.assertTrue(p._eligible_interaction(working, actor, target, followup, {}, self.library))
        self.assertFalse(p._eligible_interaction(working, target, actor, followup, {}, self.library))
        third = next(pid for pid, row in working["people"].items() if pid not in {actor, target} and not row["anchor"] and row["status"] == "alive" and p._age(working, row) >= 18)
        self.assertFalse(p._eligible_interaction(working, actor, third, followup, {}, self.library))
        bad = interaction(effects=[{"op": "stat", "who": "actor", "key": "reputation", "delta": -5},
                                   {"op": "transfer", "from": "target", "to": "actor", "amount": working["people"][target]["stats"]["cash"] + 1}])
        before = deepcopy(working)
        self.assertFalse(p._apply_interaction(working, actor, target, bad, {}, self.library))
        self.assertEqual(working, before)

    def test_ordinary_entrusted_purchase_enters_followup_queue(self):
        actor, target = self.adult_pair()
        work = p._copy(self.base)
        p._edge(work, actor, target)["flags"]["entrusted_fund"] = True
        followup = interaction("test.honest_fulfillment", "repair", [{"path": "edge.flags.entrusted_fund", "op": "eq", "value": True}],
                               [{"op": "edge_flag", "direction": "actor_target", "key": "entrusted_fund", "value": False}])
        followup["tags"] = ["case_followup"]
        p._resolve_interactions(work, {}, {**self.library, "interactions": [followup]})
        self.assertFalse(work["people"][actor]["relations"][target]["flags"]["entrusted_fund"])
        self.assertEqual(work["counters"]["consequences"], 1)

    def test_malformed_knowledge_or_archive_is_rejected_before_view(self):
        actor, _ = self.adult_pair()
        for mutate in (lambda pop: pop["people"][actor]["knowledge"].pop("ever_close"),
                       lambda pop: pop["people"][actor]["knowledge"].update(traits=42),
                       lambda pop: pop["people"][actor]["knowledge"].update(identities=["unknown"]),
                       lambda pop: pop["people"][actor]["history"][0].pop("title") if pop["people"][actor]["history"] else pop["people"][actor]["recent"][0].pop("text"),
                       lambda pop: pop["news"].append({"id": "broken", "year": 7, "visibility": "public", "text": "消息", "source": "公开记录"})):
            bad = deepcopy(self.base)
            mutate(bad)
            with self.assertRaises(p.PopulationError):
                p.validate_population(bad, full=True)

    def test_personal_routine_does_not_displace_news_about_other_people(self):
        work = p._copy(self.base)
        pid = next(pid for pid, row in work["people"].items() if not row["anchor"] and row["knowledge"]["contact"] == "direct")
        p._record(work, [pid], "career", "真正的工作变化", "一次公开的职业变动。")
        for _ in range(140):
            p._record(work, [pid], "shared_time", "一起活动", "实际共同参加活动。", "participants", True)
        self.assertEqual(work["news"][-1]["title"], "真正的工作变化")
        self.assertTrue(any(entry["code"] == "shared_time" for entry in work["people"][pid]["history"]))

    def test_children_cannot_participate_in_crime_or_exploitation(self):
        ids = [pid for pid, row in self.base["people"].items() if not row["anchor"] and row["status"] == "alive" and p._age(self.base, row) < 18][:2]
        for kind in ("crime", "deception", "exploitation"):
            event = interaction(kind=kind)
            event["min_age"] = 0
            self.assertFalse(p._eligible_interaction(self.base, *ids, event, {}, self.library))

    def test_detention_expires_with_record_and_dead_people_cannot_return(self):
        pop = deepcopy(self.base)
        actor, target = self.adult_pair()
        pop["people"][actor]["flags"]["detained"] = True
        pop["people"][actor]["detained_until"] = 8
        quiet = {**self.library, "interactions": []}
        result = p.advance_population(pop, 8, anchors(8), {}, library=quiet)
        self.assertFalse(result["people"][actor]["flags"]["detained"])
        self.assertTrue(any(row["code"] == "release" for row in result["people"][actor]["history"] + result["people"][actor]["recent"]))
        dead = p._copy(result)
        p._mark_dead(dead, target, "测试中的实际死亡。")
        dead = p._done(dead)
        next_year = p.advance_population(dead, 9, anchors(9), {}, library=quiet)
        self.assertEqual(next_year["people"][target]["status"], "dead")
        self.assertEqual(next_year["people"][target]["death_year"], 8)
        bad = deepcopy(dead)
        bad["people"][target].update(status="alive", death_year=None, death_recorded=False)
        with self.assertRaises(p.PopulationError):
            p.validate_population(bad, full=True, library=self.library)

    def test_retained_history_grows_and_promotion_does_not_invent_past(self):
        work = p._copy(self.base)
        pid = next(pid for pid, row in work["people"].items() if not row["detailed"] and row["status"] == "alive" and row["knowledge"]["contact"] == "none")
        for index in range(10):
            p._record(work, [pid], "test", "已发生", str(index), "private")
        self.assertEqual(len(work["people"][pid]["recent"]), 6)
        surviving = [entry["id"] for entry in work["people"][pid]["recent"]]
        p._discover(work, pid, "direct", "实际见面")
        self.assertEqual([entry["id"] for entry in work["people"][pid]["history"]][:6], surviving)
        for index in range(30):
            p._record(work, [pid], "test", "新的实际经历", str(index))
        self.assertGreater(len(work["people"][pid]["history"]), 24)

    def test_anchor_authority_and_posthumous_occupation_are_stable(self):
        authority = anchors()
        authority["father"].update(alive=False, death_year=7, death_age=33)
        pop = p.sync_anchors(self.base, authority, 7)
        occupation = pop["people"]["father"]["occupation"]
        for year in range(8, 13):
            pop = p.advance_population(pop, year, authority, {}, library=self.library)
            self.assertEqual(pop["people"]["father"]["occupation"], occupation)
            self.assertEqual(pop["people"]["father"]["stats"]["cash"], authority["father"]["cash"])
        options = p.interaction_options(pop, "mother", 11, {"cash": 1000, "energy": 90})
        self.assertTrue(all(not item["available"] for item in options if item["id"] != "follow"))

    def test_anchor_follow_choice_survives_authority_sync(self):
        changed, _ = p.interact(self.base, "mother", "follow", 6, {"cash": 100, "energy": 50})
        synced = p.sync_anchors(changed, anchors(), 7)
        self.assertNotIn("mother", synced["tracked"])
        self.assertEqual(synced["people"]["mother"]["knowledge"]["closeness"], anchors()["mother"]["closeness"])

    def test_private_facts_and_unknown_identity_cannot_be_searched(self):
        work = p._copy(self.base)
        pid = next(pid for pid, row in work["people"].items() if not row["anchor"] and row["knowledge"]["contact"] == "direct")
        p._record(work, [pid], "secret", "秘密哨兵XYZ", "私密事实XYZ", "private")
        work = p._done(work)
        self.assertNotIn("XYZ", json.dumps(p.person_view(work, pid), ensure_ascii=False))
        self.assertNotIn("XYZ", json.dumps(p.population_view(work), ensure_ascii=False))
        self.assertEqual(p.population_view(work, query="秘密哨兵XYZ")["total"], 0)

    def test_new_birth_appears_only_at_actual_year_and_large_migration_is_bounded(self):
        future = min((row for row in self.base["people"].values() if row["status"] == "unborn"), key=lambda row: row["birth_year"])
        end = p.advance_population(self.base, future["birth_year"], anchors(future["birth_year"]), {}, library=self.library)
        born = end["people"][future["id"]]
        self.assertEqual(born["status"], "alive")
        self.assertTrue(born["birth_recorded"])
        self.assertEqual(born["birth_year"], end["year"])
        late = p.new_population(4, 83, anchors(83), self.library)
        self.assertLessEqual(max(p._age(late, row) for row in late["people"].values() if not row["anchor"] and row["status"] == "alive"), 90)
        self.assertTrue(all(entry["year"] == 83 for row in late["people"].values() for entry in row["history"] + row["recent"]))


if __name__ == "__main__":
    unittest.main()
