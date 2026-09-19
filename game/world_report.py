"""Reproducible fictional-world coverage; sampling does not prove completeness."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .world import MODES, VERSION, advance_world, load_catalog, modifiers, new_world, validate_world


def run_batch(seeds=128, years=82):
    if type(seeds) is not int or seeds < 1 or type(years) is not int or years < 1:
        raise ValueError("seeds 和 years 必须是正整数")
    catalog = load_catalog()
    seen, domains, scopes = Counter(), Counter(), Counter()
    mode_values = {key: set() for key in MODES}
    signatures, runs = set(), []
    for seed in range(seeds):
        initial = new_world(seed, 1)
        original = json.dumps(initial, sort_keys=True)
        final = advance_world(initial, years + 1, catalog)
        validate_world(final, catalog, expected_year=years + 1)
        if json.dumps(initial, sort_keys=True) != original:
            raise AssertionError("推进世界修改了输入状态")
        # JSON round-trip halfway through must produce the same future. This
        # also compares a single jump against multiple time advances.
        middle = advance_world(initial, 1 + years // 2, catalog)
        resumed = advance_world(json.loads(json.dumps(middle)), years + 1, catalog)
        if resumed != final:
            raise AssertionError(f"分段推进或存档接续发生分叉：{seed}")
        trace = [row["event_id"] for row in final["history"]]
        signatures.add(tuple(trace))
        seen.update(trace)
        domains.update(row["domain"] for row in final["history"])
        scopes.update(row["scope"] for row in final["history"])
        modes = dict(final["initial_modes"])
        for key, value in modes.items():
            mode_values[key].add(value)
        for row in final["history"]:
            for effect in row["contract"]["effects"]:
                if effect["op"] == "mode":
                    mode_values[effect["key"]].add(effect["value"])
        runs.append({"seed": seed, "events": len(trace), "event_ids": trace,
                     "final_metrics": final["metrics"], "final_modes": final["modes"],
                     "modifiers": modifiers(final)})
    ids = {event["id"] for event in catalog["events"]}
    root = Path(__file__).resolve().parents[1]
    paths = ["game/world.py", "game/world_report.py", "content/world-events.json"]
    hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
    return {"version": VERSION, "seeds": seeds, "years": years, "file_hashes": hashes,
            "catalog_events": len(ids), "events_seen": len(seen), "events_unseen": sorted(ids - seen.keys()),
            "occurrences": dict(sorted(seen.items())), "unique_histories": len(signatures),
            "domains": [{"id": domain["id"], "label": domain["label"],
                         "authored": sum(event["domain"] == domain["id"] for event in catalog["events"]),
                         "seen": sum(event["domain"] == domain["id"] and event["id"] in seen for event in catalog["events"]),
                         "occurrences": domains[domain["id"]]} for domain in catalog["domains"]],
            "scopes": dict(sorted(scopes.items())),
            "modes_seen": {key: sorted(values) for key, values in mode_values.items()},
            "checks": {"history_replay": True, "input_unchanged": True,
                       "split_advance_and_json_resume": True},
            "note": "覆盖只表示这批确定种子曾触发的资产；未出现不等于不可达，出现也不证明叙事质量、现实真实性或全部未来覆盖。",
            "runs": runs}


def markdown(report):
    lines = ["# v0.4 架空世界批量验证", "",
             f"从新历 1 年开始，{report['seeds']} 个种子分别推进 {report['years']} 年。",
             f"出现 {report['events_seen']} / {report['catalog_events']} 个宏观事件，形成 {report['unique_histories']} 条不同的事件序列。", "",
             "每个世界均检查：前提与冷却、按历史重放状态、时间不倒退、模式互斥、指标范围、原输入不变、分段推进及 JSON 接续与一次推进完全一致。", "",
             "| 领域 | 编写事件 | 本批出现 | 触发总次数 |", "| --- | ---: | ---: | ---: |"]
    lines.extend(f"| {row['label']} | {row['authored']} | {row['seen']} | {row['occurrences']} |" for row in report["domains"])
    lines.extend(["", "## 出现过的发展模式", ""])
    lines.extend(f"- {key}：{'、'.join(MODES[key][value] for value in values)}" for key, values in report["modes_seen"].items())
    lines.extend(["", "## 本批未触发的事件", "", ", ".join(report["events_unseen"]) or "无。", "", report["note"], "",
                  "此报告单独验证宏观世界；个人事件和 NPC 的接续、一致性由单元测试与试玩检查。", "",
                  "## 复现", "", "```powershell",
                  f"python -X utf8 -m game.world_report --seeds {report['seeds']} --years {report['years']} --output reports/world-v0.4",
                  "```", "", "### 文件 SHA-256", ""])
    lines.extend(f"- `{path}`：`{digest}`" for path, digest in report["file_hashes"].items())
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=128)
    parser.add_argument("--years", type=int, default=82)
    parser.add_argument("--output", type=Path, default=Path("reports/world-v0.4"))
    args = parser.parse_args(argv)
    report = run_batch(args.seeds, args.years)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.output) + ".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(str(args.output) + ".md").write_text(markdown(report), encoding="utf-8")
    print(f"{report['events_seen']}/{report['catalog_events']} events; {report['unique_histories']} unique histories; all consistency checks passed")


if __name__ == "__main__":
    main()
