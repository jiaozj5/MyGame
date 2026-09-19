import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.server import GameServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = GameServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, path, body, headers=None):
        request = Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type":"application/json", **(headers or {})})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_new_choice_stale_command_and_resume(self):
        status, new = self.post("/api/new", {"name":"测试人物", "origin":"ordinary", "seed":42})
        self.assertEqual(status, 200)
        option = next(c for c in new["view"]["event"]["choices"] if c["available"])
        command = {"game_id":new["game_id"], "revision":new["view"]["revision"], "choice_id":option["id"]}
        status, chosen = self.post("/api/choose", command)
        self.assertEqual(status, 200)
        self.assertGreater(chosen["view"]["revision"], new["view"]["revision"])
        status, error = self.post("/api/choose", command)
        self.assertEqual(status, 400)
        self.assertIn("error", error)
        status, resumed = self.post("/api/resume", {"save":chosen["save"]})
        self.assertEqual(status, 200)
        self.assertEqual(resumed["save"], chosen["save"])
        self.assertNotEqual(resumed["game_id"], new["game_id"])

    def test_bad_save_does_not_replace_active_game(self):
        _, new = self.post("/api/new", {"seed":7})
        status, error = self.post("/api/resume", {"save":{"schema_version":"unknown"}})
        self.assertEqual(status, 400)
        self.assertIn("error", error)
        self.assertIn(new["game_id"], self.server.games)

    def test_legacy_resume_preserves_history_and_exposes_current_forecast(self):
        path = Path(__file__).parent / "fixtures" / "v02-save.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        status, upgraded = self.post("/api/resume", {"save": original})
        self.assertEqual(status, 200)
        self.assertEqual(upgraded["save"]["schema_version"], "1.3.0")
        self.assertEqual(upgraded["view"]["version"], "0.5.0")
        self.assertTrue(upgraded["view"]["migration_note"])
        for key in ("timeline", "current_event", "random_counter", "revision"):
            self.assertEqual(upgraded["save"]["state"][key], original["state"][key], key)
        outlook = upgraded["view"]["outlook"]
        self.assertEqual(outlook["balance"], outlook["income"] - outlook["expenses"])
        self.assertIn(outlook["pace"], {"steady", "push", "rest"})
        self.assertIsInstance(outlook["warnings"], list)
        self.assertEqual(original["schema_version"], "1.0.0")

    def test_health_reports_the_running_game_version(self):
        with urlopen(self.base + "/api/health", timeout=10) as response:
            self.assertEqual(json.load(response), {"ok": True, "version": "0.5.0"})

    def test_world_birth_and_previous_version_resume_do_not_invent_history(self):
        status, new = self.post("/api/new", {"seed": 14})
        self.assertEqual(status, 200)
        self.assertEqual(new["view"]["year"], 7)
        self.assertEqual(new["view"]["world"]["calendar"], "新历")
        self.assertEqual(len(new["view"]["world"]["metrics"]), 20)
        self.assertTrue(all(row["year"] <= 7 for row in new["view"]["world"]["history"]))
        original = json.loads((Path(__file__).parent / "fixtures/v03-save.json").read_text(encoding="utf-8"))
        status, resumed = self.post("/api/resume", {"save": original})
        self.assertEqual(status, 200)
        self.assertEqual(resumed["save"]["state"]["timeline"], original["state"]["timeline"])
        self.assertEqual(resumed["view"]["world"]["start_year"], original["state"]["year"])
        self.assertEqual(resumed["view"]["world"]["history"], [])
        status, repeat = self.post("/api/resume", {"save": resumed["save"]})
        self.assertEqual(status, 200)
        self.assertEqual(repeat["save"], resumed["save"])

    def test_cross_origin_command_is_rejected(self):
        status, _ = self.post("/api/new", {}, {"Origin":"https://example.invalid"})
        self.assertEqual(status, 403)

    def test_population_reads_and_social_commands_preserve_revision_contract(self):
        _, new = self.post("/api/new", {"seed": 71})
        game_id = new["game_id"]
        status, people = self.post("/api/people", {"game_id": game_id})
        self.assertEqual(status, 200)
        self.assertEqual(people["capacity"], 2000)
        self.assertNotIn("save", people)
        self.assertTrue(all("traits" not in person and "stats" not in person for person in people["people"]))
        person = next(row for row in people["people"] if row["id"].startswith("npc-") and row["contact"] == "direct")
        status, detail = self.post("/api/person", {"game_id": game_id, "npc_id": person["id"]})
        self.assertEqual(status, 200)
        action = next(item for item in detail["actions"] if item["id"] == "talk" and item["available"])
        command = {"game_id": game_id, "npc_id": person["id"], "action": action["id"], "revision": 0}
        status, social = self.post("/api/social", command)
        self.assertEqual(status, 200)
        self.assertEqual(social["view"]["revision"], 1)
        self.assertEqual(social["view"]["age"], new["view"]["age"])
        self.assertEqual(social["save"]["state"]["slot_index"], 0)
        self.assertEqual(social["view"]["stats"]["energy"], new["view"]["stats"]["energy"] - action["costs"]["energy"])
        self.assertEqual(self.post("/api/social", command)[0], 400)
        status, planned = self.post("/api/social-plan", {"game_id": game_id, "plan": "community", "revision": 1})
        self.assertEqual(status, 200)
        self.assertEqual(planned["view"]["population"]["plan"], "community")
        self.assertEqual(planned["view"]["revision"], 2)
        self.assertEqual(self.post("/api/people", {"game_id": game_id, "limit": 2000})[0], 400)

    def test_static_root_exposes_only_game_files(self):
        with urlopen(self.base + "/", timeout=10) as response:
            self.assertIn("浮生", response.read().decode("utf-8"))
        for path in ("/game/engine.py", "/content/life-events.json"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.base + path, timeout=10)
            self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
