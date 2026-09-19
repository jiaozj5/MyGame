"""Command-line access: serve, catalog, simulate, and optimize."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Windows launched from a non-UTF-8 console otherwise encodes JSON with the
# system code page, which makes the machine-readable CLI impossible to pipe.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .catalog import get_catalog
from .engine import optimize, simulate


def _invalid_number(value):
    raise ValueError(f"JSON 不能包含 {value}。")


def read_config(filename):
    source = sys.stdin.read() if filename == "-" else Path(filename).read_text(encoding="utf-8-sig")
    config = json.loads(source, parse_constant=_invalid_number)
    if not isinstance(config, dict):
        raise ValueError("配置需要是一个 JSON 对象。")
    return config


def write_result(result, filename=None):
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if filename and filename != "-":
        target = Path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv=None):
    parser = argparse.ArgumentParser(description="LOL 上路 1–6 级对线实验室：本地页面与批量测试接口")
    commands = parser.add_subparsers(dest="command", required=True)
    server_command = commands.add_parser("serve", help="启动本机网页（默认端口 8767）")
    server_command.add_argument("--port", type=int, default=8767)
    catalog_command = commands.add_parser("catalog", help="导出英雄、符文、装备与数据版本目录")
    catalog_command.add_argument("--output", help="输出 JSON 文件；省略或 '-' 为标准输出")
    for name, help_text in (("simulate", "运行一组对线配置"), ("optimize", "比较候选配置并给出模型内建议")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--config", required=True, help="JSON 配置文件；'-' 从标准输入读取")
        command.add_argument("--output", help="输出 JSON 文件；省略或 '-' 为标准输出")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from .server import serve
            serve(args.port)
        elif args.command == "catalog":
            write_result(get_catalog(), args.output)
        else:
            operation = {"simulate": simulate, "optimize": optimize}[args.command]
            write_result(operation(read_config(args.config)), args.output)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
        parser.exit(2, f"错误：{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
