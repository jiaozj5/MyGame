"""Contract tests for the standalone LOL simulator service and CLI."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lol_sim.server import SimulatorServer


ROOT = Path(__file__).resolve().parents[1]


class LolServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = SimulatorServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, body=None, *, content_type="application/json", headers=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode())
        request_headers = {} if headers is None else dict(headers)
        if data is not None:
            request_headers.setdefault("Content-Type", content_type)
        request = Request(self.base + path, data=data, headers=request_headers)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = raw.decode("utf-8", errors="replace")
                return response.status, payload
        except HTTPError as error:
            raw = error.read()
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = raw.decode("utf-8", errors="replace")
            return error.code, payload

    def test_health_catalog_and_static_page(self):
        status, health = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["ok"], True)
        self.assertEqual(health["service"], "toplane-lab")
        status, catalog = self.request("/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(catalog["patch"], "26.18")
        self.assertIn("Garen", catalog["champions"])
        self.assertIn("1055", catalog["items"])
        status, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("上路 1–6 级对线实验室", html)

    def test_simulate_and_optimize_use_real_engine(self):
        config = {
            "duration": 30,
            "seed": 7,
            "player": {"champion": "Garen"},
            "opponent": {"champion": "Darius"},
        }
        status, result = self.request("/api/simulate", config)
        self.assertEqual(status, 200)
        self.assertEqual(result["patch"], "26.18")
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["player"]["champion"], "Garen")
        config["search"] = {"runes": ["conqueror", "grasp"], "seeds": [7]}
        status, result = self.request("/api/optimize", config)
        self.assertEqual(status, 200)
        self.assertEqual(result["search"]["candidates"], 2)
        self.assertEqual(result["search"]["trials"], 2)
        self.assertEqual(len(result["ranking"]), 2)

    def test_invalid_json_unknown_champion_and_oversized_request(self):
        status, payload = self.request("/api/simulate", b"{not json")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        status, payload = self.request("/api/simulate", {"player": {"champion": "Teemo"}})
        self.assertEqual(status, 400)
        self.assertIn("尚未实现英雄", payload["error"])
        # Declare an oversized body while keeping the test payload tiny; the
        # handler rejects by Content-Length before reading attacker-controlled
        # bytes, which also keeps the connection reusable on Windows.
        status, payload = self.request("/api/simulate", b"{}", headers={"Content-Length": "1000001"})
        self.assertEqual(status, 413)
        self.assertIn("1 MB", payload["error"])
        status, payload = self.request("/api/simulate", {"duration": 10 ** 1000})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_origin_and_content_type_guards(self):
        status, payload = self.request("/api/simulate", {"duration": 1}, headers={"Origin": "https://example.invalid"})
        self.assertEqual(status, 403)
        status, payload = self.request("/api/simulate", {"duration": 1}, content_type="text/plain")
        self.assertEqual(status, 415)

    def test_cli_catalog_and_simulate(self):
        command = [sys.executable, "-X", "utf8", "-m", "lol_sim", "catalog"]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        catalog = json.loads(completed.stdout)
        self.assertIn("Darius", catalog["champions"])
        config = json.dumps({"duration": 5, "seed": 3})
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "lol_sim", "simulate", "--config", "-"],
            cwd=ROOT, input=config, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("summary", json.loads(completed.stdout))
        optimize_config = json.dumps({"duration": 2, "seed": 3, "search": {"runes": ["conqueror", "grasp"], "seeds": [3]}})
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "lol_sim", "optimize", "--config", "-"],
            cwd=ROOT, input=optimize_config, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["search"]["trials"], 2)


if __name__ == "__main__":
    unittest.main()
