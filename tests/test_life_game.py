"""Integration regressions for the playable life game, using its real catalog."""
from copy import deepcopy
import json
import random
import unittest

from game.engine import AGES, LifeGame, ORIGINS, RECOVERY_COOLDOWN_YEARS, RuleError
from game.portrait import build_biography
from game.population import sync_anchors


def choose_feasible(game, rng=None):
    """Use the real transaction boundary, without rendering a view every turn."""
    candidates = list(game.state["current_event"]["choices"])
    if rng is not None:
        rng.shuffle(candidates)
    failures = []
    for candidate in candidates:
        try:
            game.choose(candidate["id"], game.state["revision"])
            return candidate["id"]
        except RuleError as error:
            failures.append(str(error))
    raise AssertionError(f"没有可执行选项：{game.state['current_event']['id']}；{failures}")


def constrained_offer():
    return {"id": "test.financial_choice", "title": "手头有限的一次求助", "category": "关怀",
            "scene": "town", "age_min": 0, "age_max": 82, "actors": [],
            "requires": [], "once": True, "_kind": "slot", "text": "有人请求五百元帮助。",
            "choices": [
                {"id": "pay", "label": "拿出五百元", "requires": [],
                 "effects": [{"op": "stat", "key": "cash", "delta": -500}],
                 "observations": [{"dimension": "care", "behavior": "提供现金帮助"}],
                 "outcome": "你提供了五百元。"},
                {"id": "decline", "label": "说明自己无法出钱", "requires": [], "effects": [],
                 "observations": [{"dimension": "care", "behavior": "拒绝出钱"}],
                 "outcome": "你说明了自己的处境。"},
                {"id": "search", "label": "尝试寻找别的办法", "requires": [], "effects": [],
                 "observations": [{"dimension": "care", "behavior": "寻找替代支持"}],
                 "outcome": "你开始寻找其他办法。"}]}


def adult_loan_game():
    """A small valid adult fixture isolates debt behavior from event selection."""
    game = LifeGame.new(seed=77)
    while game.state["age"] < 20:
        choose_feasible(game)
    state = game.state
    state["stats"]["cash"] = max(state["stats"]["cash"], 2000)
    state["current_event"] = {
        "id": "test.friend_loan", "title": "一笔借款", "category": "借款", "scene": "town",
        "age_min": 18, "age_max": 82, "actors": ["friend"], "requires": [],
        "once": True, "_kind": "slot", "text": "周远希望借四百元，一年后归还。",
        "choices": [
            {"id": "lend", "label": "借出四百元", "requires": [],
             "effects": [{"op": "loan", "npc": "friend", "amount": 400, "due_years": 1}],
             "observations": [{"dimension": "care", "behavior": "提供借款"}],
             "outcome": "你借给周远四百元。"},
            {"id": "decline", "label": "拒绝借款", "requires": [], "effects": [],
             "observations": [], "outcome": "这次没有借出钱。"}]}
    game._update_budget()
    game._validate()
    return game


class LifeGameIntegrationTests(unittest.TestCase):
    def assert_report_references_exist(self, game):
        report = build_biography(game.state)
        actual = {entry["id"] for entry in game.state["timeline"]}
        for section in ("chapters", "relationships"):
            for item in report[section]:
                self.assertTrue(set(item["event_ids"]) <= actual)
        for pattern in report["patterns"]:
            self.assertTrue(set(pattern["evidence_ids"]) <= actual)
            self.assertTrue(set(pattern["counter_evidence_ids"]) <= actual)
        self.assertEqual(len(report["chapters"]), 4)
        self.assertEqual(len(report["patterns"]), 8)
        return report

    def test_multiple_seeds_and_origins_finish_without_dead_actors_or_negative_resources(self):
        # 54 independent paths: eighteen seeds across all three starting states.
        # Other tests isolate failure causes instead of adding random repetition.
        completed = []
        for origin in ORIGINS:
            for seed in range(18):
                with self.subTest(origin=origin, seed=seed):
                    game = LifeGame.new(name="林禾", origin=origin, seed=seed)
                    rng = random.Random(9000 + seed)
                    count = 0
                    while not game.state["finished"]:
                        self.assertLess(count, 80, "人生选择没有在合理次数内推进")
                        event = game.state["current_event"]
                        self.assertIsNotNone(event)
                        for npc_id in event.get("actors", []):
                            self.assertTrue(game.state["npcs"][npc_id]["alive"],
                                            f"死者参与活人事件 {event['id']}")
                        choose_feasible(game, rng)
                        count += 1
                        for key, value in game.state["stats"].items():
                            self.assertGreaterEqual(value, 0, key)
                            if key != "cash":
                                self.assertLessEqual(value, 100, key)
                        for npc in game.state["npcs"].values():
                            self.assertGreaterEqual(npc["cash"], 0)
                    # Same-year relationship replies do not consume a life slot.
                    adjustments = game.state["survival"]["adjustment_count"]
                    self.assertLessEqual(adjustments, (game.state["age"] - 6) // RECOVERY_COOLDOWN_YEARS + 1)
                    self.assertLessEqual(count, len(AGES) + 2 + 3 * len(game.state["loans"]) + adjustments)
                    self.assertIsNone(game.state["current_event"])
                    self.assertTrue(game.state["death_reason"])
                    self.assertEqual(game.state["timeline"][-1]["kind"], "death")
                    self.assertLessEqual(game.state["age"], 82)
                    if game.state["age"] == 82 and game.state["death_reason"] != "健康耗尽":
                        self.assertIn("later.life_review", game.state["used_events"], "时代事件不能挤掉人生回顾的收尾机会")
                    dead = set()
                    for entry in game.state["timeline"]:
                        if entry["kind"] == "npc_death":
                            dead.update(entry.get("npc_ids", []))
                        elif entry["kind"] == "choice":
                            self.assertFalse(dead.intersection(entry.get("npc_ids", [])))
                    self.assert_report_references_exist(game)
                    completed.append(game.state["age"])
        self.assertEqual(len(completed), 54)
        self.assertIn(82, completed, "至少应有一条实际路径到达晚年终章")

    def test_deceased_debtor_keeps_claim_and_cannot_execute_cached_repayment(self):
        game = adult_loan_game()
        game.choose("lend", game.state["revision"])
        self.assertEqual(game.state["current_event"]["_kind"], "loan_due")
        cached = deepcopy(game.state["current_event"])
        game._npc_death("friend")
        # _npc_death is a private part of the annual transaction. This test
        # invokes it directly, so explicitly finish the anchor synchronization.
        game.state["population"] = sync_anchors(game.state["population"], game.state["npcs"], game.state["year"])
        cash_after_death = game.state["stats"]["cash"]
        loan = game.state["loans"][0]
        self.assertEqual(loan["status"], "deceased_pending")
        self.assertEqual(loan["amount"], 400)
        self.assertFalse(loan["scheduled"])
        self.assertIsNone(game._due_loan())
        repayment = next(item for item in cached["choices"] if item["id"] == "repay")
        candidate, reason = game._choice_result(cached, repayment)
        self.assertIsNone(candidate)
        self.assertTrue(reason)
        self.assertEqual(game.state["stats"]["cash"], cash_after_death)
        game._select_event()
        game._validate()
        self.assertNotIn("friend", game.state["current_event"].get("actors", []))
        report = self.assert_report_references_exist(game)
        friend = next(item for item in report["relationships"] if item["name"] == "周远")
        self.assertNotIn("偿还了", friend["text"])
        self.assertNotIn("还清", friend["text"])

    def test_save_roundtrip_preserves_pending_loan_random_progress_and_continuation(self):
        game = adult_loan_game()
        game.choose("lend", game.state["revision"])
        saved = json.loads(json.dumps(game.to_dict(), ensure_ascii=False))
        restored = LifeGame.from_dict(saved)
        self.assertEqual(restored.to_dict(), game.to_dict())
        self.assertEqual(restored.state["current_event"]["_kind"], "loan_due")
        for _ in range(5):
            selected = choose_feasible(game)
            restored.choose(selected, restored.state["revision"])
            self.assertEqual(restored.to_dict(), game.to_dict())
        # Export/import must not make the caller's save object mutable game state.
        restored.state["stats"]["cash"] += 1
        self.assertNotEqual(restored.state["stats"]["cash"], game.state["stats"]["cash"])
        self.assertEqual(saved["state"]["age"], 21)

    def test_stale_revision_is_rejected_before_any_state_change(self):
        game = LifeGame.new(seed=11)
        old_revision = game.state["revision"]
        choose_feasible(game)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "已经更新"):
            game.choose(game.state["current_event"]["choices"][0]["id"], old_revision)
        self.assertEqual(game.to_dict(), before)

    def test_cash_gate_cannot_be_forced_and_logged_constraint_is_not_preference(self):
        game = LifeGame.new(origin="struggling", seed=5)
        game.state["current_event"] = constrained_offer()
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "现金不足"):
            game.choose("pay", game.state["revision"])
        self.assertEqual(game.to_dict(), before)
        game.choose("decline", game.state["revision"])
        decision = next(entry for entry in reversed(game.state["timeline"])
                        if entry["kind"] == "choice")
        context = decision["context"]
        self.assertEqual(set(context["available_choice_ids"]), {"decline", "search"})
        self.assertTrue(context["opportunity"], "机械上仍有两个方案；这不等于能够自由选择借钱")
        self.assertEqual([item["id"] for item in context["locked_options"]], ["pay"])
        self.assertIn("现金不足", context["locked_options"][0]["reason"])
        self.assertEqual(context["resources_before"]["cash"], before["state"]["stats"]["cash"])
        report = self.assert_report_references_exist(game)
        care = next(item for item in report["patterns"] if item["dimension"] == "care")
        self.assertNotIn(decision["id"], care["evidence_ids"])
        self.assertEqual(care["coverage"], "未观察")
        self.assertIn(decision["id"], report["chapters"][0]["event_ids"])


if __name__ == "__main__":
    unittest.main()
