"""Static catalog linting. Passing this check does not prove event reachability."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from .engine import ROOT, STAT_NAMES, RuleError, _event_contract


NPC_IDS = {"mother", "father", "friend", "partner"}
# Engine-owned producers only. Content-owned flags are discovered from effects.
INITIAL_FLAGS = {"partner_met": False, "partnered": False, "has_child": False,
                 "work_pace": "steady", "work_push_years": 0, "work_push_seen": False}
ENGINE_FLAGS = {"widowed": {bool}, "work_pace": {str}, "work_push_years": {int},
                "work_push_seen": {bool},
                **{f"loan_{pid}_{suffix}": {bool} for pid in NPC_IDS for suffix in ("open", "due")}}
NPC_FIELDS = {"id": {str}, "name": {str}, "role": {str}, "birth_year": {int}, "age": {int},
              "alive": {bool}, "met": {bool}, "closeness": {int}, "cash": {int},
              "death_year": {int, type(None)}, "death_age": {int, type(None)}, "description": {str}}
STATUS_FIELDS = {"job": {str}, "job_label": {str}, "income": {int}, "expenses": {int}}
TEMPLATE = re.compile(r"\{([A-Za-z0-9_.]+)\}")


def check_catalog(catalog: dict, dimension_ids: set[str] | None = None, world_catalog: dict | None = None) -> dict:
    diagnostics = []

    def issue(level, code, location, message):
        diagnostics.append({"level": level, "code": code, "location": location, "message": message})

    if dimension_ids is None:
        data = json.loads((ROOT / "content/personality-dimensions.json").read_text(encoding="utf-8"))
        dimension_ids = {item["id"] for item in data["dimensions"]}
    if not isinstance(catalog, dict) or not isinstance(catalog.get("events"), list):
        issue("error", "catalog_shape", "catalog", "事件库必须包含events列表。")
        return _result(diagnostics, 0)
    valid = []
    from .world import METRICS, MODES
    if world_catalog is None:
        world_path = ROOT / "content/world-events.json"
        world_catalog = json.loads(world_path.read_text(encoding="utf-8")) if world_path.exists() else {"domains": [], "events": []}
    world_flags = {effect["key"] for event in world_catalog.get("events", [])
                   for effect in event.get("effects", []) if effect.get("op") == "flag"}
    world_domains = {domain["id"] for domain in world_catalog.get("domains", [])}
    seen = set()
    flag_types = defaultdict(set)
    writers = defaultdict(list)
    for key, value in INITIAL_FLAGS.items():
        flag_types[key].add(type(value))
        writers[key].append({"source": "engine.initial", "age_min": 0, "value": value})
    for key, types in ENGINE_FLAGS.items():
        flag_types[key].update(types)
        writers[key].append({"source": "engine.runtime", "age_min": 0})
    for index, event in enumerate(catalog["events"]):
        location = event.get("id", f"events[{index}]") if isinstance(event, dict) else f"events[{index}]"
        if isinstance(location, str):
            if location in seen:
                issue("error", "duplicate_event_id", location, "事件编号重复。")
            seen.add(location)
        try:
            _event_contract(event)
        except (RuleError, TypeError, KeyError, AttributeError) as error:
            issue("error", "event_contract", str(location), str(error))
            continue
        valid.append(event)
        for choice in event["choices"]:
            for effect in choice.get("effects", []):
                if effect["op"] == "flag":
                    key = effect["key"]
                    flag_types[key].add(type(effect["value"]))
                    writers[key].append({"source": event["id"], "age_min": event["age_min"],
                                         "value": effect["value"]})

    def path_types(path):
        bits = path.split(".")
        if len(bits) == 1:
            return {"age": {int}, "year": {int}, "origin": {str}}.get(path)
        if len(bits) == 2 and bits[0] == "stats":
            return {int} if bits[1] in STAT_NAMES else None
        if len(bits) == 2 and bits[0] == "status":
            return STATUS_FIELDS.get(bits[1])
        if len(bits) == 2 and bits[0] == "flags":
            return flag_types.get(bits[1], set())
        if len(bits) == 3 and bits[0] == "npc" and bits[1] in NPC_IDS:
            return NPC_FIELDS.get(bits[2])
        if len(bits) == 3 and bits[:2] == ["world", "metrics"]:
            return {int} if bits[2] in METRICS else None
        if len(bits) == 3 and bits[:2] == ["world", "modes"]:
            return {str} if bits[2] in MODES else None
        if len(bits) == 3 and bits[:2] == ["world", "flags"]:
            return {bool} if bits[2] in world_flags else None
        return None

    def condition_check(condition, event, location, active_npcs):
        path, op, value = condition["path"], condition["op"], condition.get("value")
        types = path_types(path)
        if types is None:
            issue("error", "unknown_path", location, f"条件引用未知字段：{path}")
            return
        if op == "exists":
            if type(value) is not bool:
                issue("error", "condition_type", location, f"{path}的exists条件需要布尔值。")
        elif op in {"gte", "lte"}:
            if type(value) is not int or (types and int not in types):
                issue("error", "condition_type", location, f"{path}的数值比较需要整数型字段和整数值。")
        elif types and type(value) not in types:
            issue("error", "condition_type", location, f"{path}的比较值类型与已知字段/写入类型不符。")
        parts = path.split(".")
        if len(parts) == 3 and parts[:2] == ["world", "modes"] and op in {"eq", "ne"}:
            if value not in MODES.get(parts[2], {}):
                issue("error", "unknown_world_mode", location, f"{path}引用未知发展路线：{value}")
        if len(parts) == 3 and parts[:2] == ["world", "metrics"] and type(value) is int and not 0 <= value <= 100:
            issue("error", "world_threshold_range", location, f"{path}条件超出0到100的指标范围。")
        if parts[0] == "flags":
            key = parts[1]
            if key not in writers:
                # Missing flags evaluate to False in ordinary engine conditions.
                requires_presence = (op == "eq" and value is not False) or (op == "ne" and value is False) or op in {"gte", "lte"} or (op == "exists" and value is True)
                issue("error" if requires_presence else "warning", "flag_without_source", location,
                      f"{path}没有初始、引擎或内容写入来源；仅检查到读操作，缺省值条件可能是有意的。")
            elif op == "eq":
                matches = [writer for writer in writers[key] if "value" not in writer or
                           (type(writer["value"]) is type(value) and writer["value"] == value)]
                if matches and all(writer["age_min"] > event["age_max"] for writer in matches):
                    issue("warning", "producer_after_consumer", location,
                          f"{path}满足该值的已知内容写入者都晚于本事件年龄上限；请人工检查事件链。")
        if len(parts) == 3 and parts[0] == "npc" and parts[2] == "alive":
            requires_dead = (op == "eq" and value is False) or (op == "ne" and value is True)
            if requires_dead and parts[1] in active_npcs:
                issue("error", "dead_active_actor", location,
                      f"{parts[1]}同时被要求已故并作为在世参与者或动作对象。")

    def template_check(text, location):
        if not isinstance(text, str):
            return
        for path in TEMPLATE.findall(text):
            if path in {"name", "age", "year"}:
                continue
            types = path_types(path)
            if types is None or not types:
                issue("error", "unknown_template_path", location, f"叙事模板引用未知字段：{{{path}}}")

    for event in valid:
        if "world_domain" in event:
            if event["world_domain"] not in world_domains:
                issue("error", "unknown_world_domain", event["id"], "时代响应引用未知领域。")
            if not any(condition["path"].startswith("world.") for condition in event.get("requires", [])):
                issue("error", "missing_world_gate", event["id"], "时代响应需要真实的世界前提。")
        actors = set(event.get("actors", []))
        for condition in event.get("requires", []):
            condition_check(condition, event, event["id"], actors)
        template_check(event["text"], event["id"])
        for choice in event["choices"]:
            location = event["id"] + "/" + choice["id"]
            effect_npcs = {effect["npc"] for effect in choice.get("effects", []) if "npc" in effect}
            for condition in choice.get("requires", []):
                condition_check(condition, event, location, actors | effect_npcs)
            # An event may be historical while a particular choice still tries to
            # mutate its deceased subject; catch that cross-level contradiction.
            for condition in event.get("requires", []):
                if effect_npcs - actors and condition["path"].startswith("npc."):
                    condition_check(condition, event, location, effect_npcs - actors)
            for field in ("label", "description", "outcome"):
                template_check(choice.get(field), location + "/" + field)
            for observation in choice.get("observations", []):
                if observation["dimension"] not in dimension_ids:
                    issue("error", "unknown_observation_dimension", location,
                          f"观察维度未在personality-dimensions中定义：{observation['dimension']}")
    return _result(diagnostics, len(catalog["events"]))


def _result(diagnostics, count):
    return {"event_count": count, "errors": [item for item in diagnostics if item["level"] == "error"],
            "warnings": [item for item in diagnostics if item["level"] == "warning"],
            "note": "静态检查只发现部分结构、类型与依赖问题；通过不证明可达、剧情一致或玩法平衡。"}


def check_personality_coverage(path=None, event_ids=None, event_dimensions=None):
    """Validate the editor-owned 8-dimension coverage matrix."""
    path = path or (ROOT / "content/personality-coverage.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"care", "conflict_style", "exploration", "fairness", "help_seeking",
                "persistence", "risk_taking", "social_initiative"}
    errors = []
    if data.get("version") != "0.1.0":
        errors.append({"code": "coverage_version", "message": "覆盖矩阵版本无效。"})
    if set(data.get("dimensions", [])) != required:
        errors.append({"code": "coverage_dimensions", "message": "覆盖矩阵必须恰好包含八个观察维度。"})
    contexts = data.get("contexts", [])
    if len(contexts) != 4 or len({c.get("id") for c in contexts}) != 4:
        errors.append({"code": "coverage_contexts", "message": "覆盖矩阵必须包含四个互异子情境。"})
    fields = {"age", "pressure", "relationship", "scale", "information", "horizon", "events"}
    for context in contexts:
        if not fields <= set(context) or not isinstance(context.get("events"), list) or not context["events"]:
            errors.append({"code": "coverage_context_shape", "message": f"子情境字段不完整：{context.get('id')}。"})
    matrix = data.get("matrix", {})
    if set(matrix) != required or any(not isinstance(v, list) or len(v) < 4 for v in matrix.values()):
        errors.append({"code": "coverage_matrix", "message": "每个观察维度必须至少引用四个事件。"})
    if event_ids is not None:
        refs = {eid for c in contexts for eid in c.get("events", [])}
        refs.update(eid for values in matrix.values() for eid in values)
        unknown = sorted(refs - set(event_ids))
        if unknown:
            errors.append({"code": "coverage_unknown_event", "message": "覆盖矩阵引用未知事件：" + ", ".join(unknown)})
    if event_dimensions is not None:
        for dimension, ids in matrix.items():
            for event_id in ids:
                observed = event_dimensions.get(event_id, set())
                if dimension not in observed:
                    errors.append({"code": "coverage_dimension_mismatch",
                                   "message": f"覆盖矩阵把 {event_id} 列入 {dimension}，但该事件没有预标注该维度。"})
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, help="仅检查指定的个人事件文件；默认检查全部运行内容")
    parser.add_argument("--json", action="store_true", help="输出结构化诊断")
    args = parser.parse_args(argv)
    try:
        if args.catalog:
            catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
            result = check_catalog(catalog)
        else:
            from .world import load_catalog, validate_catalog
            from .engine import _catalog
            world = load_catalog()
            validate_catalog(world)
            result = check_catalog(_catalog(), world_catalog=world)
            result["world_event_count"] = len(world["events"])
            catalog = _catalog()
            event_dimensions = {
                event["id"]: {item.get("dimension", item.get("dimension_id"))
                               for choice in event.get("choices", [])
                               for item in choice.get("observations", [])}
                for event in catalog["events"]
            }
            coverage_errors = check_personality_coverage(
                event_ids=set(event_dimensions), event_dimensions=event_dimensions)
            result["coverage_errors"] = coverage_errors
            result["errors"].extend(coverage_errors)
    except (OSError, ValueError) as error:
        result = _result([{"level": "error", "code": "read_error", "location": str(args.catalog),
                           "message": str(error)}], 0)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['event_count']} events; {len(result['errors'])} errors; {len(result['warnings'])} warnings")
        if "world_event_count" in result:
            print(f"World catalog: {result['world_event_count']} events")
        for issue in result["errors"] + result["warnings"]:
            print(f"[{issue['level']}] {issue['code']} {issue['location']}: {issue['message']}")
        print(result["note"])
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
