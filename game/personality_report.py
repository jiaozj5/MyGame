"""Generate an auditable content-coverage report for the v0.6 portrait system."""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path

from .engine import ROOT, _catalog
from .content_check import check_personality_coverage


def build_report(catalog: dict | None = None) -> dict:
    catalog = catalog or _catalog()
    dimensions = defaultdict(lambda: {
        "event_ids": set(), "choice_count": 0, "behavior_counts": Counter(),
        "facet_counts": Counter(), "life_stages": Counter(),
        "pressure_bands": Counter(), "relationship_scopes": Counter(),
        "information_levels": Counter(),
    })
    event_dimensions = {}
    for event in catalog.get("events", []):
        event_id = event["id"]
        context = event.get("assessment_context", {})
        observed = set()
        for choice in event.get("choices", []):
            for observation in choice.get("observations", []):
                dimension = observation.get("dimension", observation.get("dimension_id"))
                if not dimension:
                    continue
                observed.add(dimension)
                row = dimensions[dimension]
                row["event_ids"].add(event_id)
                row["choice_count"] += 1
                row["behavior_counts"][observation.get("behavior", "未命名")] += 1
                row["facet_counts"][observation.get("facet", "general")] += 1
                row["life_stages"][context.get("life_stage", "unknown")] += 1
                row["pressure_bands"][context.get("pressure_band", "unknown")] += 1
                row["relationship_scopes"][context.get("relationship_scope", "unknown")] += 1
                row["information_levels"][context.get("information_level", "unknown")] += 1
        event_dimensions[event_id] = observed
    coverage_errors = check_personality_coverage(
        event_ids=set(event_dimensions), event_dimensions=event_dimensions)
    serialized = {}
    for dimension, row in sorted(dimensions.items()):
        serialized[dimension] = {
            "event_count": len(row["event_ids"]),
            "event_ids": sorted(row["event_ids"]),
            "choice_count": row["choice_count"],
            "behavior_counts": dict(sorted(row["behavior_counts"].items())),
            "facet_counts": dict(sorted(row["facet_counts"].items())),
            "life_stages": dict(sorted(row["life_stages"].items())),
            "pressure_bands": dict(sorted(row["pressure_bands"].items())),
            "relationship_scopes": dict(sorted(row["relationship_scopes"].items())),
            "information_levels": dict(sorted(row["information_levels"].items())),
        }
    return {"schema_version": "0.1.0", "event_count": len(event_dimensions),
            "dimensions": serialized, "coverage_errors": coverage_errors,
            "note": "这是内容入口覆盖报告，不是角色人格测量结果。"}


def _markdown(report: dict) -> str:
    lines = ["# 人物画像事件覆盖报告 v0.6", "", report["note"], "",
             f"事件总数：{report['event_count']}；覆盖检查错误：{len(report['coverage_errors'])}", "",
             "| 维度 | 事件数 | 标注选择数 | 年龄阶段 | 压力 | 关系范围 | 信息条件 |", "|---|---:|---:|---|---|---|---|"]
    for dimension, row in report["dimensions"].items():
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            dimension, row["event_count"], row["choice_count"],
            "、".join(f"{k}:{v}" for k, v in row["life_stages"].items()),
            "、".join(f"{k}:{v}" for k, v in row["pressure_bands"].items()),
            "、".join(f"{k}:{v}" for k, v in row["relationship_scopes"].items()),
            "、".join(f"{k}:{v}" for k, v in row["information_levels"].items())))
    if report["coverage_errors"]:
        lines += ["", "## 覆盖错误", ""]
        lines.extend(f"- {item['message']}" for item in report["coverage_errors"])
    lines += ["", "## 解释", "", "事件数表示至少有一个选项标注了该维度。选择数是内容标注数量，不是玩家行为次数。实际人物志只统计玩家在运行中真正遇到且未受硬性约束的记录。"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/personality-coverage-v0.6")
    args = parser.parse_args(argv)
    report = build_report()
    base = args.output.with_suffix("") if args.output.suffix in {".json", ".md"} else args.output
    json_path = Path(str(base) + ".json")
    markdown_path = Path(str(base) + ".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(f"wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
