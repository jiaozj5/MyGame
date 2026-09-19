"""Reproducible population playthroughs; scripted behavior is not a player model.

Run ``python -m game.population_report --seeds 4 --output reports/population-v0.5``.
Only public, executable actions are selected. Developer-only aggregate visibility
counts never turn hidden facts about an individual into player-facing knowledge.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import random
from statistics import mean, median
from time import perf_counter
from unittest.mock import patch


POLICY_VERSION = "1"
MAX_LIFE_CHOICES = 150
MAX_CONTACTS_PER_VISITED_YEAR = 2
POLICIES = {
    "annual_only": "保留默认年度社交安排，不额外点击联系。人生决策采用谨慎脚本。",
    "keep_contact": "采用相同人生评分；每个实际停留的新年份，轮换已知人物，最多执行两次公开可行的联系。",
}


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _timed(call, samples: list[float]):
    started = perf_counter()
    result = call()
    samples.append((perf_counter() - started) * 1000)
    return result


def _timing(samples: list[float]) -> dict:
    """Describe observed wall time without asserting machine-specific budgets."""
    return {"samples": len(samples), "mean_ms": mean(samples) if samples else None,
            "median_ms": median(samples) if samples else None,
            "max_ms": max(samples) if samples else None,
            "total_ms": sum(samples)}


def _source_hashes() -> dict:
    root = Path(__file__).resolve().parents[1]
    paths = [root / "game" / name for name in
             ("engine.py", "population.py", "world.py", "balance.py", "portrait.py", "population_report.py")]
    paths += sorted((root / "content").glob("*.json"))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def _stable_run(run: dict) -> dict:
    """Exclude timings only; deterministic state, counts and traces must match."""
    return {key: value for key, value in run.items() if key != "performance"}


def population_counts(pop: dict) -> dict:
    """Keep simulation detail, tracking and actual acquaintance independent."""
    people = pop["people"]
    if not isinstance(people, dict):
        raise ValueError("population.people 必须是 ID 到人物的映射")
    known = [person for person in people.values() if person["knowledge"]["contact"] != "none"]
    direct = [person for person in known if person["knowledge"]["contact"] == "direct"]
    tracked = pop["tracked"]
    if len(tracked) != len(set(tracked)) or not set(tracked) <= people.keys():
        raise ValueError("关注名单存在重复或未知人物")
    statuses = Counter(person["status"] for person in people.values())
    if not set(statuses) <= {"alive", "dead", "unborn"}:
        raise ValueError("人口记录含未知生命状态")
    return {"total": len(people), "alive": statuses["alive"], "dead": statuses["dead"],
            "unborn": statuses["unborn"], "born": statuses["alive"] + statuses["dead"],
            "discovered": len(known), "direct": len(direct),
            "close": sum(person["status"] == "alive" and person["knowledge"]["closeness"] >= 60
                         for person in direct),
            "close_ever_count": sum(person["knowledge"]["ever_close"] for person in people.values()),
            "direct_alive": sum(person["status"] == "alive" for person in direct),
            "close_alive": sum(person["status"] == "alive" and person["knowledge"]["closeness"] >= 60
                               for person in direct),
            "focus": len(tracked),
            "detailed": sum(person["detailed"] for person in people.values()),
            "detailed_alive": sum(person["detailed"] and person["status"] == "alive"
                                  for person in people.values())}


def visibility_counts(pop: dict) -> dict:
    """Count retained per-person records, never label unseen truth as knowledge.

    A single world occurrence can have a record for several people. Such records
    are separate observations here; history/recent duplicates for one person are
    counted once. A public record about an undiscovered person is not exposed by
    the person directory, so it is not counted as player-visible in this metric.
    """
    total = visible = broadcasts = 0
    for person in pop["people"].values():
        records = {}
        for record in person["history"] + person["recent"]:
            record_id = record["id"]
            if record_id in records and records[record_id] != record:
                raise ValueError("同一人物的记录 ID 对应了不一致的内容")
            records[record_id] = record
        discovered = person["knowledge"]["contact"] != "none"
        for record in records.values():
            total += 1
            broadcasts += record["visibility"] == "public"
            visible += discovered and (record["visibility"] == "public" or record["known"])
    return {"retained_records": total, "public_records": visible,
            "hidden_records": total - visible, "broadcast_records": broadcasts,
            "public_share": visible / total if total else None}


def _known_people(game) -> list[dict]:
    people, offset = [], 0
    while True:
        page = game.people(group="known", offset=offset, limit=24)
        batch = page["people"]
        people.extend(batch)
        if len(people) >= page["total"]:
            break
        if not batch:
            raise RuntimeError("人物分页在到达公开人数前停止")
        offset += len(batch)
    if len({person["id"] for person in people}) != len(people):
        raise RuntimeError("人物分页出现重复身份")
    return people


def _contact(game, visits: Counter, timings: dict) -> dict | None:
    """Choose solely among known people and their public executable actions."""
    people = sorted(_known_people(game), key=lambda person: (visits[person["id"]], person["id"]))
    for person in people:
        detail = game.person(person["id"])
        available = {action["id"]: action for action in detail["actions"] if action["available"]}
        action_id = next((key for key in ("talk", "meet") if key in available), None)
        if action_id is None:
            continue
        action = available[action_id]
        before_stats = deepcopy(game.state["stats"])
        revision, year = game.state["revision"], game.state["year"]
        _timed(lambda: game.social(person["id"], action_id, revision), timings["social"])
        visits[person["id"]] += 1
        return {"kind": "social", "year": year, "npc_id": person["id"],
                "action": action_id, "advertised_costs": deepcopy(action["costs"]),
                "resource_changes": {key: game.state["stats"][key] - before_stats[key]
                                     for key in before_stats}}
    return None


def run_life(seed: int, policy: str, origin: str = "ordinary") -> dict:
    from . import population as population_rules
    from .balance import select_choice
    from .engine import LifeGame

    if policy not in POLICIES:
        raise ValueError(f"未知脚本策略：{policy}")
    started = perf_counter()
    timings = {key: [] for key in ("new", "view", "choose", "social", "population_advance")}
    original_advance = population_rules.advance_population
    annual_population = []

    def measured_advance(*args, **kwargs):
        result = _timed(lambda: original_advance(*args, **kwargs), timings["population_advance"])
        annual_population.append({"year": result["year"], **population_counts(result)})
        return result

    visits, visited_years, trace = Counter(), set(), []
    life_choices = 0
    rng = random.Random(f"population-report:{POLICY_VERSION}:{seed}")
    with patch.object(population_rules, "advance_population", measured_advance):
        game = _timed(lambda: LifeGame.new(name="林禾", origin=origin, seed=seed), timings["new"])
        initial_counts = population_counts(game.state["population"])
        while not game.state["finished"]:
            if life_choices >= MAX_LIFE_CHOICES:
                raise RuntimeError(f"超过 {MAX_LIFE_CHOICES} 次人生选择：seed={seed}, policy={policy}")
            year = game.state["year"]
            if policy == "keep_contact" and year not in visited_years:
                visited_years.add(year)
                for _ in range(MAX_CONTACTS_PER_VISITED_YEAR):
                    contact = _contact(game, visits, timings)
                    if contact is None:
                        break
                    trace.append(contact)
            public = _timed(game.view, timings["view"])
            authored = game.state["current_event"]
            selected = select_choice(public, authored, "cautious", rng)
            if not any(choice["id"] == selected and choice["available"]
                       for choice in public["event"]["choices"]):
                raise RuntimeError("脚本选择了公开列表之外或不可执行的行动")
            trace.append({"kind": "choice", "year": game.state["year"],
                          "event_id": authored["id"], "choice_id": selected})
            _timed(lambda: game.choose(selected, public["revision"]), timings["choose"])
            life_choices += 1
        # Include finished-report rendering in view measurements, explicitly.
        _timed(game.view, timings["view"])
    if not timings["population_advance"]:
        raise RuntimeError("没有测到人口年度推进；检查引擎是否调用了人口模块接口")
    save = game.to_dict()
    social = [row for row in game.state["timeline"] if row["kind"] == "social"]
    if len(social) != sum(visits.values()):
        raise RuntimeError("实际社会互动记录与成功提交的脚本行动数量不一致")
    final_counts = population_counts(game.state["population"])
    count_snapshots = [initial_counts, *annual_population, final_counts]
    return {"seed": seed, "origin": origin, "policy": policy,
            "end_age": game.state["age"], "death_reason": game.state["death_reason"],
            "life_choices": life_choices, "social_interactions": len(social),
            "social_targets": len(visits), "stats": deepcopy(game.state["stats"]),
            "initial_population": initial_counts,
            "population": final_counts, "annual_population": annual_population,
            "peak_population_counts": {key: max(row[key] for row in count_snapshots)
                                       for key in ("discovered", "direct", "close", "close_alive", "focus", "close_ever_count")},
            "population_counters": deepcopy(game.state["population"]["counters"]),
            "visibility": visibility_counts(game.state["population"]),
            "save_bytes": len(_canonical(save)), "final_state_sha256": _digest(save),
            "performance": {**{key: _timing(samples) for key, samples in timings.items()},
                            "life_wall_ms": (perf_counter() - started) * 1000},
            "trace": trace}


def run_batch(seeds: int = 4, progress=None) -> dict:
    from .engine import VERSION, VIEW_VERSION

    if not isinstance(seeds, int) or isinstance(seeds, bool) or seeds < 1:
        raise ValueError("seeds 必须是正整数")
    started = perf_counter()
    hashes = _source_hashes()
    runs = []
    for policy in POLICIES:
        for seed in range(seeds):
            run = run_life(seed, policy)
            runs.append(run)
            if progress is not None:
                progress(f"{len(runs)}/{len(POLICIES) * seeds}: {policy}, seed={seed}, "
                         f"age={run['end_age']}, direct={run['population']['direct']}, "
                         f"ever_close={run['population']['close_ever_count']}")
    reference = next(run for run in runs if run["policy"] == "keep_contact")
    repeat = run_life(reference["seed"], reference["policy"], reference["origin"])
    if _stable_run(reference) != _stable_run(repeat):
        raise RuntimeError("同一种子与脚本策略未产生相同轨迹及人口终态")
    if _source_hashes() != hashes:
        raise RuntimeError("试玩期间规则或内容文件发生变化；请在版本稳定后重新生成报告")
    if progress is not None:
        progress("Repeated keep_contact seed matched (excluding timings).")
    return {"report_version": "0.5", "engine_version": VERSION, "view_version": VIEW_VERSION,
            "python_version": platform.python_version(), "policy_version": POLICY_VERSION,
            "measurement_wall_seconds": perf_counter() - started,
            "policies": POLICIES, "seed_values": list(range(seeds)), "total_runs": len(runs),
            "source_sha256": hashes,
            "determinism_check": {"seed": reference["seed"], "policy": reference["policy"], "identical": True},
            "notes": [
                "两组使用相同种子、普通出身与谨慎人生决策评分；脚本策略不是现实玩家行为预测，也没有预设应有多少好友。",
                "年度默认计划保持 balanced。主动联系最多每个实际停留的年份两次；略过的年份只由年度模拟处理，不补点互动。",
                "维系策略按累计主动联系次数从少到多、ID稳定排序，依次检查公开动作；优先talk，尚未正式相识时可选meet；没有可行行动就继续人生。",
                "人生选择复用 game.balance 的谨慎评分，只读取公开可行性和已定义效果；没有直接写入资源、关系或人口状态。",
                "登记档案包括在世、已故与尚未出生的未来队列，不能等同当前活人；JSON分别列出born/alive/dead/unborn及初始计数。",
                "已发现=contact不为none，直接=contact为direct，两者保留故人的实际相识；当前密切要求仍在世、direct且closeness至少60。",
                "曾密切=真实持久标记knowledge.ever_close；它由实际共同活动跨过阈值或四位旧人物已存在的核心关系产生，不由关注容量推算。",
                "实际关注=tracked名单长度；详细模拟=detailed为true的人数。这两种数量均不表示已经认识、互相亲密或建立友谊。",
                "可见/隐藏比例以每位人物当前保留的history与recent去重记录为分母；玩家可见要求该人物已发现，且记录为public或known。",
                "外围recent会截断，且同一社会事件可涉及多人，因此上述比例不代表全部历史或犯罪发生率；它只描述目前保留的人物记录。",
                "主动互动按主年表kind=social计数；NPC间互动来自人口模块实际完成的interactions计数器，二者不是同一类活动。",
                "save_bytes按UTF-8紧凑JSON序列化计量。完整存档包含模拟真值；公开人物投影隐藏真值不能替代存档防作弊机制。",
                "view计时包含终局人物志生成；choose包含事件效果、所有跨越年份、人口推进与校验。population_advance是实际人口接口调用耗时，二者存在包含关系，不能相加。",
                "性能在同一进程顺序测量，受机器负载与缓存影响，只作观测；重复种子校验排除耗时后比较完整结果。",
                f"measurement_wall_seconds包含{len(runs)}局对照与额外的1局确定性复跑、统计和哈希核对，不含最终JSON/Markdown写盘。",
            ], "runs": runs}


def render_markdown(report: dict) -> str:
    lines = ["# v0.5 人口系统试玩报告", "",
             f"固定种子：{report['seed_values']}；共 {report['total_runs']} 局完整人生。",
             f"测量墙钟耗时：{report['measurement_wall_seconds']:.2f} 秒（含额外一局确定性复跑，不含报告写盘）。",
             f"规则版本 `{report['engine_version']}`；视图版本 `{report['view_version']}`；"
             f"Python `{report['python_version']}`；策略版本 `{report['policy_version']}`。", "",
             "## 脚本策略", ""]
    lines.extend(f"- **{key}**：{description}" for key, description in report["policies"].items())
    lines.extend(["", "## 实际人口与关系", "",
                  "登记档案与重点人物是模拟规模；已发现、直接关系和密切关系分别按下列定义计数，不能相互替代。", "",
                  "| 策略 | 种子 | 终局年龄 | 登记/已出生/存活 | 已发现 | 直接关系 | 当前/曾密切 | 实际关注/详细模拟 | 主动互动 | 存档 KiB |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for run in report["runs"]:
        p = run["population"]
        lines.append(f"| {run['policy']} | {run['seed']} | {run['end_age']} | "
                     f"{p['total']}/{p['born']}/{p['alive']} | {p['discovered']} | {p['direct']} | "
                     f"{p['close']}/{p['close_ever_count']} | {p['focus']}/{p['detailed']} | {run['social_interactions']} | "
                     f"{run['save_bytes'] / 1024:.1f} |")
    lines.extend(["", "## 记录可见性与性能", "",
                  "可见性统计仅用于开发审查，不展示任何具体人物的隐藏事项。耗时为本机观测，未设置通过阈值。", "",
                  "| 策略 | 种子 | NPC 间互动 | 可见/隐藏记录 | 可见占比 | view 均值/最大 ms | choose 均值/最大 ms | 人口年度推进均值 ms |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for run in report["runs"]:
        v, timing = run["visibility"], run["performance"]
        view, choice, advance = timing["view"], timing["choose"], timing["population_advance"]
        share = "无记录" if v["public_share"] is None else f"{v['public_share']:.1%}"
        lines.append(f"| {run['policy']} | {run['seed']} | {run['population_counters']['interactions']} | "
                     f"{v['public_records']}/{v['hidden_records']} | "
                     f"{share} | {view['mean_ms']:.2f}/{view['max_ms']:.2f} | "
                     f"{choice['mean_ms']:.2f}/{choice['max_ms']:.2f} | {advance['mean_ms']:.2f} |")
    lines.extend(["", "## 计数定义与限制", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    lines.extend(["", "## 确定性与来源", "",
                  f"重复完整轨迹：{'一致' if report['determinism_check']['identical'] else '不一致'}。",
                  "耗时不进入确定性比较；逐局终态摘要、行动轨迹与统计保存在同名前缀 JSON。", ""])
    lines.extend(f"- `{path}`：`{digest}`" for path, digest in report["source_sha256"].items())
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=4, help="每种策略使用种子 0 到 N-1")
    parser.add_argument("--output", default="reports/population-v0.5",
                        help="JSON 与 Markdown 输出文件的共同前缀")
    args = parser.parse_args(argv)
    report = run_batch(args.seeds, progress=lambda message: print(message, flush=True))
    prefix = Path(args.output)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = Path(str(prefix) + ".json"), Path(str(prefix) + ".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"{report['total_runs']} runs: {json_path} / {markdown_path}")


if __name__ == "__main__":
    main()
