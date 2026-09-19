"""Local HTTP entry point for the independent top-lane simulator."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from .catalog import get_catalog
from .engine import optimize, simulate


WEB_ROOT = Path(__file__).resolve().parents[1] / "lol_web"
VERSION = "0.1.0"
MAX_REQUEST_BYTES = 1_000_000


def _invalid_number(value):
    raise ValueError(f"JSON 不能包含 {value}。")


class SimulatorServer(ThreadingHTTPServer):
    """A stateless, loopback-only server; each run receives its own config."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address=("127.0.0.1", 8767)):
        if address[0] not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("模拟器服务只能监听本机地址。")
        super().__init__(address, SimulatorHandler)


class SimulatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(200, {"ok": True, "service": "toplane-lab", "version": VERSION})
        if path == "/api/catalog":
            try:
                return self._json(200, get_catalog())
            except Exception:
                self.log_error("Catalog could not be read")
                return self._json(500, {"error": "模拟器数据目录读取失败，请检查本地数据文件。"})
        if path.startswith("/api/"):
            return self._json(404, {"error": "没有这个接口。"})
        return super().do_GET()

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != self.headers.get("Host"):
                return self._json(403, {"error": "请从当前模拟器页面发起请求。"})
        operation = {
            "/api/simulate": simulate,
            "/api/optimize": optimize,
        }.get(urlparse(self.path).path)
        if operation is None:
            return self._json(404, {"error": "没有这个接口。"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                return self._json(413, {"error": "请求需要是 1 MB 以内的 JSON 配置。"})
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                return self._json(415, {"error": "请使用 application/json 发送配置。"})
            config = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=_invalid_number)
            if not isinstance(config, dict):
                raise ValueError("配置需要是一个 JSON 对象。")
            return self._json(200, operation(config))
        except (ValueError, KeyError, TypeError, UnicodeError, OverflowError) as error:
            return self._json(400, {"error": str(error) or "配置格式不正确。"})
        except Exception:
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": "本次模拟未完成，请查看终端中的错误信息。"})


def serve(port=8767):
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("端口须为 0 到 65535 之间的整数。")
    server = SimulatorServer(("127.0.0.1", port))
    print(f"Top-lane simulator ready: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="LOL 上路 1–6 级对线实验室")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
