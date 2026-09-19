"""Rule-driven life game. Narrative assets never execute arbitrary code."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import random
import re

from . import world as world_rules
from . import population as population_rules


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.3.0"
VIEW_VERSION = "0.5.0"
RECOVERY_COOLDOWN_YEARS = 3
PACE_LABELS = {"steady": "稳健节奏", "push": "加紧节奏", "rest": "放慢节奏"}
AGES = [6, 6, 9, 12, 12, 15, 18, 18, 20, 23, 23, 26, 30, 30, 34,
        38, 38, 42, 46, 46, 50, 55, 55, 60, 65, 65, 70, 75, 80, 82]
STAT_NAMES = {"cash": "现金", "energy": "精力", "health": "健康", "stress": "压力",
              "education": "学识", "skill": "技能"}
JOBS = {
    "none": ("零工与待业", 9200, 2), "apprentice": ("学徒", 16000, 3),
    "worker": ("技术工人", 23000, 4), "clerk": ("职员", 25000, 4),
    "teacher": ("教师", 26500, 4), "freelancer": ("自由职业", 21000, 5),
    "retired": ("退休", 15600, 0),
}
ORIGINS = {"ordinary": (80, 18000), "struggling": (30, 8000), "comfortable": (180, 30000)}
OPCODES = {"stat", "flag", "relation", "npc_cash", "job", "loan", "loan_repay"}


class RuleError(ValueError):
    """An invalid command or save, expressed as a player-readable message."""


def require(condition, message):
    if not condition:
        raise RuleError(message)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def stage(age):
    if age < 12:
        return "童年"
    if age < 18:
        return "少年"
    if age < 35:
        return "青年"
    if age < 60:
        return "中年"
    return "晚年"


def _event_contract(event):
    require(isinstance(event, dict), "当前事件格式不正确。")
    for key in ("id", "title", "category", "scene", "text"):
        require(isinstance(event.get(key), str) and bool(event[key]), "事件缺少必要的叙事信息。")
    require(integer(event.get("age_min")) and integer(event.get("age_max"))
            and 0 <= event["age_min"] <= event["age_max"] <= 120, "事件年龄范围不正确。")
    require(isinstance(event.get("actors", []), list) and all(x in {"mother", "father", "friend", "partner"}
            for x in event.get("actors", [])), "事件引用了未知人物。")
    require(isinstance(event.get("choices"), list) and len(event["choices"]) >= 2, "事件至少需要两个选项。")
    if "episode_group" in event:
        require(isinstance(event["episode_group"], str) and bool(event["episode_group"]),
                "事件的 episode_group 必须是非空文字。")
    if "assessment_context" in event:
        require(isinstance(event["assessment_context"], dict), "事件评价情境必须是对象。")
        for key in ("life_stage", "pressure_band", "relationship_scope", "scale", "information_level", "time_horizon"):
            if key in event["assessment_context"]:
                require(isinstance(event["assessment_context"][key], str),
                        f"事件评价情境的 {key} 必须是文字。")
    conditions = list(event.get("requires", []))
    seen = set()
    for choice in event["choices"]:
        require(isinstance(choice, dict) and isinstance(choice.get("id"), str) and choice["id"] not in seen,
                "同一事件的选项编号必须存在且不能重复。")
        seen.add(choice["id"])
        require(isinstance(choice.get("label"), str) and bool(choice["label"]), "选项缺少名称。")
        require(isinstance(choice.get("effects", []), list), "选项后果格式不正确。")
        conditions.extend(choice.get("requires", []))
        for effect in choice.get("effects", []):
            require(isinstance(effect, dict) and effect.get("op") in OPCODES, "内容包含尚未实现的动作。")
            op = effect["op"]
            if op == "stat":
                require(effect.get("key") in STAT_NAMES and integer(effect.get("delta")), "属性变化格式不正确。")
            if op in {"relation", "npc_cash", "loan", "loan_repay"}:
                require(effect.get("npc") in {"mother", "father", "friend", "partner"}, "选项引用了未知人物。")
            if op in {"relation", "npc_cash"}:
                require(integer(effect.get("delta")), "人物变化需要整数数值。")
            if op == "job":
                require(effect.get("value") in JOBS, "选项引用了未知职业。")
            if op == "flag":
                require(isinstance(effect.get("key"), str) and isinstance(effect.get("value"), (bool, int, str)), "经历标记格式不正确。")
                require(not effect["key"].startswith("world."), "个人选择不能直接改写世界状态。")
            if op == "loan":
                require(integer(effect.get("amount")) and effect["amount"] > 0 and
                        integer(effect.get("due_years")) and effect["due_years"] > 0, "借款金额和期限须为正整数。")
        require(isinstance(choice.get("observations", []), list), "行为证据格式不正确。")
        for observation in choice.get("observations", []):
            require(isinstance(observation, dict) and isinstance(observation.get("dimension"), str)
                    and isinstance(observation.get("behavior"), str), "行为证据缺少维度或行为。")
            if "facet" in observation:
                require(isinstance(observation["facet"], str) and bool(observation["facet"]),
                        "行为观察的 facet 必须是非空文字。")
    for condition in conditions:
        require(isinstance(condition, dict) and isinstance(condition.get("path"), str)
                and condition.get("op") in {"eq", "gte", "lte", "ne", "exists"}, "事件条件格式不正确。")


def _catalog():
    events = []
    try:
        for filename in ("life-events.json", "society-events.json"):
            data = json.loads((ROOT / "content" / filename).read_text(encoding="utf-8"))
            require(isinstance(data, dict) and isinstance(data.get("events"), list), "人生事件库格式不正确。")
            require(data.get("version") == "0.4.0", "当前规则只支持 0.4.0 事件库。")
            for event in data["events"]:
                if filename == "society-events.json":
                    require(isinstance(event.get("world_domain"), str), "社会事件需要注明相关世界领域。")
                events.append(event)
        world_catalog = world_rules.load_catalog()
    except world_rules.WorldError as exc:
        raise RuleError(str(exc)) from exc
    except (OSError, ValueError) as exc:
        if isinstance(exc, RuleError):
            raise
        raise RuleError("人生事件库暂时无法读取。") from exc
    seen = set()
    domains = {domain["id"] for domain in world_catalog["domains"]}
    for event in events:
        _event_contract(event)
        require(event["id"] not in seen, "事件编号不能重复。")
        require("world_domain" not in event or event["world_domain"] in domains, "个人事件关联了不存在的世界领域。")
        seen.add(event["id"])
    return {"version": "0.4.0", "events": events, "world_catalog": world_catalog}


class LifeGame:
    def __init__(self, state, catalog=None):
        self.state = deepcopy(state)
        # Assets are read-only; each selected event is copied before use.
        self.catalog = catalog if catalog is not None else _catalog()

    def _fork(self):
        clone = object.__new__(LifeGame)
        clone.state = deepcopy({key: value for key, value in self.state.items() if key not in {"timeline", "world", "population"}})
        # Population operations are copy-on-write; previews never copy 2,000 people.
        clone.state["population"] = self.state["population"]
        # Committed history entries are immutable. Only the list receives new entries.
        clone.state["timeline"] = list(self.state["timeline"])
        clone.state["world"] = deepcopy({key: value for key, value in self.state["world"].items() if key != "history"})
        clone.state["world"]["history"] = list(self.state["world"]["history"])
        clone.catalog = self.catalog
        return clone

    @classmethod
    def new(cls, name="林禾", origin="ordinary", seed=1988):
        require(isinstance(name, str) and 1 <= len(name.strip()) <= 20, "姓名请使用 1 至 20 个字符。")
        require(origin in ORIGINS, "请选择已有的家庭起点。")
        require(integer(seed), "人生种子必须是整数。")
        data = _catalog()
        born_year = 1
        year = born_year + 6
        npcs = {}
        definitions = [("mother", "许岚", "母亲", born_year - 24, 76), ("father", "林川", "父亲", born_year - 27, 70),
                       ("friend", "周远", "朋友", born_year, 48), ("partner", "陈安", "相识的人", born_year + 1, 15)]
        parent_cash = {"struggling": 9000, "ordinary": 20000, "comfortable": 45000}[origin]
        for pid, npc_name, role, birth, closeness in definitions:
            npcs[pid] = {"id": pid, "name": npc_name, "role": role, "birth_year": birth,
                         "age": year - birth, "alive": True, "met": pid != "partner",
                         "closeness": closeness, "cash": parent_cash if pid in {"mother", "father"} else 50,
                         "death_year": None, "death_age": None, "description": ""}
        state = {"version": VERSION, "content_version": data.get("version", "unknown"),
                 "name": name.strip(), "origin": origin, "born_year": born_year, "age": 6, "year": year,
                 "revision": 0, "finished": False, "death_reason": None,
                 "stats": {"cash": ORIGINS[origin][0], "energy": 80, "health": 90,
                           "stress": 10, "education": 5, "skill": 3},
                 "status": {"job": "none", "job_label": "在校", "income": 0, "expenses": 0},
                 "npcs": npcs, "flags": {"partner_met": False, "partnered": False, "has_child": False,
                                           "work_pace": "steady", "work_push_years": 0, "work_push_seen": False},
                 "loans": [], "timeline": [], "last_outcome": None, "current_event": None,
                 "seed": seed, "random_counter": 0, "slot_index": 0, "used_events": [],
                 "aid_remaining": 12000, "family_grant_given": False, "sequence": 0,
                 "child_birth_year": None, "migration_note": None,
                 "survival": {"cooldown_until": born_year, "adjustment_count": 0, "consecutive_push_years": 0},
                 "world": world_rules.advance_world(world_rules.new_world(seed, born_year), year, data["world_catalog"])}
        state["population"] = population_rules.new_population(seed, year, npcs)
        game = cls(state, data)
        game._record("birth", "来到青溪镇", f"新历 {born_year} 年，{name.strip()}出生在澄川诸邦的青溪镇。", age=0)
        game._update_budget()
        game._select_event()
        game._validate()
        return game

    @classmethod
    def from_dict(cls, save):
        try:
            require(isinstance(save, dict) and save.get("schema_version") in {VERSION, "1.2.0", "1.1.0", "1.0.0"}, "存档版本不兼容。")
            require(isinstance(save.get("state"), dict), "存档缺少人生状态。")
            state = deepcopy(save["state"])
            data = _catalog()
            if save["schema_version"] in {"1.0.0", "1.1.0"}:
                old_version = save["schema_version"]
                old_content = {"1.0.0": "0.2.0", "1.1.0": "0.3.0"}[old_version]
                require(state.get("version") == old_version and state.get("content_version") == old_content,
                        "旧存档的格式版本与事件库版本不匹配，不能直接迁移。")
                state["version"], state["content_version"] = VERSION, data["version"]
                if old_version == "1.0.0":
                    state["flags"].update(work_pace="steady", work_push_years=0, work_push_seen=False)
                    state["survival"] = {"cooldown_until": state["year"], "adjustment_count": 0, "consecutive_push_years": 0}
                state["world"] = world_rules.new_world(state["seed"], state["year"], "旧档纪年")
                state["migration_note"] = "已迁移至 0.4：过去的经历、原有年份、当前选择和人物随机进度保持不变；架空世界从当前年开始记录，不补造此前的世界历史。" + (" 工作节奏初始为稳健。" if old_version == "1.0.0" else "")
            if save["schema_version"] != VERSION:
                if save["schema_version"] == "1.2.0":
                    require(state.get("version") == "1.2.0" and state.get("content_version") == "0.4.0", "旧存档版本不一致。")
                state["version"] = VERSION
                state["population"] = population_rules.new_population(state["seed"], state["year"], state["npcs"])
                state["migration_note"] = "已接续至 0.5：旧经历、当前选项与时代纪事保留；新增人群从当前年开始生活，不补造过去的交往。"
            game = cls(state, data)
            game._validate()
            population_rules.validate_population(game.state["population"], anchors=game.state["npcs"], expected_year=game.state["year"], full=True)
            if save["schema_version"] in {"1.0.0", "1.1.0"}:
                game._update_budget()
            return game
        except RuleError:
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RuleError("存档内容不完整或存在不一致，无法继续。") from exc

    def to_dict(self):
        return {"schema_version": VERSION, "state": deepcopy(self.state)}

    def _draw(self):
        s = self.state
        rng = random.Random(f"{s['seed']}:{s['random_counter']}")
        s["random_counter"] += 1
        return rng.random()

    def _record(self, kind, title, text, age=None, **extra):
        s = self.state
        s["sequence"] += 1
        age = s["age"] if age is None else age
        row = {"id": f"life-{s['sequence']}", "age": age, "year": s["born_year"] + age,
               "title": title, "text": text, "kind": kind, **deepcopy(extra)}
        if age == s["age"]:
            row["stats_after"] = deepcopy(s["stats"])
        s["timeline"].append(row)
        return row

    def _path(self, path, missing=False):
        require(isinstance(path, str), "事件条件缺少有效字段。")
        bits = path.split(".")
        current = {"stats": self.state["stats"], "flags": self.state["flags"],
                   "npc": self.state["npcs"], "status": self.state["status"],
                   "age": self.state["age"], "year": self.state["year"], "origin": self.state["origin"], "world": self.state["world"]}
        for bit in bits:
            if not isinstance(current, dict) or bit not in current:
                is_flag = bits[0] == "flags" or len(bits) > 1 and bits[:2] == ["world", "flags"]
                return None if missing else (False if is_flag else None)
            current = current[bit]
        return current

    def _condition_reason(self, cond):
        path, op, value = cond.get("path"), cond.get("op"), cond.get("value")
        require(op in {"eq", "gte", "lte", "ne", "exists"}, "事件包含不支持的条件。")
        actual = self._path(path, missing=op == "exists")
        if op == "exists":
            ok = (actual is not None) == bool(value)
        elif op in {"eq", "ne"}:
            equal = type(actual) is type(value) and actual == value
            ok = equal if op == "eq" else not equal
        else:
            ok = integer(actual) and integer(value) and (actual >= value if op == "gte" else actual <= value)
        if ok:
            return None
        field = path.split(".")[-1]
        if path.startswith("stats."):
            label = STAT_NAMES.get(field, field)
            return f"{label}需要{'至少' if op == 'gte' else '不高于' if op == 'lte' else '达到'} {value}，目前为 {actual}。"
        if path.startswith("npc."):
            npc = self.state["npcs"].get(path.split(".")[1], {})
            name = npc.get("name", "相关人物")
            if field == "alive":
                return f"{name}的当前生死状态不符合这件事的前提。"
            if field == "cash":
                return f"{name}目前没有足够的钱。"
            if field == "met":
                return f"你们还没有相识。"
            return f"与{name}的关系还不满足这个选项的条件。"
        if path.startswith("status."):
            return "目前的工作状态不符合这个选项。"
        if path.startswith("world."):
            return "当前的世界状况尚不满足这个选项的条件。"
        return "此前的经历还不满足这个选项的条件。"

    def _eligible(self, event):
        s = self.state
        if not event["age_min"] <= s["age"] <= event["age_max"]:
            return False
        for pid in event.get("actors", []):
            if pid not in s["npcs"] or not s["npcs"][pid]["alive"]:
                return False
        return all(self._condition_reason(cond) is None for cond in event.get("requires", []))

    def _render(self, text):
        def replace(match):
            key = match[1]
            if key in {"name", "age", "year"}:
                return str(self.state[key])
            value = self._path(key)
            return str(value) if value is not None else match[0]
        return re.sub(r"\{([A-Za-z0-9_.]+)\}", replace, str(text))

    def _loan_flags(self):
        for pid in self.state["npcs"]:
            loans = [x for x in self.state["loans"] if x["npc"] == pid and x["status"] != "repaid"]
            self.state["flags"][f"loan_{pid}_open"] = bool(loans)
            self.state["flags"][f"loan_{pid}_due"] = any(x["status"] == "outstanding" and x["scheduled"]
                and x["due_year"] <= self.state["year"] for x in loans)

    def _due_loan(self):
        items = [x for x in self.state["loans"] if x["status"] == "outstanding" and x["scheduled"]
                 and x["due_year"] <= self.state["year"] and self.state["npcs"][x["npc"]]["alive"]]
        return min(items, key=lambda x: (x["due_year"], x["id"])) if items else None

    def _loan_event(self, loan):
        npc = self.state["npcs"][loan["npc"]]
        choices = [{"id": "repay", "label": "接受按约还款", "description": "收回约定的本金，需要对方手头有足够的钱。",
                    "requires": [], "effects": [{"op": "loan_repay", "npc": npc["id"]}], "observations": [],
                    "outcome": f"{npc['name']}偿还了这笔 {loan['amount']} 元借款。"}]
        if loan["deferrals"] < 2:
            choices.append({"id": "extend", "label": "再给三年时间", "description": "延长约定，不改变本金。",
                "requires": [], "effects": [], "observations": [{"dimension": "conflict_style", "behavior": "negotiated_extension", "facet": "negotiation_compromise"}],
                "outcome": "你们重新约定了时间。这笔借款仍然存在。"})
        choices.append({"id": "leave", "label": "暂时不再催促，保留债权", "description": "先不催促，欠款继续留在账上。",
                        "requires": [], "effects": [], "observations": [], "outcome": "你暂时放下催促。欠款仍留在账上。"})
        return {"id": f"system.loan.{loan['id']}.{loan['deferrals']}", "title": "到了约定的还款时间", "category": "承诺", "scene": "town",
                "age_min": 0, "age_max": 82, "actors": [npc["id"]], "requires": [], "once": True,
                "text": f"{npc['name']}向你借的 {loan['amount']} 元已到期。对方目前有 {npc['cash']} 元。你可以决定如何继续。",
                "choices": choices, "episode_group": f"loan_due.{loan['id']}",
                "assessment_context": {"life_stage": "dynamic", "pressure_band": "moderate",
                                       "relationship_scope": "friend", "scale": "personal",
                                       "information_level": "partial", "time_horizon": "short"},
                "_kind": "loan_due", "_loan_id": loan["id"]}

    def _fallback(self):
        age = self.state["age"]
        return {"id": f"daily.{self.state['slot_index']}", "title": "普通的一段日子", "category": "日常", "scene": "river",
                "age_min": age, "age_max": age, "once": True, "actors": [], "requires": [], "_kind": "slot",
                "text": "生活暂时没有新的转折。河边的路仍在那里，你可以给自己留一点时间。",
                "episode_group": f"daily.{self.state['slot_index']}",
                "assessment_context": {"life_stage": "dynamic", "pressure_band": "low",
                                       "relationship_scope": "self", "scale": "personal",
                                       "information_level": "known", "time_horizon": "short"},
                "choices": [
                    {"id": "rest", "label": "慢下来，照料自己的身体", "description": "散步、休息，让身心缓一缓。", "requires": [],
                     "effects": [{"op": "stat", "key": "health", "delta": 4}, {"op": "stat", "key": "energy", "delta": 15},
                                 {"op": "stat", "key": "stress", "delta": -10}], "observations": [], "outcome": "这段平常的日子，让你重新有了些余力。"},
                    {"id": "learn", "label": "学一点力所能及的新东西", "description": "从书本和身边的事情开始。", "requires": [],
                     "effects": [{"op": "stat", "key": "skill", "delta": 3}, {"op": "stat", "key": "education", "delta": 2}],
                     "observations": [{"dimension": "exploration", "behavior": "everyday_learning", "facet": "information_seeking"}], "outcome": "没有立刻改变命运的收获，但你多懂了一点。"}]}

    def _reply_event(self):
        for event in self.catalog["events"]:
            if event["id"] in {"adult.partner_yes", "adult.partner_no"} and event["id"] not in self.state["used_events"] and self._eligible(event):
                response = deepcopy(event)
                response["_kind"] = "followup"
                return response
        return None

    def _needs_recovery(self):
        s = self.state
        return (not s["finished"] and s["year"] >= s["survival"]["cooldown_until"]
                and (s["stats"]["health"] <= 28 or s["stats"]["energy"] <= 22 or s["stats"]["stress"] >= 78))

    def _recovery_event(self):
        s = self.state
        choices = [
            {"id": "recovery_rest", "label": "放慢安排，先恢复体力", "description": "不花现金；减少之后的工作收入，给恢复留下时间。", "requires": [],
             "effects": [{"op": "flag", "key": "work_pace", "value": "rest"}, {"op": "stat", "key": "health", "delta": 10},
                         {"op": "stat", "key": "energy", "delta": 25}, {"op": "stat", "key": "stress", "delta": -18}],
             "observations": [], "outcome": "你删去额外安排，先让生活回到身体能够承受的速度。之后的收入也会随节奏减少。"},
            {"id": "recovery_care", "label": "花 1800 元治疗和休整", "description": "及时照顾健康，再以稳健节奏继续生活。", "requires": [],
             "effects": [{"op": "stat", "key": "cash", "delta": -1800}, {"op": "flag", "key": "work_pace", "value": "steady"},
                         {"op": "stat", "key": "health", "delta": 18}, {"op": "stat", "key": "energy", "delta": 20},
                         {"op": "stat", "key": "stress", "delta": -16}],
             "observations": [], "outcome": "你为治疗和休整留出了预算，也重新安排了接下来的负担。"},
            {"id": "recovery_steady", "label": "重新安排作息，维持稳健节奏", "description": "不花现金；恢复幅度较小，也保留正常的工作收入。", "requires": [],
             "effects": [{"op": "flag", "key": "work_pace", "value": "steady"}, {"op": "stat", "key": "health", "delta": 5},
                         {"op": "stat", "key": "energy", "delta": 14}, {"op": "stat", "key": "stress", "delta": -10}],
             "observations": [], "outcome": "你重新划分工作与休息的时间。恢复不会立刻完成，但你开始按可持续的节奏生活。"},
            {"id": "recovery_keep", "label": "暂时维持原来的安排", "description": "继续承受现有负担；若压力和疲惫不缓解，健康仍会受损。", "requires": [],
             "effects": [], "observations": [], "outcome": "你暂时保留了原来的安排，身体与生活的负担也仍然存在。"},
        ]
        if 18 <= s["age"] < 65 and s["status"]["job"] == "none":
            choices.insert(2, {"id": "recovery_job", "label": "先找一份有固定收入的学徒工作", "description": "不需现金或学历门槛；收入从下一次年结算开始。", "requires": [],
                "effects": [{"op": "job", "value": "apprentice"}, {"op": "flag", "key": "work_pace", "value": "steady"},
                            {"op": "stat", "key": "energy", "delta": 12}, {"op": "stat", "key": "stress", "delta": -10}],
                "observations": [], "outcome": "你接受了一份基础学徒工作，先让收入和作息稳定下来。"})
        return {"id": f"system.recovery.{s['year']}.{s['survival']['adjustment_count'] + 1}", "title": "生活需要缓一缓",
                "category": "生活调整", "scene": "home", "age_min": s["age"], "age_max": s["age"], "once": True,
                "actors": [], "requires": [], "_kind": "recovery", "choices": choices,
                "text": f"这一年的负担已经变得明显：健康 {s['stats']['health']}，精力 {s['stats']['energy']}，压力 {s['stats']['stress']}。时间先停在这里，你可以决定怎样调整接下来的生活。"}

    def _select_event(self):
        s = self.state
        if s["finished"]:
            s["current_event"] = None
            return
        if self._needs_recovery():
            s["current_event"] = self._recovery_event()
            return
        due = self._due_loan()
        if due:
            s["current_event"] = self._loan_event(due)
            return
        response = self._reply_event()
        if response:
            s["current_event"] = response
            return
        candidates = [deepcopy(event) for event in self.catalog["events"] if
                      event["id"] not in s["used_events"] and self._eligible(event)]
        def priority(event):
            causal = sum(cond.get("path", "").startswith("flags.") and cond.get("op") == "eq"
                         and cond.get("value") is True for cond in event.get("requires", []))
            entry_job = s["status"]["job"] == "none" and event["id"] in {"youth.school_exit", "youth.apprentice", "youth.career_entry"}
            society_slot = s["slot_index"] % 3 == 2 and bool(event.get("world_domain"))
            closing = s["age"] == 82 and event["id"] == "later.life_review"
            reply = 5 if closing else 4 if entry_job else 3 if event["id"] == "adult.work_pace" else 2 if event["id"] == "youth.partner_meet" else 1 if society_slot else 0
            return (-reply, -causal, event["age_max"] - event["age_min"])
        candidates.sort(key=lambda event: (*priority(event), event["id"]))
        executable = []
        for event in candidates:
            event["_kind"] = "slot"
            if any(self._choice_result(event, c)[0] is not None for c in event["choices"]):
                executable.append(event)
        if executable:
            best = executable[0]
            tied = [e for e in executable if priority(e) == priority(best)]
            s["current_event"] = tied[min(int(self._draw() * len(tied)), len(tied) - 1)]
        else:
            s["current_event"] = self._fallback()

    def _npc(self, pid):
        require(pid in self.state["npcs"], "相关人物不存在。")
        npc = self.state["npcs"][pid]
        require(npc["alive"], f"{npc['name']}已经去世，不能再主动参与这件事。")
        return npc

    def _apply(self, effect, event, changes):
        s, op = self.state, effect.get("op")
        require(op in OPCODES, "这个行动尚未得到规则支持。")
        if op == "stat":
            key, delta = effect.get("key"), effect.get("delta")
            require(key in STAT_NAMES and integer(delta), "属性变化格式不正确。")
            before = s["stats"][key]
            if key != "stress" and delta < 0:
                require(before >= -delta, f"{STAT_NAMES[key]}不足：需要 {-delta}，目前只有 {before}。")
            after = before + delta if key == "cash" else clamp(before + delta)
            require(after >= 0, "现金不能为负。")
            s["stats"][key] = after
            if after != before:
                changes.append(f"{STAT_NAMES[key]} {after - before:+d}")
        elif op == "flag":
            key, value = effect.get("key"), effect.get("value")
            require(isinstance(key, str) and isinstance(value, (bool, int, str)), "经历标记格式不正确。")
            require(not key.startswith("world."), "个人选择不能直接改写世界状态。")
            require(key not in {"work_push_years", "work_push_seen"}, "实际工作经历只能由年度结算记录。")
            if key == "work_pace":
                require(value in PACE_LABELS, "请选择稳健、加紧或放慢三种节奏。")
                changes.append(f"生活节奏：{PACE_LABELS[value]}")
            if key in {"partner_met", "partnered"} and value is True:
                self._npc("partner")["met"] = True
                s["flags"]["partner_met"] = True
            if key == "partnered":
                s["npcs"]["partner"]["role"] = "伴侣" if value is True else "相识的人"
            if key == "has_child" and value is True and not s["flags"].get("has_child"):
                require(s["age"] >= 18, "目前还不适合承担养育孩子的决定。")
                s["child_birth_year"] = s["year"]
                changes.append("家庭中有了孩子")
            s["flags"][key] = value
        elif op == "relation":
            npc, delta = self._npc(effect.get("npc")), effect.get("delta")
            require(integer(delta), "关系变化必须是整数。")
            before = npc["closeness"]
            npc["closeness"] = clamp(before + delta)
            if npc["closeness"] != before:
                changes.append(f"与{npc['name']}的亲近 {npc['closeness'] - before:+d}")
        elif op == "npc_cash":
            npc, delta = self._npc(effect.get("npc")), effect.get("delta")
            require(integer(delta) and npc["cash"] + delta >= 0, f"{npc['name']}没有足够的现金。")
            npc["cash"] += delta
            changes.append(f"{npc['name']}的现金 {delta:+d}")
        elif op == "job":
            job = effect.get("value")
            require(job in JOBS and s["age"] >= 18, "目前不能进入这份工作。")
            s["status"]["job"] = job
            changes.append(f"工作：{JOBS[job][0]}")
        elif op == "loan":
            npc, amount, years = self._npc(effect.get("npc")), effect.get("amount"), effect.get("due_years")
            require(integer(amount) and amount > 0 and integer(years) and years > 0, "借款金额和期限须为正整数。")
            require(s["age"] >= 18, "成年后才能独立借出这笔钱。")
            require(s["stats"]["cash"] >= amount, f"现金不足：需要 {amount}，目前只有 {s['stats']['cash']}。")
            require(not any(x["npc"] == npc["id"] and x["status"] != "repaid" for x in s["loans"]), "这位朋友还有尚未处理的借款。")
            s["stats"]["cash"] -= amount
            npc["cash"] += amount
            s["loans"].append({"id": f"loan-{len(s['loans']) + 1}", "npc": npc["id"], "amount": amount,
                               "created_year": s["year"], "due_year": s["year"] + years,
                               "status": "outstanding", "scheduled": True, "deferrals": 0})
            changes.append(f"借出 {amount} 元，约定 {years} 年后归还")
        elif op == "loan_repay":
            npc = self._npc(effect.get("npc"))
            candidates = [x for x in s["loans"] if x["npc"] == npc["id"] and x["status"] == "outstanding"
                          and x["due_year"] <= s["year"]]
            require(bool(candidates), "目前没有到期且尚未归还的这笔借款。")
            loan = next((x for x in candidates if x["id"] == event.get("_loan_id")), candidates[0])
            require(npc["cash"] >= loan["amount"], f"{npc['name']}目前只有 {npc['cash']} 元，无法足额还款。")
            npc["cash"] -= loan["amount"]
            s["stats"]["cash"] += loan["amount"]
            loan.update(status="repaid", scheduled=False, repaid_year=s["year"])
            changes.append(f"收回借款 {loan['amount']} 元")
        self._loan_flags()

    def _choice_result(self, event, choice):
        clone = self._fork()
        changes = []
        try:
            require(clone._eligible(event), "这件事的前提已经发生变化。")
            for condition in choice.get("requires", []):
                reason = clone._condition_reason(condition)
                require(reason is None, reason)
            for effect in choice.get("effects", []):
                clone._apply(effect, event, changes)
            if event.get("_kind") == "loan_due" and choice["id"] in {"extend", "leave"}:
                loan = next(x for x in clone.state["loans"] if x["id"] == event["_loan_id"])
                if choice["id"] == "extend":
                    require(loan["deferrals"] < 2, "这笔约定已经延期过两次。")
                    loan["due_year"] = clone.state["year"] + 3
                    loan["deferrals"] += 1
                    changes.append("还款期限延后三年")
                else:
                    loan["scheduled"] = False
                    changes.append("债权保留，停止到期提醒")
                clone._loan_flags()
            if event.get("_kind") == "recovery":
                clone.state["survival"]["adjustment_count"] += 1
                clone.state["survival"]["cooldown_until"] = clone.state["year"] + RECOVERY_COOLDOWN_YEARS
            clone._update_budget()
            clone._validate(check_event=False)
            return clone.state, changes
        except RuleError as exc:
            return None, str(exc)

    def _costs(self, choice):
        costs = []
        for effect in choice.get("effects", []):
            op = effect["op"]
            if op == "stat":
                costs.append(f"{STAT_NAMES[effect['key']]} {effect['delta']:+d}")
            elif op == "loan":
                costs.append(f"现金 -{effect['amount']}（借出）")
            elif op == "relation":
                costs.append(f"与{self.state['npcs'][effect['npc']]['name']}的亲近 {effect['delta']:+d}")
            elif op == "job":
                costs.append("进入退休生活" if effect["value"] == "retired" else f"成为{JOBS[effect['value']][0]}")
            elif op == "flag" and effect["key"] == "work_pace":
                costs.append(f"后续采用{PACE_LABELS[effect['value']]}")
        return costs

    def choose(self, choice_id, expected_revision):
        require(integer(expected_revision) and expected_revision == self.state["revision"], "这一页已经更新，请刷新后再作选择。")
        require(not self.state["finished"], "这段人生已经结束。")
        event = self.state["current_event"]
        require(isinstance(event, dict), "目前没有可作出的选择。")
        chosen = next((x for x in event["choices"] if x["id"] == choice_id), None)
        require(chosen is not None, "找不到这个选项。")
        options = []
        chosen_state, chosen_changes = None, None
        for choice in event["choices"]:
            candidate, result = self._choice_result(event, choice)
            options.append({"id": choice["id"], "label": choice["label"], "available": candidate is not None,
                            "reason": None if candidate is not None else result})
            if choice["id"] == choice_id:
                chosen_state, chosen_changes = candidate, result
        require(chosen_state is not None, chosen_changes or "这个选项目前不可执行。")
        working = object.__new__(LifeGame)
        working.state, working.catalog = chosen_state, self.catalog
        before, s = self.state, working.state
        cash_cost = sum(-e["delta"] for e in chosen.get("effects", []) if e["op"] == "stat" and e["key"] == "cash" and e["delta"] < 0)
        cash_cost += sum(e["amount"] for e in chosen.get("effects", []) if e["op"] == "loan")
        npc_ids = set(event.get("actors", [])) | {e["npc"] for e in chosen.get("effects", []) if "npc" in e}
        text = working._render(chosen.get("outcome", "你作出了自己的选择。"))
        working._record("choice", event["title"], text, choice=chosen["label"], choice_id=chosen["id"],
                        event_id=event["id"], observations=chosen.get("observations", []), npc_ids=sorted(npc_ids),
                        episode_id=event.get("episode_group", event["id"]),
                        gained_flags={effect["key"]: s["flags"][effect["key"]] for effect in chosen.get("effects", []) if effect["op"] == "flag"},
                        context={"available_choice_ids": [x["id"] for x in options if x["available"]],
                                 "locked_options": [{"id": x["id"], "reason": x["reason"]} for x in options if not x["available"]],
                                 "resources_before": before["stats"], "cash_cost": cash_cost,
                                 "cash_cost_share": cash_cost / before["stats"]["cash"] if before["stats"]["cash"] else None,
                                 "npc_knowledge": [{k: n[k] for k in ("id", "name", "alive", "met")} for n in before["npcs"].values() if n["met"]],
                                 "context_tags": [event["category"], stage(before["age"])],
                                 "opportunity_dimensions": sorted({item.get("dimension", item.get("dimension_id"))
                                                                    for option in event.get("choices", [])
                                                                    for item in option.get("observations", [])
                                                                    if item.get("dimension", item.get("dimension_id"))}),
                                 "assessment_context": deepcopy(event.get("assessment_context", {})),
                                 "presented_text": self._render(event["text"]), "opportunity": sum(x["available"] for x in options) >= 2})
        s["timeline"][-1]["context"]["world_context"] = world_rules.event_context(before["world"], event.get("world_domain"), requires=event.get("requires", []))
        s["timeline"][-1]["context"]["world_modifiers"] = world_rules.modifiers(before["world"])
        s["last_outcome"] = {"title": event["title"], "text": text, "changes": chosen_changes}
        if event.get("_kind") != "loan_due":
            s["used_events"].append(event["id"])
        if event.get("_kind") == "slot":
            s["slot_index"] += 1
        s["current_event"] = None
        if s["stats"]["health"] <= 0:
            working._finish("健康耗尽")
        elif s["slot_index"] >= len(AGES):
            working._finish("在八十二岁走完了这一生")
        else:
            response = working._reply_event()
            if working._needs_recovery():
                s["current_event"] = working._recovery_event()
            elif response:
                s["current_event"] = response
            else:
                working._advance_to(AGES[s["slot_index"]])
                working._select_event()
        s["revision"] += 1
        s["population"] = population_rules.sync_anchors(s["population"], s["npcs"], s["year"])
        working._validate()
        self.state = s
        return self

    def people(self, query="", group="known", offset=0, limit=24):
        require(isinstance(query, str) and len(query) <= 80, "搜索词请控制在 80 字内。")
        require(group in {"known", "direct", "close", "important", "deceased"}, "没有这一类人物。")
        require(integer(offset) and offset >= 0 and integer(limit) and 1 <= limit <= 48, "人物分页范围不正确。")
        return population_rules.population_view(self.state["population"], query=query, group=group, offset=offset, limit=limit)

    def person(self, npc_id):
        require(isinstance(npc_id, str), "人物编号无效。")
        try:
            result = population_rules.person_view(self.state["population"], npc_id)
            result["actions"] = [] if self.state["finished"] else population_rules.interaction_options(
                self.state["population"], npc_id, self.state["age"], self.state["stats"])
            for action in result["actions"]:
                if action["available"]:
                    try:
                        self._fork().social(npc_id, action["id"], self.state["revision"])
                    except RuleError:
                        action.update(available=False, locked_reason="请先完成眼前的人生片段，再安排这次来往。")
            return result
        except population_rules.PopulationError as exc:
            raise RuleError(str(exc)) from exc

    def social(self, npc_id, action, expected_revision):
        require(integer(expected_revision) and expected_revision == self.state["revision"], "这一页已经更新，请刷新后再作选择。")
        require(not self.state["finished"], "这段人生已经结束。")
        require(isinstance(npc_id, str) and isinstance(action, str), "交往指令无效。")
        working = self._fork()
        s = working.state
        try:
            s["population"], result = population_rules.interact(s["population"], npc_id, action, s["age"], s["stats"])
        except population_rules.PopulationError as exc:
            raise RuleError(str(exc)) from exc
        for key, value in result.get("costs", {}).items():
            require(key in STAT_NAMES and integer(value) and value >= 0 and s["stats"][key] >= value, "交往所需资源不足。")
            s["stats"][key] -= value
        for key, value in result.get("stat_deltas", {}).items():
            require(key in STAT_NAMES and integer(value), "交往后果格式不正确。")
            s["stats"][key] = max(0, s["stats"][key] + value) if key == "cash" else clamp(s["stats"][key] + value)
        working._record("social", result["title"], result["text"], action=action,
                        population_ids=[npc_id], observations=[], costs=result.get("costs", {}))
        s["last_outcome"] = {key: result.get(key, []) for key in ("title", "text", "changes")}
        s["revision"] += 1
        working._validate()
        self.state = s
        return self

    def set_social_plan(self, plan, expected_revision):
        require(integer(expected_revision) and expected_revision == self.state["revision"], "这一页已经更新，请刷新后再作选择。")
        require(not self.state["finished"], "这段人生已经结束。")
        labels = {"balanced": "兼顾各处", "family": "照应身边人", "work": "工作与学业", "community": "走进社区", "guarded": "保留私人空间"}
        require(isinstance(plan, str) and plan in labels, "请选择已有的交往安排。")
        require(plan != self.state["population"]["plan"], "目前已经采用这一安排。")
        require(sum(row["year"] == self.state["year"] and row["kind"] == "social_plan" for row in self.state["timeline"]) < 3,
                "这一年已经调整过三次安排，请先继续生活。")
        working = self._fork()
        working.state["population"] = population_rules.set_plan(working.state["population"], plan)
        working._record("social_plan", "为日常来往留些时间", f"你决定在接下来的日常交往中采用「{labels[plan]}」的安排。实际接触会随年份推进。", observations=[])
        working.state["revision"] += 1
        working._validate()
        self.state = working.state
        return self

    def _annual_plan(self, age=None):
        """One source for forecasts and annual settlement; excludes one-off events."""
        s, stats = self.state, self.state["stats"]
        age = s["age"] if age is None else age
        year = s["born_year"] + age
        world_modifiers = world_rules.modifiers(s["world"])
        job = "retired" if age >= 65 else s["status"]["job"]
        pace = s["flags"]["work_pace"]
        if age >= 65 and s["status"]["job"] != "retired":
            pace = "steady"
        if age < 18:
            allowance = {"struggling": 20, "ordinary": 50, "comfortable": 110}[s["origin"]]
            return {"job": job, "pace": "steady", "pace_label": "在家人与学校支持下成长", "income": allowance, "expenses": 0,
                    "energy_change": clamp((76 - stats["energy"]) // 4, -4, 8),
                    "stress_change": clamp((16 - stats["stress"]) // 4, -5, 4), "health_change": 0,
                    "world_modifiers": world_modifiers, "world_year": s["world"]["year"]}
        base, load = JOBS[job][1:]
        if job == "retired":
            income = base + (2000 if s["flags"].get("retirement_planned") else 0)
        elif job == "none":
            income = base + min(stats["skill"], 50) * 30
        else:
            skill_bonus = min(stats["skill"], 40) * 90 + max(0, min(stats["skill"] - 40, 40)) * 30
            income = base + skill_bonus + min(stats["education"], 50) * 30
        if job != "retired":
            income = income * {"steady": 100, "push": 115, "rest": 75}[pace] // 100
        has_young_child = (s["flags"].get("has_child") and s["child_birth_year"] is not None
                           and year - s["child_birth_year"] < 18)
        expenses = 16800 - (3000 if s["flags"].get("settled_home") else 0)
        expenses += 2400 if s["flags"].get("partnered") else 0
        expenses += 4800 if has_young_child else 0
        expenses += 2400 if age >= 70 else 0
        income = income * world_modifiers["income_percent"] // 100
        expenses = expenses * world_modifiers["expense_percent"] // 100
        if pace == "push":
            energy_delta = (-4 if job == "retired" else -7) - int(has_young_child)
            stress_delta = (4 if job == "retired" else 7 + load // 3) + int(has_young_child)
        elif pace == "rest":
            energy_delta = clamp((85 - stats["energy"]) // 3, -3, 14)
            stress_delta = clamp((18 - stats["stress"]) // 3, -12, 3)
        else:
            energy_target = 72 - load * 2 - (4 if has_young_child else 0)
            stress_target = 24 + load * 3 + (6 if has_young_child else 0) + (8 if job == "none" else 0)
            energy_delta = clamp((energy_target - stats["energy"]) // 4, -4, 7)
            stress_delta = clamp((stress_target - stats["stress"]) // 4, -5, 6)
        energy_after = clamp(stats["energy"] + energy_delta)
        stress_after = clamp(stats["stress"] + stress_delta)
        ageing = 2 if age >= 80 else 1 if age >= 68 else int(age >= 50 and age % 4 == 0)
        strain = 2 * int(energy_after <= 22) + 2 * int(stress_after >= 78)
        strain += int(pace == "push" and job != "retired" and s["survival"]["consecutive_push_years"] >= 2)
        return {"job": job, "pace": pace, "pace_label": PACE_LABELS[pace], "income": income, "expenses": expenses,
                "energy_change": energy_after - stats["energy"], "stress_change": stress_after - stats["stress"],
                "health_change": -ageing - strain, "world_modifiers": world_modifiers, "world_year": s["world"]["year"]}

    def _update_budget(self):
        plan = self._annual_plan()
        self.state["status"].update(job_label="在校" if self.state["age"] < 18 else JOBS[plan["job"]][0],
                                    income=plan["income"], expenses=plan["expenses"])

    def _outlook(self):
        s = self.state
        if s["finished"] or s["age"] >= 82:
            return {"pace": s["flags"]["work_pace"], "pace_label": PACE_LABELS[s["flags"]["work_pace"]],
                    "income": 0, "expenses": 0, "balance": 0, "years_to_next": 0, "energy_change": 0,
                    "stress_change": 0, "warnings": ["这段人生已经结束，没有后续年度结算。" if s["finished"] else "已经来到最后的回顾，不再进行下一年度结算。"]}
        plan = self._annual_plan(min(s["age"] + 1, 82))
        next_slot = s["slot_index"] + int(s["current_event"].get("_kind") == "slot")
        years = max(0, AGES[next_slot] - s["age"]) if next_slot < len(AGES) else 0
        warnings = []
        if plan["income"] < plan["expenses"]:
            warnings.append(f"按当前安排，下一年预计缺口 {plan['expenses'] - plan['income']} 元，需要动用积蓄或调整生活。")
        if s["stats"]["energy"] <= 30:
            warnings.append("精力已经偏低，持续透支会影响健康。")
        if s["stats"]["stress"] >= 70:
            warnings.append("压力接近危险水平，继续加重负担会损伤健康。")
        if s["stats"]["health"] <= 35:
            warnings.append("健康余量有限，宜在继续跨年之前安排恢复。")
        if plan["pace"] == "push" and plan["job"] != "retired":
            warnings.append("加紧节奏增加收入；连续第三年起，额外透支也会直接消耗健康。")
        if plan["job"] == "retired" and s["status"]["job"] != "retired":
            warnings.append("下一年将进入退休预算，并恢复稳健节奏。")
        warnings.append("这是下一年的常规预算；不含一次性借还款、家人支援及额外事件，跨年中可能提前停下。")
        warnings.append("预测沿用当前时代状况；未来世界变化可能改变实际收入与开支。")
        return {key: plan[key] for key in ("pace", "pace_label", "income", "expenses", "energy_change", "stress_change")} | {
            "balance": plan["income"] - plan["expenses"], "years_to_next": years, "warnings": warnings}

    def _npc_year(self):
        s = self.state
        for npc in s["npcs"].values():
            if not npc["alive"]:
                continue
            npc["age"] = s["year"] - npc["birth_year"]
            age = npc["age"]
            if age >= 18:
                npc["cash"] += 1600 if age < 65 else 700
            risk = 0 if age < 65 else 0.006 if age < 75 else 0.025 if age < 82 else 0.075 if age < 90 else 0.18
            if npc["cash"] < 1000 and age >= 65:
                risk *= 1.2
            if age >= 95 or (risk and self._draw() < risk):
                self._npc_death(npc["id"])

    def _npc_death(self, pid):
        s, npc = self.state, self.state["npcs"][pid]
        if not npc["alive"]:
            return
        npc.update(alive=False, death_year=s["year"], death_age=s["year"] - npc["birth_year"])
        for loan in s["loans"]:
            if loan["npc"] == pid and loan["status"] == "outstanding":
                loan.update(status="deceased_pending", scheduled=False)
        if pid == "partner" and s["flags"].get("partnered"):
            s["flags"].update(partnered=False, widowed=True)
            npc["role"] = "已故伴侣"
        if npc["met"]:
            s["stats"]["stress"] = clamp(s["stats"]["stress"] + (16 if pid == "partner" else 8))
            self._record("npc_death", f"告别{npc['name']}", f"{npc['name']}于 {s['year']} 年去世，享年 {npc['death_age']} 岁。共同的过去仍然留在你的人生中。", npc_ids=[pid])
        self._loan_flags()

    def _annual(self):
        s, stats = self.state, self.state["stats"]
        s["world"] = world_rules.advance_world(s["world"], s["year"], self.catalog["world_catalog"], validate_input=False)
        plan = self._annual_plan()
        before_stats = deepcopy(stats)
        self._npc_year()
        s["population"] = population_rules.advance_population(s["population"], s["year"], s["npcs"],
            world_metrics=s["world"]["metrics"], plan=s["population"]["plan"])
        if s["age"] < 18:
            allowance = plan["income"]
            stats["cash"] += allowance
            stats["education"] = clamp(stats["education"] + 2)
            stats["skill"] = clamp(stats["skill"] + 1)
            stats["energy"] = clamp(stats["energy"] + plan["energy_change"])
            stats["stress"] = clamp(stats["stress"] + plan["stress_change"])
            self._update_budget()
            self._record("annual", "又长大了一岁", f"家人承担日常生活开支。你得到 {allowance} 元零用钱，继续读书和成长。",
                         accounting={"income": allowance, "expenses": 0, "cash_after": stats["cash"]},
                         annual_plan=plan, resource_changes={key: stats[key] - before_stats[key] for key in STAT_NAMES})
            return
        if not s["family_grant_given"]:
            requested = ORIGINS[s["origin"]][1]
            grant = 0
            for pid in ("mother", "father"):
                npc = s["npcs"][pid]
                amount = min(max(0, npc["cash"] - 3000), requested - grant) if npc["alive"] else 0
                npc["cash"] -= amount
                grant += amount
            stats["cash"] += grant
            s["family_grant_given"] = True
            self._record("family", "第一次独立的预算", f"家人从积蓄中拿出 {grant} 元，作为你迈向成年生活的起步预算。", npc_ids=["mother", "father"])
        if s["age"] >= 65 and s["status"]["job"] != "retired":
            s["status"]["job"] = "retired"
            s["flags"]["work_pace"] = "steady"
            self._record("retirement", "开始退休生活", "你告别固定工作，开始使用退休后的生活预算。")
        self._update_budget()
        income, expected = plan["income"], plan["expenses"]
        stats["cash"] += income
        if stats["cash"] < expected:
            support = 0
            for pid in ("mother", "father"):
                npc = s["npcs"][pid]
                amount = min(1500, max(0, npc["cash"] - 8000), expected - stats["cash"]) if npc["alive"] else 0
                npc["cash"] -= amount
                stats["cash"] += amount
                support += amount
            aid = min(2000, s["aid_remaining"], max(0, expected - stats["cash"]))
            s["aid_remaining"] -= aid
            stats["cash"] += aid
            if support or aid:
                stats["stress"] = clamp(stats["stress"] + 4)
                self._record("aid", "借助身边的支持", f"这一年预算吃紧，家人支援 {support} 元，临时生活援助 {aid} 元。公共援助剩余额度 {s['aid_remaining']} 元。")
        paid = min(stats["cash"], expected)
        shortage = expected - paid
        stats["cash"] -= paid
        if shortage:
            health_cost = min(6, 1 + shortage // 2500)
            stats["health"] = max(0, stats["health"] - health_cost)
            stats["stress"] = clamp(stats["stress"] + 9)
            self._record("hardship", "收紧生活", f"你压缩了 {shortage} 元生活开支来避免负债，健康减少 {health_cost} 点，压力增加。")
        if s["status"]["job"] not in {"none", "retired"}:
            stats["skill"] = clamp(stats["skill"] + 1)
        stats["energy"] = clamp(stats["energy"] + plan["energy_change"])
        stats["stress"] = clamp(stats["stress"] + plan["stress_change"])
        health_loss = -plan["health_change"]
        if stats["stress"] >= 78 and before_stats["stress"] + plan["stress_change"] < 78:
            health_loss += 2
        if plan["pace"] == "push" and plan["job"] != "retired":
            s["survival"]["consecutive_push_years"] += 1
            s["flags"]["work_push_years"] += 1
            s["flags"]["work_push_seen"] = True
        else:
            s["survival"]["consecutive_push_years"] = 0
        stats["health"] = max(0, stats["health"] - health_loss)
        self._record("annual", "这一年的生活账", f"按{plan['pace_label']}安排，收入 {income} 元，实际生活支出 {paid} 元，结余现金 {stats['cash']} 元。精力变化 {stats['energy'] - before_stats['energy']:+d}，压力变化 {stats['stress'] - before_stats['stress']:+d}。" + (f"年龄、疲惫和压力使健康减少 {health_loss} 点。" if health_loss else ""),
                     accounting={"income": income, "expenses": paid, "planned_expenses": expected, "cash_after": stats["cash"]},
                     annual_plan=plan, resource_changes={key: stats[key] - before_stats[key] for key in STAT_NAMES})
        self._loan_flags()
        if stats["health"] <= 0:
            self._finish("健康耗尽")

    def _advance_to(self, target):
        while self.state["age"] < target and not self.state["finished"]:
            if self._needs_recovery() or self._due_loan():
                self._update_budget()
                return
            self.state["age"] += 1
            self.state["year"] += 1
            self._annual()
        self._update_budget()

    def _finish(self, reason):
        s = self.state
        if s["finished"]:
            return
        s.update(finished=True, death_reason=reason, current_event=None)
        for loan in s["loans"]:
            if loan["status"] == "outstanding":
                loan.update(status="deceased_pending", scheduled=False)
        self._loan_flags()
        self._record("death", "人生落笔", f"{s['name']}的一生停在 {s['age']} 岁。{reason}。留下的选择与关系，成为这部人物志的依据。")

    def _validate(self, check_event=True):
        s = self.state
        require(s["version"] == VERSION, "人生状态版本不兼容。")
        require(s["content_version"] == self.catalog.get("version", "unknown"), "事件库版本已改变，这份存档需要迁移后才能继续。")
        require(isinstance(s["name"], str) and 1 <= len(s["name"]) <= 20 and s["origin"] in ORIGINS, "人物身份无效。")
        require(integer(s["revision"]) and s["revision"] >= 0 and integer(s["seed"]), "存档版本号或随机种子无效。")
        require(integer(s["random_counter"]) and s["random_counter"] >= 0, "随机进度无效。")
        require(integer(s["age"]) and 6 <= s["age"] <= 82 and s["year"] == s["born_year"] + s["age"], "人生时间不一致。")
        require(integer(s["born_year"]) and s["born_year"] in {1, 1988} and integer(s["slot_index"]) and 0 <= s["slot_index"] <= len(AGES), "人生阶段不一致。")
        try:
            world_rules.validate_world(s["world"], self.catalog["world_catalog"], expected_year=s["year"], full_history=check_event)
        except world_rules.WorldError as exc:
            raise RuleError(str(exc)) from exc
        try:
            population_rules.validate_population(s["population"], anchors=s["npcs"] if check_event else None,
                expected_year=s["year"], full=False)
        except population_rules.PopulationError as exc:
            raise RuleError(str(exc)) from exc
        require(s["population"]["source_seed"] == s["seed"] and s["population"]["player_birth_year"] == s["born_year"], "人物群体与这段人生的来源不一致。")
        require(s["born_year"] + 6 <= s["population"]["start_year"] <= s["year"], "人物群体开始记录的时间无效。")
        require(s["world"]["source_seed"] == s["seed"], "人物与世界的种子来源不一致。")
        require((s["born_year"] == 1 and s["world"]["calendar"] == "新历" and s["world"]["start_year"] == 1)
                or (s["born_year"] == 1988 and s["world"]["calendar"] == "旧档纪年" and s["born_year"] + 6 <= s["world"]["start_year"] <= s["year"]), "人物与世界历法不一致。")
        require(isinstance(s["finished"], bool), "人生结束状态无效。")
        require(isinstance(s["flags"], dict) and all(isinstance(k, str) and isinstance(v, (bool, int, str))
                for k, v in s["flags"].items()), "经历标记无效。")
        require(s["flags"].get("work_pace") in PACE_LABELS, "工作节奏无效。")
        require(integer(s["flags"].get("work_push_years")) and 0 <= s["flags"]["work_push_years"] <= max(0, s["age"] - 17), "实际加紧工作的年数无效。")
        require(isinstance(s["flags"].get("work_push_seen"), bool) and s["flags"]["work_push_seen"] == (s["flags"]["work_push_years"] > 0), "工作节奏与实际年度经历不一致。")
        require(isinstance(s["survival"], dict), "生活调整记录无效。")
        require(integer(s["survival"]["cooldown_until"]) and s["born_year"] <= s["survival"]["cooldown_until"] <= s["year"] + RECOVERY_COOLDOWN_YEARS, "生活调整冷却时间无效。")
        require(integer(s["survival"]["adjustment_count"]) and 0 <= s["survival"]["adjustment_count"] <= (s["age"] - 6) // RECOVERY_COOLDOWN_YEARS + 1, "生活调整次数无效。")
        require(integer(s["survival"]["consecutive_push_years"]) and 0 <= s["survival"]["consecutive_push_years"] <= s["flags"]["work_push_years"], "连续透支记录无效。")
        require(s["migration_note"] is None or isinstance(s["migration_note"], str), "迁移说明无效。")
        require(isinstance(s["used_events"], list) and len(s["used_events"]) >= s["slot_index"]
                and len(set(s["used_events"])) == len(s["used_events"]), "已发生的事件与人生进度不一致。")
        for key in STAT_NAMES:
            value = s["stats"][key]
            require(integer(value) and value >= 0 and (key == "cash" or value <= 100), f"{STAT_NAMES[key]}超出有效范围。")
        require(s["status"]["job"] in JOBS and integer(s["aid_remaining"]) and 0 <= s["aid_remaining"] <= 12000, "预算或援助额度无效。")
        require(all(integer(s["status"][key]) and s["status"][key] >= 0 for key in ("income", "expenses")), "年度预算数值无效。")
        require(set(s["npcs"]) == {"mother", "father", "friend", "partner"}, "人物关系不完整。")
        for pid, npc in s["npcs"].items():
            require(npc["id"] == pid and isinstance(npc["alive"], bool) and isinstance(npc["met"], bool), "人物身份状态不正确。")
            require(integer(npc["cash"]) and npc["cash"] >= 0 and integer(npc["closeness"]) and 0 <= npc["closeness"] <= 100, "人物财产或关系无效。")
            if npc["alive"]:
                require(npc["death_year"] is None and npc["death_age"] is None and npc["age"] == s["year"] - npc["birth_year"], "在世人物的时间状态不一致。")
            else:
                require(integer(npc["death_year"]) and npc["birth_year"] <= npc["death_year"] <= s["year"], "人物死亡时间无效。")
                require(npc["death_age"] == npc["death_year"] - npc["birth_year"] and npc["age"] == npc["death_age"], "人物享年不一致。")
        if s["flags"].get("partnered"):
            require(s["npcs"]["partner"]["met"] and s["npcs"]["partner"]["alive"], "伴侣关系与人物状态不一致。")
        require(bool(s["flags"].get("partner_met")) == s["npcs"]["partner"]["met"], "相识记录与伴侣状态不一致。")
        require((s["child_birth_year"] is not None) == bool(s["flags"].get("has_child")), "孩子的记录不一致。")
        if s["child_birth_year"] is not None:
            require(integer(s["child_birth_year"]) and s["born_year"] + 18 <= s["child_birth_year"] <= s["year"], "孩子出生时间无效。")
        loan_ids = set()
        for loan in s["loans"]:
            require(loan["id"] not in loan_ids and loan["npc"] in s["npcs"], "债务身份无效。")
            loan_ids.add(loan["id"])
            require(integer(loan["amount"]) and loan["amount"] > 0, "债务本金无效。")
            require(integer(loan["created_year"]) and integer(loan["due_year"]) and s["born_year"] <= loan["created_year"] <= s["year"] and loan["due_year"] >= loan["created_year"], "债务日期无效。")
            require(loan["status"] in {"outstanding", "repaid", "deceased_pending"} and isinstance(loan["scheduled"], bool), "债务状态无效。")
            require(integer(loan["deferrals"]) and 0 <= loan["deferrals"] <= 2, "债务延期记录无效。")
            if loan["status"] == "outstanding":
                require(s["npcs"][loan["npc"]]["alive"] and not s["finished"], "已故人物不能继续主动履行约定。")
            else:
                require(not loan["scheduled"], "已经终止的约定不能继续触发。")
        require(isinstance(s["timeline"], list) and s["sequence"] == len(s["timeline"]), "人生记录序号不一致。")
        last_age = -1
        deaths = {}
        for index, entry in enumerate(s["timeline"], 1):
            require(entry["id"] == f"life-{index}" and integer(entry["age"]) and last_age <= entry["age"] <= s["age"], "人生记录时间或编号不一致。")
            require(entry["year"] == s["born_year"] + entry["age"], "人生记录年份不一致。")
            last_age = entry["age"]
            if entry.get("kind") == "npc_death":
                for pid in entry.get("npc_ids", []):
                    require(pid not in deaths and pid in s["npcs"], "人物死亡记录重复或缺少身份。")
                    deaths[pid] = entry["year"]
        for pid, year in deaths.items():
            require(not s["npcs"][pid]["alive"] and s["npcs"][pid]["death_year"] == year,
                    "已去世的人物不能在存档中重新成为在世状态。")
        if check_event:
            require(sum(entry.get("kind") in {"choice", "social", "social_plan"} for entry in s["timeline"]) == s["revision"], "选择记录与版本号不一致。")
            require(sum(entry.get("kind") == "social" for entry in s["timeline"]) == s["population"]["action_counter"], "主动交往次数与实际记录不一致。")
            for row in s["timeline"]:
                for pid in row.get("population_ids", []):
                    require(pid in s["population"]["people"] and s["population"]["people"][pid]["birth_year"] <= row["year"], "交往记录引用了不存在或尚未出生的人。")
            recovery_rows = [row for row in s["timeline"] if row.get("kind") == "choice" and row.get("event_id", "").startswith("system.recovery.")]
            require(len(recovery_rows) == s["survival"]["adjustment_count"], "生活调整与实际选择记录不一致。")
            if recovery_rows:
                require(s["survival"]["cooldown_until"] == recovery_rows[-1]["year"] + RECOVERY_COOLDOWN_YEARS, "生活调整日期与记录不一致。")
                require(all(b["year"] - a["year"] >= RECOVERY_COOLDOWN_YEARS for a, b in zip(recovery_rows, recovery_rows[1:])), "生活调整发生得过于频繁。")
            if s["finished"]:
                require(s["current_event"] is None and isinstance(s["death_reason"], str), "结束状态不能仍有可选事件。")
            else:
                require(s["stats"]["health"] > 0 and s["death_reason"] is None, "存活与健康状态不一致。")
                require(s["slot_index"] < len(AGES) and isinstance(s["current_event"], dict), "人生缺少当前事件。")
                event = s["current_event"]
                _event_contract(event)
                require(event.get("_kind") in {"slot", "followup", "loan_due", "recovery"}, "当前事件的推进方式无效。")
                require(event["id"] not in s["used_events"], "已经发生的一次性事件不能再次成为当前事件。")
                if event["_kind"] == "loan_due":
                    loan = next((item for item in s["loans"] if item["id"] == event.get("_loan_id")), None)
                    require(loan is not None and loan["status"] == "outstanding" and loan["scheduled"]
                            and loan["due_year"] <= s["year"], "还款事件没有对应的有效到期约定。")
                    require(event["actors"] == [loan["npc"]], "还款事件与债务当事人不一致。")
                if event["_kind"] == "recovery":
                    require(self._needs_recovery(), "当前状态不需要再次触发生活调整。")
                    require(event["id"] == f"system.recovery.{s['year']}.{s['survival']['adjustment_count'] + 1}", "生活调整事件与当前年份不一致。")
                require(self._eligible(event), "当前事件与年龄、人物生死或经历不一致。")

    def _causes(self, event):
        conditions = [cond for cond in event.get("requires", []) if cond["path"].startswith("flags.")]
        found = []
        seen = set()
        for condition in conditions:
            if self._condition_reason(condition) is not None:
                continue
            key = condition["path"].split(".", 1)[1]
            actual = self._path(condition["path"])
            for row in reversed(self.state["timeline"]):
                written = row.get("gained_flags", {})
                if key in written and type(written[key]) is type(actual) and written[key] == actual:
                    if row["id"] not in seen:
                        found.append({"id": row["id"], "title": row["title"], "age": row["age"], "choice": row.get("choice", "")})
                        seen.add(row["id"])
                    break
            if len(found) >= 3:
                break
        return found

    def view(self):
        s = self.state
        event = s["current_event"]
        public_event = None
        if event is not None and not s["finished"]:
            choices = []
            for choice in event["choices"]:
                candidate, reason = self._choice_result(event, choice)
                choices.append({"id": choice["id"], "label": choice["label"], "description": choice.get("description", ""),
                                "available": candidate is not None, "locked_reason": None if candidate is not None else reason,
                                "costs": self._costs(choice)})
            public_event = {k: event[k] for k in ("id", "title", "category", "scene")}
            public_event.update(text=self._render(event["text"]), choices=choices, causes=self._causes(event),
                                world_context=world_rules.event_context(s["world"], event.get("world_domain"), requires=event.get("requires", [])))
        npcs = []
        for npc in s["npcs"].values():
            row = {k: npc[k] for k in ("id", "name", "role", "age", "alive", "met", "closeness", "cash")}
            if npc["id"] == "partner":
                row["role"] = "已故伴侣" if s["flags"].get("widowed") else "伴侣" if s["flags"].get("partnered") else "相识的人"
            row["description"] = "尚未相识" if not npc["met"] else f"已于 {npc['death_year']} 年去世，享年 {npc['death_age']} 岁" if not npc["alive"] else f"仍在青溪镇的生活中，{npc['age']} 岁"
            npcs.append(row)
        biography = None
        if s["finished"]:
            try:
                from .portrait import build_biography
            except ImportError:
                biography = {"title": f"{s['name']}人物志", "summary": f"这段人生停在 {s['age']} 岁。完整经历保存在年表中。", "chapters": [], "dimensions": []}
            else:
                biography = build_biography(deepcopy({key: value for key, value in s.items() if key != "population"}))
                # Only explicit, witnessed encounters enter this appendix. Hidden
                # NPC traits and private simulation history are never evidence.
                encounters = {}
                for row in s["timeline"]:
                    if row["kind"] == "social" and row.get("action") != "follow":
                        for pid in row.get("population_ids", []):
                            encounters.setdefault(pid, []).append(row)
                for pid, records in sorted(encounters.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:6]:
                    known = population_rules.person_view(s["population"], pid)
                    selected = records[-2:]
                    biography.setdefault("relationships", []).append({"name": known["name"],
                        "text": f"你留下了与{known['name']}有关的 {len(records)} 次主动来往记录。" + " ".join(row["text"] for row in selected),
                        "event_ids": [row["id"] for row in selected]})
        return {"version": VIEW_VERSION, "revision": s["revision"], "name": s["name"], "origin": s["origin"],
                "age": s["age"], "year": s["year"], "stage": stage(s["age"]), "finished": s["finished"],
                "death_reason": s["death_reason"], "stats": deepcopy(s["stats"]), "status": deepcopy(s["status"]),
                "npcs": npcs, "event": public_event, "last_outcome": deepcopy(s["last_outcome"]),
                "timeline": deepcopy(s["timeline"]), "biography": biography,
                "outlook": self._outlook(), "migration_note": s["migration_note"],
                "world": world_rules.world_view(s["world"], self.catalog["world_catalog"]),
                "population": self.people(),
                "progress": 1 if s["finished"] else round(s["slot_index"] / len(AGES), 4)}
