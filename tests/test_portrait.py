from copy import deepcopy
import json
import unittest

from game.portrait import build_biography


def life(records=None, **changes):
    state = {"name": "林初", "age": 76, "year": 2064, "born_year": 1988,
             "finished": True, "death_reason": "自然离世", "timeline": records or [],
             "npcs": {}, "stats": {"cash": 900, "health": 0}}
    state.update(changes)
    return state


def choice(record_id, age, selected="提供帮助", behavior="提供实际帮助", *,
           available=None, locked=None, dimension="care", category="friend"):
    available = ["selected", "other"] if available is None else available
    return {"id": record_id, "age": age, "year": 1988 + age,
            "title": "一次取舍", "kind": "choice", "choice": selected,
            "choice_id": "selected", "text": "这次选择已记入经历。",
            "observations": [{"dimension": dimension, "behavior": behavior}],
            "context": {"opportunity": len(available) >= 2,
                        "available_choice_ids": available, "locked_options": locked or [],
                        "context_tags": [category, "adult"],
                        "resources_before": {"cash": 100}}}


class PortraitTests(unittest.TestCase):
    def test_evaluation_contract_is_present_for_every_dimension(self):
        report = build_biography(life())
        self.assertEqual(len(report["patterns"]), 8)
        for pattern in report["patterns"]:
            self.assertTrue(pattern["dimension"])
            self.assertIsInstance(pattern["subdimensions"], list)
            self.assertTrue(pattern["subdimensions"])
            self.assertEqual(pattern["eligible_opportunities"], 0)
            self.assertEqual(pattern["independent_episodes"], 0)
            self.assertEqual(pattern["behavior_counts"], {})
            self.assertEqual(pattern["context_counts"], {})
            self.assertIsInstance(pattern["limitations"], list)
        serialized = json.dumps(report, ensure_ascii=False)
        for forbidden in ("psychometric_score", "percentile", "personality_type",
                          "confidence_probability", "real_player_inference"):
            self.assertNotIn(forbidden, serialized)

    def test_behavior_counts_and_episode_counts_are_deterministic(self):
        first = choice("episode-a", 22, behavior="material_support", category="借款")
        first["episode_id"] = "loan-1"
        second = choice("episode-b", 23, behavior="material_support", category="借款")
        second["episode_id"] = "loan-1"
        third = choice("episode-c", 24, behavior="limit_financial_exposure", category="借款")
        third["episode_id"] = "loan-2"
        report = build_biography(life([first, second, third]))
        care = next(item for item in report["patterns"] if item["dimension"] == "care")
        self.assertEqual(care["independent_episodes"], 2)
        self.assertEqual(care["eligible_opportunities"], 3)
        self.assertEqual(care["behavior_counts"], {"material_support": 2,
                                                     "limit_financial_exposure": 1})
        self.assertEqual(care["context_counts"]["adult|借款"], 3)
    def test_locked_loan_and_only_feasible_action_are_not_personality_evidence(self):
        # There are two executable choices, but lending itself is unavailable.
        no_money = choice("r1", 20, selected="说明无法借钱", behavior="拒绝借钱",
                          locked=[{"id": "lend", "reason": "现金不足"}])
        forced = choice("r2", 21, selected="接受救助", behavior="接受帮助",
                        available=["selected"], dimension="help_seeking")
        report = build_biography(life([no_money, forced]))
        for pattern in report["patterns"]:
            self.assertEqual(pattern["evidence_ids"], [])
            self.assertEqual(pattern["counter_evidence_ids"], [])
        care = next(item for item in report["patterns"] if item["dimension"] == "care")
        self.assertEqual(care["coverage"], "未观察")
        self.assertIn("不作为自由偏好", " ".join(report["notes"]))
        self.assertIn("r1", report["chapters"][1]["event_ids"])
        self.assertIn("说明无法借钱", report["chapters"][1]["text"])

    def test_missing_choice_conditions_are_not_silently_treated_as_free_choice(self):
        entry = choice("unknown-context", 28)
        del entry["context"]
        report = build_biography(life([entry]))
        care = next(item for item in report["patterns"] if item["dimension"] == "care")
        self.assertEqual(care["coverage"], "未观察")
        self.assertEqual(care["evidence_ids"], [])
        self.assertIn("选择条件不完整", care["text"])

    def test_all_references_resolve_and_different_actions_remain_visible(self):
        records = [choice("help", 22),
                   choice("decline", 24, selected="这次选择拒绝", behavior="拒绝此次帮助")]
        state = life(records)
        before = deepcopy(state)
        report = build_biography(state)
        care = next(item for item in report["patterns"] if item["dimension"] == "care")
        self.assertEqual(set(care["evidence_ids"]), {"help"})
        self.assertEqual(care["counter_evidence_ids"], ["decline"])
        self.assertIn("拒绝此次帮助", care["text"])
        self.assertEqual(care["coverage"], "有限")
        existing = {entry["id"] for entry in records}
        for section in ("chapters", "relationships"):
            for item in report[section]:
                self.assertTrue(set(item["event_ids"]) <= existing)
        for pattern in report["patterns"]:
            self.assertTrue(set(pattern["evidence_ids"]) <= existing)
            self.assertTrue(set(pattern["counter_evidence_ids"]) <= existing)
        self.assertEqual(state, before)

    def test_stage_boundaries_and_unlived_years_do_not_invent_later_life(self):
        records = [choice(f"age-{age}", age) for age in (17, 18, 35, 36, 59, 60)]
        chapters = build_biography(life(records))["chapters"]
        self.assertEqual([chapter["event_ids"] for chapter in chapters],
                         [["age-17"], ["age-18", "age-35"], ["age-36", "age-59"], ["age-60"]])
        short_life = build_biography(life(records[:2], age=19, year=2007))
        self.assertEqual(short_life["chapters"][2]["event_ids"], [])
        self.assertIn("没有进入这一阶段", short_life["chapters"][2]["text"])
        self.assertNotIn("退休", short_life["chapters"][3]["text"])

    def test_deceased_debtor_and_surviving_claim_do_not_imply_repayment(self):
        records = [{"id": "loss", "age": 45, "year": 2033, "kind": "npc_death",
                    "title": "朋友离世", "text": "周远离世，借款保留待处理。", "npc_ids": ["friend"]}]
        state = life(records, npcs={"friend": {"name": "周远", "alive": False,
                                               "met": True, "death_year": 2033}},
                     loans=[{"npc": "friend", "amount": 400, "status": "deceased_pending"}])
        report = build_biography(state)
        relationship = report["relationships"][0]
        self.assertEqual(relationship["event_ids"], ["loss"])
        self.assertIn("借款保留待处理", relationship["text"])
        self.assertNotIn("还清", relationship["text"])
        self.assertNotIn("已经还款", relationship["text"])
        self.assertTrue(all(not pattern["evidence_ids"] for pattern in report["patterns"]))

    def test_invalid_or_unresolvable_records_are_rejected_instead_of_repaired(self):
        original = choice("same-id", 20)
        with self.assertRaisesRegex(ValueError, "重复"):
            build_biography(life([original, deepcopy(original)]))
        nonexistent_choice = choice("bad-choice", 21)
        nonexistent_choice["choice_id"] = "not-offered"
        with self.assertRaisesRegex(ValueError, "不在可行选项"):
            build_biography(life([nonexistent_choice]))
        unknown_dimension = choice("bad-dimension", 21, dimension="secret_diagnosis")
        with self.assertRaisesRegex(ValueError, "未知观察维度"):
            build_biography(life([unknown_dimension]))
        future = choice("future", 77)
        with self.assertRaisesRegex(ValueError, "超出"):
            build_biography(life([future]))

    def test_empty_partial_life_reports_absence_without_filling_in_traits(self):
        report = build_biography({"name": "阿宁", "age": 8})
        self.assertEqual(len(report["patterns"]), 8)
        self.assertTrue(all(item["coverage"] == "未观察" for item in report["patterns"]))
        self.assertEqual(report["relationships"], [])
        self.assertIn("尚无具体经历", report["summary"])
        self.assertNotIn("置信概率", json.dumps(report, ensure_ascii=False))

    def test_chapters_select_turning_points_without_erasing_the_complete_timeline(self):
        records = [{"id": "birth", "age": 0, "year": 1988, "kind": "birth",
                    "title": "出生", "text": "林初出生了。"}]
        for age in range(1, 18):
            records.append({"id": f"annual-{age}", "age": age, "year": 1988 + age,
                            "kind": "annual", "title": "又长大一岁", "text": "零用钱流水。"})
            if age in (6, 9, 12, 15):
                records.append(choice(f"decision-{age}", age))
        records.extend([choice(f"adult-{age}", age) for age in range(18, 35)])
        state = life(records)
        before = deepcopy(state)
        report = build_biography(state)
        for chapter in report["chapters"]:
            self.assertLessEqual(len(chapter["event_ids"]), 5)
            self.assertFalse(any(item.startswith("annual-") for item in chapter["event_ids"]))
            self.assertNotIn("零用钱流水", chapter["text"])
        self.assertIn("birth", report["chapters"][0]["event_ids"])
        self.assertIn("adult-18", report["chapters"][1]["event_ids"])
        self.assertIn("adult-34", report["chapters"][1]["event_ids"])
        self.assertEqual(state, before)

    def test_patterns_are_short_behavior_based_and_hide_internal_identifiers(self):
        records = [choice(f"action-{age}", age, selected="选择卡片很长的具体说明",
                          behavior="继续投入已有的学习路径" if age % 2 else "调整练习的方法",
                          dimension="persistence") for age in range(18, 31)]
        records.append(choice("extension", 31, selected="再等三年",
                              behavior="negotiated_extension", dimension="conflict_style"))
        report = build_biography(life(records))
        for pattern in report["patterns"]:
            self.assertLessEqual(len(pattern["evidence_ids"]), 3)
            self.assertLessEqual(len(pattern["counter_evidence_ids"]), 1)
            self.assertLess(len(pattern["text"]), 350)
            self.assertNotIn("不足以证明稳定偏好", pattern["text"])
        persistence = next(item for item in report["patterns"] if item["dimension"] == "persistence")
        self.assertIn("调整练习的方法", persistence["text"])
        self.assertIn("继续投入已有的学习路径", persistence["text"])
        self.assertNotIn("选择卡片很长的具体说明", persistence["text"])
        conflict = next(item for item in report["patterns"] if item["dimension"] == "conflict_style")
        self.assertIn("延长还款期限", conflict["text"])
        self.assertNotIn("negotiated_extension", conflict["text"])

    def test_relationship_highlights_keep_actual_settlement_and_death(self):
        records = []
        for age in range(20, 33):
            entry = choice(f"friend-{age}", age)
            entry["npc_ids"] = ["friend"]
            records.append(entry)
        repaid = choice("repaid", 34, selected="接受还款", behavior="按约处理借款")
        repaid["choice_id"] = "repay"
        repaid["context"]["available_choice_ids"] = ["repay", "extend"]
        repaid["npc_ids"] = ["friend"]
        repaid["text"] = "周远偿还了四百元借款。"
        records.extend([repaid, {"id": "loss", "age": 45, "year": 2033, "kind": "npc_death",
                                "title": "告别周远", "text": "周远于2033年离世。", "npc_ids": ["friend"]}])
        report = build_biography(life(records, npcs={"friend": {"name": "周远", "alive": False,
                                                                "met": True, "death_year": 2033}}))
        friend = report["relationships"][0]
        self.assertLessEqual(len(friend["event_ids"]), 4)
        self.assertIn("repaid", friend["event_ids"])
        self.assertIn("loss", friend["event_ids"])
        self.assertIn("偿还了四百元借款", friend["text"])
        self.assertEqual(friend["text"].count("周远于2033年离世"), 1)


if __name__ == "__main__":
    unittest.main()
