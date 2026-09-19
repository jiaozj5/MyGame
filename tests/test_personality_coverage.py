import json
from pathlib import Path
import unittest

from game.content_check import check_personality_coverage
from game.engine import _catalog


ROOT = Path(__file__).resolve().parents[1]


class PersonalityCoverageTests(unittest.TestCase):
    def test_coverage_matrix_points_to_real_dimension_annotated_events(self):
        catalog = _catalog()
        dimensions = {
            event["id"]: {
                item.get("dimension", item.get("dimension_id"))
                for choice in event.get("choices", [])
                for item in choice.get("observations", [])
            }
            for event in catalog["events"]
        }
        self.assertEqual(check_personality_coverage(
            event_ids=set(dimensions), event_dimensions=dimensions), [])

    def test_event_assessment_metadata_is_complete_and_observations_have_facets(self):
        for filename in ("life-events.json", "society-events.json"):
            data = json.loads((ROOT / "content" / filename).read_text(encoding="utf-8"))
            self.assertTrue(data["events"])
            for event in data["events"]:
                self.assertTrue(event.get("episode_group"))
                context = event.get("assessment_context")
                self.assertIsInstance(context, dict)
                for field in ("life_stage", "pressure_band", "relationship_scope",
                              "scale", "information_level", "time_horizon"):
                    self.assertIsInstance(context.get(field), str)
                for choice in event["choices"]:
                    for observation in choice.get("observations", []):
                        self.assertIsInstance(observation.get("facet"), str)
                        self.assertTrue(observation["facet"])


if __name__ == "__main__":
    unittest.main()
