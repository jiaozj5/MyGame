from copy import deepcopy
import unittest

from game.content_check import check_catalog


def event(event_id="event", minimum=18, maximum=30):
    return {"id": event_id, "title": "事件", "category": "日常", "scene": "town",
            "age_min": minimum, "age_max": maximum, "actors": [], "requires": [],
            "text": "{name}在{year}年作出选择。", "choices": [
                {"id": "a", "label": "行动", "effects": [], "requires": [], "observations": []},
                {"id": "b", "label": "等待", "effects": [], "requires": [], "observations": []}]}


class ContentCheckTests(unittest.TestCase):
    def codes(self, events, level="errors"):
        return {item["code"] for item in check_catalog({"events": events})[level]}

    def test_unknown_fields_wrong_types_templates_and_dimensions_are_errors(self):
        item = event()
        item["requires"] = [{"path": "stats.heath", "op": "gte", "value": 5},
                            {"path": "npc.friend.alive", "op": "eq", "value": 1}]
        item["text"] = "{npc.friend.unknown}"
        item["choices"][0]["observations"] = [{"dimension": "mind_reading", "behavior": "未知"}]
        self.assertEqual(self.codes([item]), {"unknown_path", "condition_type", "unknown_template_path",
                                              "unknown_observation_dimension"})

    def test_content_flag_producers_are_discovered_and_late_producer_is_only_warning(self):
        consumer = event("consumer", 18, 20)
        consumer["requires"] = [{"path": "flags.custom_chain", "op": "eq", "value": True}]
        producer = event("producer", 30, 40)
        producer["choices"][0]["effects"] = [{"op": "flag", "key": "custom_chain", "value": True}]
        report = check_catalog({"events": [consumer, producer]})
        self.assertEqual(report["errors"], [])
        self.assertEqual({item["code"] for item in report["warnings"]}, {"producer_after_consumer"})
        producer["age_min"] = 20
        self.assertEqual(check_catalog({"events": [consumer, producer]})["warnings"], [])
        self.assertIn("flag_without_source", self.codes([consumer]))

    def test_dead_person_can_be_remembered_but_cannot_act_or_receive_active_effects(self):
        memory = event("memory")
        memory["requires"] = [{"path": "npc.friend.alive", "op": "eq", "value": False}]
        self.assertEqual(self.codes([memory]), set())
        active = deepcopy(memory)
        active["actors"] = ["friend"]
        self.assertIn("dead_active_actor", self.codes([active]))
        memory["choices"][0]["effects"] = [{"op": "relation", "npc": "friend", "delta": 2}]
        self.assertIn("dead_active_actor", self.codes([memory]))

    def test_duplicate_ids_are_errors_while_implicit_absence_can_be_a_warning(self):
        first = event()
        self.assertIn("duplicate_event_id", self.codes([first, deepcopy(first)]))
        first["choices"][1]["id"] = "a"
        self.assertIn("event_contract", self.codes([first]))
        missing = event()
        missing["requires"] = [{"path": "flags.never_written", "op": "exists", "value": False}]
        report = check_catalog({"events": [missing]})
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"][0]["code"], "flag_without_source")

    def test_world_response_requires_known_domain_and_actual_world_gate(self):
        item = event()
        item["world_domain"] = "unknown_domain"
        self.assertEqual(self.codes([item]), {"unknown_world_domain", "missing_world_gate"})

    def test_world_conditions_reject_typos_invalid_modes_and_thresholds(self):
        item = event()
        item["requires"] = [{"path": "world.metrics.typo", "op": "gte", "value": 5},
                            {"path": "world.modes.energy", "op": "eq", "value": "magic"},
                            {"path": "world.metrics.food_security", "op": "lte", "value": 101}]
        self.assertEqual(self.codes([item]), {"unknown_path", "unknown_world_mode", "world_threshold_range"})


if __name__ == "__main__":
    unittest.main()
