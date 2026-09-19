"""Reproducible comparisons of scripted play styles, not player predictions.

Run with: python -m game.balance --seeds 6 --output reports/balance-v0.3
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import random
from statistics import mean

from .engine import JOBS, ORIGINS, VERSION, LifeGame


POLICY_VERSION = "1"
MAX_STEPS = 150
POLICIES = {
    "cautious": {"label": "谨慎", "weights": {"health": 12, "energy": 2, "stress": -5,
                                               "cash": 0.005, "education": 2, "skill": 2},
                 "description": "优先即时健康、精力与减压，再考虑学习和收入。健康低于55或压力高于60时偏好rest，否则steady。"},
    "overwork": {"label": "透支", "weights": {"health": 0.2, "energy": 0.1, "stress": 0.5,
                                               "cash": 0.02, "education": 2, "skill": 3},
                 "description": "偏重即时金钱、技能与学识，接受压力增加，工作节奏始终偏好push；不是随机自伤或真实玩家模型。"},
    "random": {"label": "随选", "weights": {},
               "description": "使用独立的固定种子，在当前公开可行选项中均匀随机选择。"},
}


def _score(choice: dict, policy: str, stats: dict) -> float:
    weights = POLICIES[policy]["weights"]
    score = 0.0
    for effect in choice.get("effects", []):
        op = effect["op"]
        if op == "stat":
            score += weights.get(effect["key"], 0) * effect["delta"]
        elif op == "loan":
            score -= weights["cash"] * effect["amount"]
        elif op == "job":
            score += JOBS[effect["value"]][1] / 5000
        elif op == "flag" and effect.get("key") == "work_pace":
            preferred = "push" if policy == "overwork" else (
                "rest" if stats["health"] < 55 or stats["stress"] > 60 else "steady")
            score += 100 if effect["value"] == preferred else -100
    return score


def select_choice(public: dict, authored_event: dict, policy: str, rng: random.Random) -> str:
    """Only select a currently public, executable choice; never inspect outcomes."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")
    event = public.get("event")
    if not isinstance(event, dict) or event.get("id") != authored_event.get("id"):
        raise RuntimeError("公开事件与效果定义不一致")
    available = [choice for choice in event["choices"] if choice["available"]]
    if not available:
        raise RuntimeError(f"没有公开可行选项：{event['id']}")
    if policy == "random":
        return rng.choice(available)["id"]
    authored = {choice["id"]: choice for choice in authored_event["choices"]}
    if any(choice["id"] not in authored for choice in available):
        raise RuntimeError("公开选项缺少效果定义")
    # Python max retains authored/public order on a tie; tie-breaking is stable.
    return max(available, key=lambda choice: _score(authored[choice["id"]], policy, public["stats"]))["id"]


def run_life(seed: int, origin: str, policy: str) -> dict:
    game = LifeGame.new(name="林禾", origin=origin, seed=seed)
    rng = random.Random(f"balance:{POLICY_VERSION}:{seed}")
    minimum_health = game.state["stats"]["health"]
    maximum_stress = game.state["stats"]["stress"]
    timeline_index = 0
    snapshot_count = 0
    missing_snapshots = 0
    steps = []
    offered = locked = fallback = crisis = 0
    while not game.state["finished"]:
        if len(steps) >= MAX_STEPS:
            raise RuntimeError(f"超过{MAX_STEPS}次选择：seed={seed}, origin={origin}, policy={policy}")
        public = game.view()
        authored = game.state["current_event"]
        options = public["event"]["choices"]
        selected = select_choice(public, authored, policy, rng)
        feasible_ids = {choice["id"] for choice in options if choice["available"]}
        if selected not in feasible_ids:
            raise RuntimeError("脚本选择了未公开或被锁定的选项")
        event_id = authored["id"]
        offered += len(options)
        locked += sum(not choice["available"] for choice in options)
        fallback += event_id.startswith("daily.")
        crisis += authored.get("_kind") in {"recovery", "crisis"} or event_id.startswith("system.recovery.")
        steps.append({"age": public["age"], "event_id": event_id, "choice_id": selected,
                      "available_count": len(feasible_ids), "locked_count": len(options) - len(feasible_ids)})
        # A rejected allegedly available command is an error, not an invitation to
        # try other choices or change resources until the run succeeds.
        game.choose(selected, public["revision"])
        stats = game.state["stats"]
        minimum_health = min(minimum_health, stats["health"])
        maximum_stress = max(maximum_stress, stats["stress"])
        for entry in game.state["timeline"][timeline_index:]:
            snapshot = entry.get("stats_after")
            if snapshot is None:
                missing_snapshots += 1
            else:
                snapshot_count += 1
                minimum_health = min(minimum_health, snapshot["health"])
                maximum_stress = max(maximum_stress, snapshot["stress"])
            before = entry.get("context", {}).get("resources_before", {})
            if "health" in before:
                minimum_health = min(minimum_health, before["health"])
            if "stress" in before:
                maximum_stress = max(maximum_stress, before["stress"])
        timeline_index = len(game.state["timeline"])
    kinds = Counter(entry["kind"] for entry in game.state["timeline"])
    return {"seed": seed, "origin": origin, "policy": policy, "steps": len(steps),
            "end_age": game.state["age"], "death_reason": game.state["death_reason"],
            "cash": game.state["stats"]["cash"], "minimum_health": minimum_health,
            "maximum_stress": maximum_stress, "hardship_count": kinds["hardship"],
            "aid_count": kinds["aid"], "crisis_count": crisis,
            "offered_choices": offered, "locked_choices": locked,
            "locked_rate": locked / offered if offered else 0,
            "fallback_count": fallback, "fallback_share": fallback / len(steps) if steps else 0,
            "event_ids": sorted({step["event_id"] for step in steps}),
            "snapshot_records": snapshot_count, "records_without_snapshot": missing_snapshots,
            "trace": steps}


def run_batch(seeds: int = 6) -> dict:
    if not isinstance(seeds, int) or isinstance(seeds, bool) or seeds < 1:
        raise ValueError("seeds 必须是正整数")
    initial = LifeGame.new(seed=0)
    catalog = initial.catalog
    authored_ids = {event["id"] for event in catalog["events"]}
    content_hash = hashlib.sha256(json.dumps(catalog, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
    runs = [run_life(seed, origin, policy) for origin in ORIGINS for policy in POLICIES for seed in range(seeds)]
    groups = []
    for origin in ORIGINS:
        for policy in POLICIES:
            selected = [run for run in runs if run["origin"] == origin and run["policy"] == policy]
            covered = set().union(*(set(run["event_ids"]) for run in selected)) & authored_ids
            fields = ("end_age", "cash", "minimum_health", "maximum_stress", "hardship_count", "aid_count", "crisis_count", "steps")
            offered = sum(run["offered_choices"] for run in selected)
            steps = sum(run["steps"] for run in selected)
            groups.append({"origin": origin, "policy": policy, "runs": len(selected),
                           "metrics": {field: {"mean": mean(run[field] for run in selected),
                                                "min": min(run[field] for run in selected),
                                                "max": max(run[field] for run in selected)} for field in fields},
                           "death_reasons": dict(sorted(Counter(run["death_reason"] for run in selected).items())),
                           "ended_before_82": sum(run["end_age"] < 82 for run in selected),
                           "catalog_events_seen": len(covered), "catalog_events_total": len(authored_ids),
                           "catalog_coverage": len(covered) / len(authored_ids) if authored_ids else 0,
                           "locked_rate": sum(run["locked_choices"] for run in selected) / offered if offered else 0,
                           "fallback_share": sum(run["fallback_count"] for run in selected) / steps if steps else 0})
    # Repeat one complete run, including trace, to catch hidden randomness/state leak.
    repeat = run_life(runs[0]["seed"], runs[0]["origin"], runs[0]["policy"])
    if repeat != runs[0]:
        raise RuntimeError("相同种子与策略未产生相同结果")
    return {"report_version": "0.3", "engine_version": VERSION,
            "engine_sha256": hashlib.sha256(Path(__file__).with_name("engine.py").read_bytes()).hexdigest(),
            "python_version": platform.python_version(),
            "content_version": catalog.get("version"), "content_sha256": content_hash,
            "policy_version": POLICY_VERSION, "policies": POLICIES,
            "seed_values": list(range(seeds)), "total_runs": len(runs),
            "determinism_check": {"seed": runs[0]["seed"], "origin": runs[0]["origin"],
                                  "policy": runs[0]["policy"], "identical": True},
            "notes": ["这是可复现的脚本策略比较，不预测真实玩家，也不预设应达到的死亡率。",
                      "各组使用相同种子集合；分支消耗随机数的次数可能不同，因此不保证各组遭遇完全相同的外生事件。",
                      "最低健康和最高压力来自决策边界、选择前资源和已有stats_after快照；未记录的单次操作中间态不作推断。",
                      "生活紧缩、救助按timeline.kind计数；危机按实际展示的recovery/crisis事件计数。",
                      "锁选率=所有决策中锁定选项数/展示选项数；fallback占比=普通日常兜底事件决策数/总决策数。",
                      "事件覆盖只计算静态目录ID；分支互斥、年龄与身份条件使100%覆盖并非单局目标，系统事件不进入分母。",
                      "评分只读取公开可行性与已定义效果：属性按列出的权重求和，借款按支出计，职业加基础年收入/5000，匹配工作节奏加100否则减100；同分按展示顺序。"],
            "groups": groups, "runs": runs}


def render_markdown(report: dict) -> str:
    origins = {"ordinary": "普通", "struggling": "拮据", "comfortable": "宽裕"}
    lines = ["# v0.3 脚本试玩对比", "", f"共 {report['total_runs']} 局；每组使用种子 {report['seed_values']}。",
             f"内容版本：`{report['content_version']}`；内容 SHA-256：`{report['content_sha256']}`。", "",
             f"规则 SHA-256：`{report['engine_sha256']}`；Python `{report['python_version']}`；策略版本 `{report['policy_version']}`。", "",
             "## 策略", ""]
    for key, policy in report["policies"].items():
        lines.append(f"- **{policy['label']}**：{policy['description']} 权重：`{json.dumps(policy['weights'], ensure_ascii=False)}`。")
    lines.extend(["", "## 可比汇总", "", "数值为组内均值；年龄另附范围。次数只描述记录，不代表人格或玩家偏好。", "",
                  "| 出身 | 策略 | 终局年龄（范围） | 现金 | 最低健康 | 最高压力 | 紧缩/救助/危机 | 锁选率 | 兜底占比 | 目录覆盖 |",
                  "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |"])
    for group in report["groups"]:
        metrics = group["metrics"]
        age = metrics["end_age"]
        counts = "/".join(f"{metrics[key]['mean']:.1f}" for key in ("hardship_count", "aid_count", "crisis_count"))
        lines.append(f"| {origins[group['origin']]} | {POLICIES[group['policy']]['label']} | {age['mean']:.1f}（{age['min']}–{age['max']}） | {metrics['cash']['mean']:.0f} | {metrics['minimum_health']['mean']:.1f} | {metrics['maximum_stress']['mean']:.1f} | {counts} | {group['locked_rate']:.1%} | {group['fallback_share']:.1%} | {group['catalog_events_seen']}/{group['catalog_events_total']} |")
    lines.extend(["", "## 终局原因", ""])
    for group in report["groups"]:
        reasons = "；".join(f"{reason} {count}局" for reason, count in group["death_reasons"].items())
        lines.append(f"- {origins[group['origin']]} / {POLICIES[group['policy']]['label']}：{reasons}；82岁前结束 {group['ended_before_82']}局。")
    lines.extend(["", "## 解释边界与复现", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    missing = sum(run["records_without_snapshot"] for run in report["runs"])
    lines.append(f"- 缺少stats_after的记录：{missing}条；相同种子完整轨迹重跑核对：通过。逐局指标与选择轨迹见同名前缀JSON。")
    lines.append(f"- 复现命令：`python -m game.balance --seeds {len(report['seed_values'])} --output reports/balance-v0.3`。")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=6, help="每组种子数量，使用0至N-1")
    parser.add_argument("--output", default="reports/balance-v0.3", help="JSON和Markdown输出文件的共同前缀")
    args = parser.parse_args(argv)
    report = run_batch(args.seeds)
    prefix = Path(args.output)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, md_path = Path(str(prefix) + ".json"), Path(str(prefix) + ".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"{report['total_runs']} runs: {json_path} / {md_path}")


if __name__ == "__main__":
    main()
