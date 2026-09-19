"""A bounded fictional world, with a random stream independent of the player."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random


VERSION = "0.4.0"
EVENT_INTERVAL = 2
SCOPES = {"national", "international", "planetary", "frontier"}
METRICS = {
    "prosperity": "经济活力", "cost_pressure": "生活成本压力", "employment": "就业机会",
    "inequality": "资源差距", "public_services": "公共服务", "social_trust": "社会信任",
    "civil_liberties": "个人自由", "institutional_capacity": "公共机构能力",
    "international_tension": "邦际紧张", "trade_openness": "贸易开放", "technology": "技术水平",
    "automation": "自动化程度", "energy_security": "能源保障", "ecology": "生态状况",
    "climate_stress": "气候压力", "public_health": "公共健康", "knowledge_access": "知识可及性",
    "demographic_pressure": "人口结构压力", "food_security": "食物保障", "infrastructure": "基础设施",
}
NEGATIVE_METRICS = {"cost_pressure", "inequality", "international_tension", "climate_stress", "demographic_pressure"}
MODES = {
    "energy": {"mixed": "混合供能", "distributed": "分布式供能", "centralized": "集中供能"},
    "governance": {"negotiated": "协商治理", "centralized": "集中治理", "fragmented": "分散治理"},
    "trade": {"open": "开放贸易", "regional": "区域贸易", "restricted": "受限贸易"},
    "technology": {"open": "开放技术网络", "platform": "平台主导", "restricted": "受限技术网络"},
}
MODE_LABELS = {"energy": "供能结构", "governance": "治理方式", "trade": "贸易结构", "technology": "技术组织"}
INITIAL_MODES = {"energy": "mixed", "governance": "negotiated", "trade": "regional", "technology": "open"}
BASE_METRICS = dict(zip(METRICS, (52, 48, 55, 45, 54, 56, 58, 55, 36, 52, 44, 32, 57, 62, 39, 58, 60, 43, 62, 56)))


class WorldError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise WorldError(message)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _seed(source):
    # Saves pass through JSON.parse/stringify: keep this integer below 2**53.
    return int(hashlib.sha256(f"fictional-world-v04:{source}".encode()).hexdigest()[:13], 16)


def _initial_metrics(source):
    return {key: base + int(hashlib.sha256(f"initial:{source}:{key}".encode()).hexdigest()[:8], 16) % 11 - 5
            for key, base in BASE_METRICS.items()}


def validate_catalog(catalog):
    try:
        return _validate_catalog(catalog)
    except WorldError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        raise WorldError("世界事件库包含缺失或无效的字段。") from exc


def _validate_catalog(catalog):
    _require(isinstance(catalog, dict) and catalog.get("version") == VERSION, "世界事件库版本不兼容。")
    _require(isinstance(catalog.get("domains"), list) and bool(catalog["domains"]), "世界事件库缺少领域。")
    domains = set()
    for domain in catalog["domains"]:
        _require(isinstance(domain, dict) and isinstance(domain.get("id"), str) and bool(domain["id"]) and domain["id"] not in domains, "世界领域编号重复或无效。")
        _require(all(isinstance(domain.get(key), str) and bool(domain[key]) for key in ("label", "description")), "世界领域说明不完整。")
        _require(domain.get("scope") in SCOPES, "世界领域尺度无效。")
        domains.add(domain["id"])
    _require(isinstance(catalog.get("events"), list), "世界事件列表无效。")
    event_ids = set()
    for event in catalog["events"]:
        _require(isinstance(event, dict) and all(isinstance(event.get(key), str) and bool(event[key]) for key in ("id", "title", "text")), "世界事件叙述不完整。")
        _require(event["id"] not in event_ids, "世界事件编号重复。")
        event_ids.add(event["id"])
        _require(event.get("domain") in domains and event.get("scope") in SCOPES, "世界事件领域或尺度无效。")
        _require(_integer(event.get("weight")) and event["weight"] > 0, "世界事件权重须为正整数。")
        _require(_integer(event.get("cooldown")) and event["cooldown"] >= 0 and isinstance(event.get("once"), bool), "世界事件冷却或次数约束无效。")
        _require(_integer(event.get("severity")) and 1 <= event["severity"] <= 3, "世界事件影响等级无效。")
        _require(isinstance(event.get("tags"), list) and all(isinstance(tag, str) for tag in event["tags"]), "世界事件标签无效。")
        _validate_contract(event)
    written_flags = {effect["key"] for event in catalog["events"] for effect in event["effects"] if effect["op"] == "flag"}
    read_flags = {condition["path"].split(".")[2] for event in catalog["events"] for condition in event["requires"]
                  if condition["path"].startswith("world.flags.")}
    _require(read_flags <= written_flags, "世界前提读取了没有来源的事实标记：" + "、".join(sorted(read_flags - written_flags)))
    return catalog


def _validate_contract(contract):
    _require(isinstance(contract, dict), "世界事件规则快照无效。")
    _require(isinstance(contract.get("requires"), list) and isinstance(contract.get("effects"), list), "世界事件前提或后果无效。")
    for condition in contract["requires"]:
        _require(isinstance(condition, dict) and isinstance(condition.get("path"), str), "世界条件路径无效。")
        pieces = condition["path"].split(".")
        _require(len(pieces) == 3 and pieces[0] == "world" and pieces[1] in {"metrics", "flags", "modes"}, "世界条件只能读取世界状态。")
        group, key = pieces[1:]
        _require(bool(key) and (group == "flags" or key in (METRICS if group == "metrics" else MODES)), "世界条件引用未知指标或模式。")
        op, value = condition.get("op"), condition.get("value")
        _require(op in {"eq", "ne", "gte", "lte", "exists"}, "世界条件运算无效。")
        if op == "exists":
            _require(isinstance(value, bool), "存在条件需要布尔值。")
        elif group == "metrics":
            _require(_integer(value) and 0 <= value <= 100, "世界指标条件超出范围。")
        elif group == "modes":
            _require(op in {"eq", "ne"} and value in MODES[key], "世界模式条件无效。")
        else:
            _require(op in {"eq", "ne"} and isinstance(value, bool), "世界事实条件需要布尔值。")
    touched = set()
    for effect in contract["effects"]:
        _require(isinstance(effect, dict) and effect.get("op") in {"metric", "flag", "mode"}, "世界事件包含不支持的动作。")
        op, key = effect["op"], effect.get("key")
        _require(isinstance(key, str) and bool(key) and (op, key) not in touched, "同一世界事件不能重复写入同一个字段。")
        touched.add((op, key))
        if op == "metric":
            _require(key in METRICS and _integer(effect.get("delta")) and -30 <= effect["delta"] <= 30, "单次世界指标变化须为 -30 到 30 的整数。")
        elif op == "mode":
            _require(key in MODES and effect.get("value") in MODES[key], "世界模式变化无效。")
        else:
            _require(isinstance(effect.get("value"), bool), "世界事实必须为布尔值。")


def load_catalog():
    path = Path(__file__).resolve().parents[1] / "content" / "world-events.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        return validate_catalog(catalog)
    except WorldError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorldError("世界事件库无法读取或格式不正确。") from exc


def new_world(seed, start_year, calendar="新历"):
    _require(_integer(seed) and _integer(start_year), "世界种子或开始年份无效。")
    _require(calendar in {"新历", "旧档纪年"}, "世界历法无效。")
    metrics = _initial_metrics(seed)
    return {"version": VERSION, "name": "澄川诸邦", "calendar": calendar, "source_seed": seed, "seed": _seed(seed),
            "random_counter": 0, "start_year": start_year, "year": start_year, "next_event_year": start_year + EVENT_INTERVAL,
            "metrics": deepcopy(metrics), "modes": deepcopy(INITIAL_MODES), "flags": {}, "history": [],
            "initial_metrics": metrics, "initial_modes": deepcopy(INITIAL_MODES)}


def _value(state, path, missing=False):
    _, group, key = path.split(".")
    return state[group].get(key, None if missing or group != "flags" else False)


def _condition(state, condition):
    op, expected = condition["op"], condition["value"]
    actual = _value(state, condition["path"], missing=op == "exists")
    if op == "exists":
        return (actual is not None) == expected
    if op in {"eq", "ne"}:
        same = type(actual) is type(expected) and actual == expected
        return same if op == "eq" else not same
    return _integer(actual) and _integer(expected) and (actual >= expected if op == "gte" else actual <= expected)


def _eligible(state, event, year):
    previous = [row for row in state["history"] if row["event_id"] == event["id"]]
    if previous and (event["once"] or year - previous[-1]["year"] < event["cooldown"]):
        return False
    return all(_condition(state, condition) for condition in event["requires"])


def _apply(state, effects):
    changes = []
    for effect in effects:
        op, key = effect["op"], effect["key"]
        if op == "metric":
            before = state["metrics"][key]
            state["metrics"][key] = _clamp(before + effect["delta"])
            changes.append(f"{METRICS[key]} {state['metrics'][key] - before:+d}")
        elif op == "mode":
            before = state["modes"][key]
            state["modes"][key] = effect["value"]
            changes.append(f"{MODE_LABELS[key]}：{MODES[key][before]} → {MODES[key][effect['value']]}")
        else:
            state["flags"][key] = effect["value"]
    return changes


def _causes(state, event):
    result = []
    groups = {"metric": "metrics", "flag": "flags", "mode": "modes"}
    for condition in event["requires"]:
        for row in reversed(state["history"]):
            if any(f"world.{groups[effect['op']]}.{effect['key']}" == condition["path"] for effect in row["contract"]["effects"]):
                if row["id"] not in result:
                    result.append(row["id"])
                break
        if len(result) >= 4:
            break
    return result


def advance_world(state, target_year, catalog=None, validate_input=True):
    """Return a new state containing only facts that have occurred by target_year."""
    catalog = load_catalog() if catalog is None else catalog
    if validate_input:
        validate_catalog(catalog)
        validate_world(state, catalog)
    _require(_integer(target_year) and target_year >= state["year"], "世界时间不能倒退。")
    working = deepcopy({key: value for key, value in state.items() if key != "history"})
    working["history"] = deepcopy(state["history"]) if validate_input else list(state["history"])
    domains = {domain["id"]: domain for domain in catalog["domains"]}
    while working["next_event_year"] <= target_year:
        year = working["next_event_year"]
        working["year"] = year
        candidates = sorted((event for event in catalog["events"] if _eligible(working, event, year)), key=lambda item: item["id"])
        if candidates:
            draw = random.Random(f"world:{working['seed']}:{working['random_counter']}").randrange(sum(event["weight"] for event in candidates))
            working["random_counter"] += 1
            for event in candidates:
                draw -= event["weight"]
                if draw < 0:
                    break
            _require(_eligible(working, event, year), "世界事件前提已经失效。")
            causes = _causes(working, event)
            changes = _apply(working, event["effects"])
            working["history"].append({"id": f"world-{len(working['history']) + 1}", "event_id": event["id"], "year": year,
                "domain": event["domain"], "domain_label": domains[event["domain"]]["label"], "scope": event["scope"],
                "title": event["title"], "text": event["text"], "changes": changes, "causes": causes,
                "severity": event["severity"], "tags": deepcopy(event["tags"]),
                "contract": {key: deepcopy(event[key]) for key in ("requires", "effects", "once", "cooldown")}})
        working["next_event_year"] += EVENT_INTERVAL
    working["year"] = target_year
    validate_world(working, catalog, expected_year=target_year, full_history=False)
    return working


def validate_world(state, catalog=None, expected_year=None, full_history=True):
    catalog = load_catalog() if catalog is None else catalog
    try:
        _require(isinstance(state, dict) and state["version"] == VERSION, "世界存档版本不兼容。")
        _require(_integer(state["source_seed"]) and state["seed"] == _seed(state["source_seed"]), "世界随机种子不一致。")
        _require(state["calendar"] in {"新历", "旧档纪年"} and state["name"] == "澄川诸邦", "世界身份或历法无效。")
        _require(_integer(state["start_year"]) and _integer(state["year"]) and state["year"] >= state["start_year"], "世界年份无效。")
        _require(expected_year is None or state["year"] == expected_year, "世界与人物所在年份不一致。")
        expected_next = state["start_year"] + EVENT_INTERVAL * ((state["year"] - state["start_year"]) // EVENT_INTERVAL + 1)
        _require(_integer(state["next_event_year"]) and state["next_event_year"] == expected_next, "世界事件时钟不一致。")
        _require(set(state["metrics"]) == set(METRICS) and all(_integer(value) and 0 <= value <= 100 for value in state["metrics"].values()), "世界指标超出范围。")
        _require(set(state["modes"]) == set(MODES) and all(state["modes"][key] in MODES[key] for key in MODES), "世界模式不互斥或值无效。")
        _require(isinstance(state["flags"], dict) and all(isinstance(key, str) and isinstance(value, bool) for key, value in state["flags"].items()), "世界事实无效。")
        _require(isinstance(state["history"], list) and _integer(state["random_counter"]) and state["random_counter"] == len(state["history"]), "世界随机进度与已发生记录不一致。")
        _require(state["initial_metrics"] == _initial_metrics(state["source_seed"]) and state["initial_modes"] == INITIAL_MODES, "世界初始基线不一致。")
        if not full_history:
            return
        domains = {domain["id"] for domain in catalog["domains"]}
        events = {event["id"] for event in catalog["events"]}
        replayed = {"metrics": deepcopy(state["initial_metrics"]), "modes": deepcopy(state["initial_modes"]), "flags": {}, "history": []}
        last_year = state["start_year"]
        ids = set()
        for index, row in enumerate(state["history"], 1):
            _require(isinstance(row, dict) and all(isinstance(row.get(key), str) and bool(row[key])
                     for key in ("id", "event_id", "domain_label", "title", "text")), "世界历史缺少叙述或身份。")
            _require(row["id"] == f"world-{index}" and row["event_id"] in events, "世界历史编号无效。")
            _require(_integer(row["year"]) and last_year + EVENT_INTERVAL <= row["year"] <= state["year"]
                     and (row["year"] - state["start_year"]) % EVENT_INTERVAL == 0, "世界历史包含未来或过密事件。")
            _require(row["domain"] in domains and row["scope"] in SCOPES, "世界历史领域或尺度无效。")
            _require(isinstance(row["causes"], list) and all(cause in ids for cause in row["causes"]), "世界历史引用了尚未发生的原因。")
            _require(_integer(row.get("severity")) and 1 <= row["severity"] <= 3
                     and isinstance(row.get("tags"), list) and all(isinstance(tag, str) for tag in row["tags"]), "世界历史标签或影响等级无效。")
            contract = row["contract"]
            _validate_contract(contract)
            _require(isinstance(contract["once"], bool) and _integer(contract["cooldown"]) and contract["cooldown"] >= 0, "世界历史冷却条件无效。")
            event = {"id": row["event_id"], **contract}
            _require(_eligible(replayed, event, row["year"]), "世界历史违反了当时前提或冷却。")
            _require(row["causes"] == _causes(replayed, event), "世界历史的前序引用与当时条件不一致。")
            _require(row["changes"] == _apply(replayed, contract["effects"]), "世界历史的实际变化与记录不一致。")
            replayed["history"].append(row)
            ids.add(row["id"])
            last_year = row["year"]
        for key in ("metrics", "modes", "flags"):
            _require(state[key] == replayed[key], "世界当前状态无法由其历史得到。")
    except WorldError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise WorldError("世界存档缺少字段或存在不一致。") from exc


def modifiers(state):
    m = state["metrics"]
    income = 100 + ((m["prosperity"] - 50) * 12 + (m["employment"] - 50) * 10
                    + (m["trade_openness"] - 50) * 4 + (m["technology"] - 50) * 3
                    - (m["international_tension"] - 50) * 5) // 100
    expenses = 100 + ((m["cost_pressure"] - 50) * 16 + (m["climate_stress"] - 50) * 6
                      + (50 - m["energy_security"]) * 6 + (50 - m["food_security"]) * 8
                      + (50 - m["public_health"]) * 4 + (50 - m["infrastructure"]) * 4) // 100
    return {"income_percent": _clamp(income, 80, 120), "expense_percent": _clamp(expenses, 82, 125)}


def event_context(state, domain, limit=3, requires=None):
    paths = {condition["path"] for condition in requires or [] if condition["path"].startswith("world.")}
    groups = {"metric": "metrics", "flag": "flags", "mode": "modes"}
    rows = [row for row in state["history"] if row["domain"] == domain or any(
            f"world.{groups[effect['op']]}.{effect['key']}" in paths for effect in row["contract"]["effects"])]
    rows = rows[-limit:] if limit > 0 else []
    return [{key: row[key] for key in ("id", "title", "year")} for row in reversed(rows)]


def world_view(state, catalog=None):
    catalog = load_catalog() if catalog is None else catalog
    keys = ("id", "event_id", "year", "domain", "domain_label", "scope", "title", "text", "changes", "causes", "severity", "tags")
    return {"name": state["name"], "calendar": state["calendar"], "year": state["year"], "start_year": state["start_year"],
            "profile": "、".join(MODES[key][state["modes"][key]] for key in MODES) + "；这些是当前状况，并非预定的历史道路。",
            "metrics": [{"id": key, "label": label, "value": state["metrics"][key],
                         "direction": "negative" if key in NEGATIVE_METRICS else "positive"} for key, label in METRICS.items()],
            "modes": [{"id": key, "label": MODE_LABELS[key], "value": state["modes"][key],
                       "value_label": MODES[key][state["modes"][key]]} for key in MODES],
            "domains": [{"id": domain["id"], "label": domain["label"]} for domain in catalog["domains"]],
            "history": [{key: deepcopy(row[key]) for key in keys} for row in state["history"]],
            "modifiers": modifiers(state), "event_interval": EVENT_INTERVAL,
            "note": "架空世界独立演化；尚未发生的未来不会提前写入记录。" if state["calendar"] == "新历" else "保留旧档原有年份；世界历史只从这次迁移所在年开始积累。"}
