"""Local-only playable life game server. Standard library, no external services."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlparse

from game.engine import LifeGame, RuleError, VIEW_VERSION


WEB = Path(__file__).resolve().parents[1] / "web"


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, GameHandler)
        self.games = {}
        self.game_lock = threading.RLock()


class GameHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/health":
            return self._json(200, {"ok": True, "version": VIEW_VERSION})
        if self.path.startswith("/api/"):
            return self._json(404, {"error": "没有这个接口。"})
        return super().do_GET()

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.netloc != self.headers.get("Host"):
                return self._json(403, {"error": "请从当前游戏页面操作。"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 20_000_000:
                return self._json(413, {"error": "请求或存档大小不合适。"})
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("请求需要是一个对象。")
            with self.server.game_lock:
                if self.path == "/api/new":
                    name = str(body.get("name", "林禾")).strip()[:16] or "林禾"
                    origin_name = body.get("origin", "ordinary")
                    seed = body.get("seed")
                    if seed is None:
                        seed = secrets.randbelow(2**31)
                    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**31:
                        raise ValueError("人生种子需要是 0 到 2147483647 之间的整数。")
                    game = LifeGame.new(name=name, origin=origin_name, seed=seed)
                    game_id = self._register(game)
                elif self.path == "/api/resume":
                    game = LifeGame.from_dict(body["save"])
                    game_id = self._register(game)
                elif self.path in {"/api/choose", "/api/people", "/api/person", "/api/social", "/api/social-plan"}:
                    game_id = body.get("game_id")
                    game = self.server.games.get(game_id)
                    if game is None:
                        return self._json(409, {"error": "游戏连接已更新，请刷新页面继续自动存档。", "code": "session_expired"})
                    if self.path == "/api/people":
                        return self._json(200, game.people(query=body.get("query", ""), group=body.get("group", "known"),
                            offset=body.get("offset", 0), limit=body.get("limit", 24)))
                    if self.path == "/api/person":
                        return self._json(200, game.person(body["npc_id"]))
                    if self.path == "/api/social":
                        game.social(body["npc_id"], body["action"], body["revision"])
                    elif self.path == "/api/social-plan":
                        game.set_social_plan(body["plan"], body["revision"])
                    else:
                        game.choose(body["choice_id"], body["revision"])
                else:
                    return self._json(404, {"error": "没有这个接口。"})
                return self._json(200, {"game_id": game_id, "view": game.view(), "save": game.to_dict()})
        except (RuleError, ValueError, KeyError, TypeError) as error:
            return self._json(400, {"error": f"这一步未能完成：{error}"})
        except Exception:
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": "游戏遇到了问题，当前浏览器存档仍然保留。请刷新后重试。"})

    def _register(self, game):
        # A population save holds thousands of people and their histories.
        while len(self.server.games) >= 8:
            self.server.games.pop(next(iter(self.server.games)))
        game_id = secrets.token_urlsafe(24)
        self.server.games[game_id] = game
        return game_id


def main():
    parser = argparse.ArgumentParser(description="浮生 · 青溪镇人生游戏")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = GameServer(("127.0.0.1", args.port))
    print(f"Game ready: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
