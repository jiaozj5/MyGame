"""Bounded NPC population. Mutations copy touched rows; views expose knowledge only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


VERSION = "0.5.0"
ANCHORS = {"mother", "father", "friend", "partner"}
PLANS = {"balanced": "均衡来往", "family": "维持熟悉关系", "work": "学习与工作往来", "community": "参与邻里", "guarded": "保留个人空间"}
AXES = ("honesty", "empathy", "aggression", "dominance", "cooperativeness", "trust", "caution", "impulsivity", "sociability", "persistence", "openness", "fairness")
STATS = {"cash", "health", "stress", "reputation"}
EDGE_STATS = {"trust", "affinity", "tension"}
KINDS = {"support", "cooperate", "conflict", "deception", "exploitation", "crime", "repair"}
GROUPS = {"known", "direct", "close", "important", "deceased"}
_CACHE = None
_INDEX_CACHE = None


class PopulationError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise PopulationError(message)


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _number(seed, *parts):
    return int(hashlib.sha256((str(seed) + ":" + ":".join(map(str, parts))).encode()).hexdigest()[:13], 16)


def validate_library(library):
    try:
        _require(isinstance(library, dict) and library.get("version") == VERSION, "人物内容库版本不兼容。")
        for group in ("occupations", "identities", "personality_axes", "motivations", "interactions"):
            rows = library[group]
            _require(isinstance(rows, list) and rows, "人物内容库缺少词典或互动。")
            ids = [row["id"] for row in rows]
            _require(all(isinstance(pid, str) and pid for pid in ids) and len(ids) == len(set(ids)), "人物内容编号重复或无效。")
        _require({row["id"] for row in library["personality_axes"]} == set(AXES), "人物性格轴不完整。")
        _require(all(isinstance(library["names"][key], list) and library["names"][key]
                     and all(isinstance(name, str) and name for name in library["names"][key]) for key in ("family", "given")), "人物姓名词典无效。")
        for occupation in library["occupations"]:
            _require(all(isinstance(occupation[key], str) and occupation[key] for key in ("label", "sector", "description")), "职业说明不完整。")
            _require(_int(occupation["min_age"]) and occupation["min_age"] >= 0 and _int(occupation["income"]) and occupation["income"] >= 0, "职业年龄或收入无效。")
        for event in library["interactions"]:
            _require(event["kind"] in KINDS and event["visibility"] in {"private", "participants", "public"}, "人物互动种类或可见性无效。")
            _require(_int(event["weight"]) and event["weight"] > 0 and _int(event["cooldown"]) and event["cooldown"] >= 0, "人物互动权重或冷却无效。")
            _require(_int(event["min_age"]) and event["min_age"] >= 0 and isinstance(event["text"], str) and isinstance(event["title"], str), "人物互动叙述或年龄无效。")
            for condition in event.get("requires", []):
                _require(condition["op"] in {"eq", "ne", "gte", "lte"} and isinstance(condition["path"], str), "人物互动条件无效。")
            for effect in event.get("effects", []):
                op = effect["op"]
                _require(op in {"stat", "relation", "flag", "transfer", "edge_flag"}, "人物互动包含未支持的动作。")
                if op == "stat":
                    _require(effect["who"] in {"actor", "target"} and effect["key"] in STATS and _int(effect["delta"]), "人物属性动作无效。")
                    _require(abs(effect["delta"]) <= (2000 if effect["key"] == "cash" else 30), "人物属性单次变化过大。")
                elif op in {"relation", "edge_flag"}:
                    _require(effect["direction"] in {"actor_target", "target_actor"}, "人物关系方向无效。")
                    if op == "relation":
                        _require(effect["key"] in EDGE_STATS and _int(effect["delta"]) and abs(effect["delta"]) <= 30, "人物关系变化无效。")
                    else:
                        _require(isinstance(effect["key"], str) and isinstance(effect["value"], bool), "案件边标记无效。")
                elif op == "flag":
                    _require(effect["who"] in {"actor", "target"} and isinstance(effect["key"], str) and isinstance(effect["value"], bool), "人物事实标记无效。")
                else:
                    _require(effect["from"] in {"actor", "target"} and effect["to"] in {"actor", "target"}
                             and effect["from"] != effect["to"] and _int(effect["amount"]) and 0 < effect["amount"] <= 2000, "人物转账无效。")
        return library
    except PopulationError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PopulationError("人物内容库字段缺失或格式错误。") from exc


def load_library():
    global _CACHE
    path = Path(__file__).resolve().parents[1] / "content" / "npc-library.json"
    try:
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        if _CACHE is None or _CACHE[0] != stamp:
            _CACHE = (stamp, validate_library(json.loads(path.read_text(encoding="utf-8"))))
        return _CACHE[1]
    except PopulationError:
        raise
    except (OSError, ValueError) as exc:
        raise PopulationError("人物内容库暂时无法读取。") from exc


def _library(library):
    return load_library() if library is None else library


def _indices(library):
    global _INDEX_CACHE
    if _INDEX_CACHE is None or _INDEX_CACHE[0] is not library:
        value = (library, {item["id"]: item for item in library["occupations"]}, {item["id"]: item for item in library["identities"]})
        _INDEX_CACHE = value
        return value[1:]
    return _INDEX_CACHE[1:]


def _row_copy(old):
    row = dict(old)
    for key in ("stats", "flags", "event_years"):
        row[key] = dict(old[key])
    row["knowledge"] = dict(old["knowledge"])
    for key in ("traits", "identities"):
        row["knowledge"][key] = list(old["knowledge"][key])
    row["relations"] = {pid: {**edge, "flags": dict(edge["flags"])} for pid, edge in old["relations"].items()}
    row["history"], row["recent"] = list(old["history"]), list(old["recent"])
    row["identities"] = list(old["identities"])
    return row


def _copy(pop):
    result = dict(pop)
    result["people"] = dict(pop["people"])
    result["tracked"] = list(pop["tracked"])
    result["news"] = list(pop["news"])
    result["counters"] = dict(pop["counters"])
    result["_edited"] = set()
    return result


def _edit(pop, pid):
    if pid not in pop["_edited"]:
        old = pop["people"][pid]
        row = _row_copy(old)
        pop["people"][pid] = row
        pop["_edited"].add(pid)
    return pop["people"][pid]


def _done(pop):
    pop.pop("_edited", None)
    return pop


def _age(pop, person):
    end = person["death_year"] if person["status"] == "dead" else pop["year"]
    return end - person["birth_year"]


def _limit(age):
    return 3 if age < 12 else 4 if age < 18 or age >= 65 else 6


def _occupation(library, age, seed, pid, year, current=None):
    catalog = _indices(library)[0]
    desired = "child_early" if age < 6 else "student" if age < 18 else "retired" if age >= 65 else None
    if desired in catalog:
        return desired
    if (current in catalog and current not in {"child_early", "student", "retired"}
            and catalog[current]["min_age"] <= age <= catalog[current].get("max_age", 120)
            and _number(seed, pid, year, "career") % 100 >= 4):
        return current
    candidates = [row for row in catalog.values() if row["min_age"] <= age <= row.get("max_age", 120)
                  and row["id"] not in {"child_early", "student", "retired", "recovering"}]
    _require(bool(candidates), "人物内容库没有适合这个年龄的职业。")
    return candidates[_number(seed, pid, year, "occupation") % len(candidates)]["id"]


def _record(pop, ids, code, title, text, visibility="public", known=False, source="地方公开记录", confidence="recorded", **extra):
    pop["sequence"] += 1
    entry = {"id": f"population-{pop['sequence']}", "year": pop["year"], "code": code, "title": title,
             "text": text, "visibility": visibility, "known": known, "source": source, "confidence": confidence, **extra}
    if code == "annual":
        subject = pop["people"][ids[0]]
        entry = {"id": entry["id"], "year": entry["year"], "code": code, "visibility": visibility, "known": known,
                 "occupation": subject["occupation"], "location": subject["location"],
                 "resources": [subject["stats"][key] for key in ("cash", "health", "stress", "reputation")]}
    for pid in ids:
        row = _edit(pop, pid)
        if row["detailed"] or pid in pop["tracked"]:
            row["history"].append(entry)
        else:
            row["recent"] = (row["recent"] + [entry])[-6:]
    personal_log = {"annual", "shared_time", "meet", "introduction", "focus", "player_social", "close_milestone"}
    if code not in personal_log and (visibility == "public" or known) and any(pop["people"][pid]["knowledge"]["contact"] != "none" for pid in ids):
        pop["news"] = (pop["news"] + [{key: entry[key] for key in ("id", "year", "title", "text", "visibility", "source")}])[-120:]
    return entry


def _track(pop, pid):
    if pid in pop["tracked"]:
        return
    if len(pop["tracked"]) >= pop["focus_limit"]:
        removable = [item for item in pop["tracked"] if item not in ANCHORS]
        if not removable:
            return
        drop = min(removable, key=lambda item: (pop["people"][item]["knowledge"]["closeness"], pop["people"][item]["last_social_year"], item))
        pop["tracked"].remove(drop)
    pop["tracked"].append(pid)
    row = _edit(pop, pid)
    # Only surviving actual records move into the retained timeline.
    row["history"] += row["recent"]
    row["recent"] = []


def _discover(pop, pid, contact, source):
    row = _edit(pop, pid)
    if row["status"] != "alive":
        return False
    knowledge = row["knowledge"]
    old = knowledge["contact"]
    if old == "none" or old == "indirect" and contact == "direct":
        knowledge.update(contact=contact, source=source)
        if contact == "direct":
            knowledge["met_year"] = pop["year"]
            knowledge["closeness"] = max(knowledge["closeness"], 12)
            _track(pop, pid)
        _record(pop, [pid], "meet" if contact == "direct" else "introduction", "一次相识" if contact == "direct" else "听到一个名字",
                f"你与{row['name']}实际见了面。" if contact == "direct" else f"通过{source}，你第一次了解到{row['name']}这个人。",
                "participants", True, source)
        return True
    return False


def _edge(pop, source, target):
    row = _edit(pop, source)
    if target not in row["relations"]:
        if len(row["relations"]) >= 6:
            removable = [pid for pid, edge in row["relations"].items() if not _pending(edge)]
            if not removable:
                return None
            del row["relations"][min(removable, key=lambda pid: (row["relations"][pid]["affinity"], row["relations"][pid]["last_year"]))]
        row["relations"][target] = {"trust": 40, "affinity": 35, "tension": 10, "flags": {}, "last_event": None,
                                      "last_year": pop["year"], "known": False, "known_label": "认识的人"}
    return row["relations"][target]


def _pending(edge):
    return any(value and (key.endswith("pending") or key == "entrusted_fund") for key, value in edge["flags"].items())


def new_population(seed, year, anchors, library=None, size=2000, focus_limit=200):
    library = validate_library(_library(library))
    _require(_int(seed) and _int(year) and _int(size) and 4 <= size <= 2000 and _int(focus_limit) and 4 <= focus_limit <= 200, "人口容量、年份或种子无效。")
    _require(set(anchors) == ANCHORS, "人口镜像缺少四位现有人物。")
    birth = anchors["friend"]["birth_year"]
    pop = {"version": VERSION, "library_version": library["version"], "source_seed": seed, "seed": _number(seed, "population-v05"),
           "year": year, "start_year": year, "player_birth_year": birth, "capacity": size, "focus_limit": min(size, focus_limit),
           "people": {}, "tracked": [], "plan": "balanced", "actions_used": 0, "action_counter": 0, "sequence": 0,
           "news": [], "counters": {"births": 0, "deaths": 0, "interactions": 0, "crimes": 0, "consequences": 0}, "_edited": set()}
    motivations = [row["id"] for row in library["motivations"]]
    for index, pid in enumerate(["mother", "father", "friend", "partner"] + [f"npc-{i:04d}" for i in range(1, size - 3)]):
        is_anchor = pid in ANCHORS
        roll = _number(pop["seed"], pid, "identity")
        if is_anchor:
            born, name = anchors[pid]["birth_year"], anchors[pid]["name"]
        else:
            cohort = index % 3
            epoch = year - 6
            born = epoch - 18 - roll % 48 if cohort == 0 else epoch - 8 + roll % 25 if cohort == 1 else epoch + 18 + roll % 43
            name = library["names"]["family"][roll % len(library["names"]["family"])]+library["names"]["given"][(roll // 100) % len(library["names"]["given"])]
        age = year - born
        status = "unborn" if age < 0 else "alive"
        occupation = _occupation(library, max(0, age), pop["seed"], pid, year)
        trait_digest = hashlib.sha256(f"traits:{pop['seed']}:{pid}".encode()).hexdigest()
        traits = {axis: int(trait_digest[i * 4:i * 4 + 4], 16) % 101 for i, axis in enumerate(AXES)}
        row = {"id": pid, "anchor": is_anchor, "name": name, "birth_year": born, "death_year": None, "status": status,
               "occupation": occupation, "location": ["青溪镇中心", "河岸街区", "北侧街区", "镇郊村落"][roll % 4],
               "stats": {"cash": 0 if age < 18 else 3000 + roll % 32000, "health": 88, "stress": 15 + roll % 25, "reputation": 50},
               "education": min(80, max(0, age - 6) * 4), "traits": traits, "motivation": motivations[roll % len(motivations)],
               "identities": [], "flags": {}, "detained_until": None, "relations": {}, "event_years": {},
               "knowledge": {"contact": "none", "closeness": 0, "met_year": None, "source": "", "traits": [], "motivation": None, "identities": [], "ever_close": False, "first_close_year": None, "detained": False},
               "detailed": index < min(200, size), "history": [], "recent": [], "last_social_year": year,
               "portrait_seed": _number(pop["seed"], pid, "portrait"), "birth_recorded": False, "death_recorded": False}
        groups = set()
        for identity in library["identities"]:
            group = identity.get("exclusive_group")
            if (identity["min_age"] <= age and group != "resources" and identity["id"] != "retired_worker" and (not group or group not in groups)
                    and _number(pop["seed"], pid, identity["id"]) % 9 == 0):
                row["identities"].append(identity["id"])
                if group:
                    groups.add(group)
        pop["people"][pid] = row
        pop["_edited"].add(pid)
        _refresh_identities(pop, row, library)
        if status == "alive" and not is_anchor:
            _record(pop, [pid], "baseline", "从这一年开始记录", f"{name}已在此生活；此前的具体经历未被本次模拟记录。")
    _sync_into(pop, anchors)
    age = year - birth
    nearby = [p for p in pop["people"].values() if not p["anchor"] and p["status"] == "alive" and abs(_age(pop, p) - age) <= 3]
    if len(nearby) < 9:
        nearby = sorted((p for p in pop["people"].values() if not p["anchor"] and p["status"] == "alive"), key=lambda p: abs(_age(pop, p) - age))[:30]
    nearby.sort(key=lambda p: _number(pop["seed"], p["id"], "initial-contact"))
    for person in nearby[:5]:
        _discover(pop, person["id"], "direct", "最初的邻里与学校往来")
    for person in nearby[5:9]:
        _discover(pop, person["id"], "indirect", "邻里介绍")
    return _done(pop)


def _sync_into(pop, anchors):
    library = load_library()
    for pid in sorted(ANCHORS):
        authority = anchors[pid]
        row = _edit(pop, pid)
        old_status = row["status"]
        was_known = row["knowledge"]["contact"] != "none"
        row.update(name=authority["name"], birth_year=authority["birth_year"], death_year=authority.get("death_year"),
                   status="alive" if authority["alive"] else "dead", role=authority["role"])
        row["stats"]["cash"] = authority["cash"]
        age = (row["death_year"] if row["status"] == "dead" else pop["year"]) - row["birth_year"]
        if old_status != "dead":
            row["occupation"] = _occupation(library, age, pop["seed"], pid, pop["year"], row["occupation"])
        row["knowledge"].update(contact="direct" if authority["met"] else "none", closeness=authority["closeness"] if authority["met"] else 0,
                                met_year=row["knowledge"]["met_year"] or (pop["year"] if authority["met"] else None), source="你已有的人生关系")
        if authority["met"] and not was_known:
            _track(pop, pid)
        if old_status != "dead":
            _refresh_identities(pop, row, library)
        if authority["met"] and authority["closeness"] >= 60 and not row["knowledge"]["ever_close"]:
            row["knowledge"].update(ever_close=True, first_close_year=pop["year"])
        if old_status != "dead" and not authority["alive"]:
            row["death_recorded"] = True
            _record(pop, [pid], "death", "收到告别的消息", f"{row['name']}已经去世。这条记录同步自你的人生事实。", known=authority["met"])


def sync_anchors(population, anchors, year):
    _require(year == population["year"], "人物镜像与人口年份不一致。")
    result = _copy(population)
    _sync_into(result, anchors)
    return _done(result)


def set_plan(population, plan):
    _require(plan in PLANS, "请选择已有的社交安排。")
    result = dict(population)
    result["plan"] = plan
    return result


def _mark_dead(pop, pid, reason):
    row = _edit(pop, pid)
    if row["status"] != "alive" or row["anchor"]:
        return
    row.update(status="dead", death_year=pop["year"], death_recorded=True, detained_until=None)
    row["flags"]["detained"] = False
    pop["counters"]["deaths"] += 1
    _record(pop, [pid], "death", "一段人生结束", f"{row['name']}于这一年去世，享年{_age(pop, row)}岁。{reason}")


def _refresh_identities(pop, row, library):
    definitions = _indices(library)[1]
    row["identities"] = [key for key in row["identities"] if definitions[key].get("exclusive_group") != "resources" and key != "retired_worker"
                          and not (pop["year"] - pop["start_year"] > 4 and key in {"newcomer", "recently_bereaved", "career_changer"})]
    if row["occupation"] == "retired" and "retired_worker" in definitions:
        row["identities"].append("retired_worker")
    resource = "financially_secure" if row["stats"]["cash"] >= 50000 else "low_income" if row["stats"]["cash"] < 4000 else None
    if resource in definitions and _age(pop, row) >= definitions[resource]["min_age"]:
        row["identities"].append(resource)
    # Previously disclosed labels follow current objectively derived identities.
    row["knowledge"]["identities"] = [key for key in row["knowledge"]["identities"] if key in row["identities"]]


def _close_milestone(pop, row):
    knowledge = row["knowledge"]
    if knowledge["contact"] == "direct" and knowledge["closeness"] >= 60 and not knowledge["ever_close"]:
        knowledge.update(ever_close=True, first_close_year=pop["year"])
        _record(pop, [row["id"]], "close_milestone", "来往逐渐深入", f"经过已经记录的多次实际来往，你与{row['name']}形成了较密切的关系。", "participants", True, "你亲自参与")


def _path(actor, target, edge, world_metrics, path, library):
    bits = path.split(".")
    if bits[:2] == ["world", "metrics"]:
        return world_metrics.get(bits[2], 50)
    if bits[0] == "edge":
        if bits[1] == "flags":
            return edge.get("flags", {}).get(bits[2], False)
        return edge.get(bits[1], 0)
    row = actor if bits[0] == "actor" else target
    if bits[1] == "sector":
        return _indices(library)[0][row["occupation"]]["sector"]
    if len(bits) == 2:
        return row.get(bits[1])
    return row.get(bits[1], {}).get(bits[2], False if bits[1] == "flags" else None)


def _eligible_interaction(pop, actor_id, target_id, event, metrics, library):
    actor, target = pop["people"][actor_id], pop["people"][target_id]
    if actor_id == target_id or actor["anchor"] or target["anchor"] or actor["status"] != "alive" or target["status"] != "alive":
        return False
    minimum = max(event["min_age"], 18 if event["kind"] in {"crime", "deception", "exploitation"} else 0)
    if min(_age(pop, actor), _age(pop, target)) < minimum:
        return False
    followup = "case_followup" in event.get("tags", [])
    if not followup and any(row["flags"].get("detained") or row["flags"].get("moved_away") for row in (actor, target)):
        return False
    edge = actor["relations"].get(target_id, {"trust": 40, "affinity": 35, "tension": 10, "flags": {}})
    last = actor["event_years"].get(event["id"])
    if last is not None and pop["year"] - last < event["cooldown"]:
        return False
    for condition in event.get("requires", []):
        actual = _path(actor, target, edge, metrics, condition["path"], library)
        expected, op = condition["value"], condition["op"]
        same = type(actual) is type(expected) and actual == expected
        if not (same if op == "eq" else not same if op == "ne" else _int(actual) and _int(expected) and (actual >= expected if op == "gte" else actual <= expected)):
            return False
    return True


def _apply_interaction(pop, actor_id, target_id, event, metrics, library):
    if not _eligible_interaction(pop, actor_id, target_id, event, metrics, library):
        return False
    # Simulate both sides first. A later unmet cash cost cannot partially settle.
    proposed = {"actor": _row_copy(pop["people"][actor_id]), "target": _row_copy(pop["people"][target_id])}
    ids = {"actor": actor_id, "target": target_id}
    pending_new = False
    for effect in event.get("effects", []):
        op = effect["op"]
        if op == "stat":
            stats, key = proposed[effect["who"]]["stats"], effect["key"]
            value = stats[key] + effect["delta"]
            if key == "cash" and value < 0:
                return False
            stats[key] = value if key == "cash" else _clamp(value)
        elif op == "transfer":
            giver, taker, amount = proposed[effect["from"]], proposed[effect["to"]], effect["amount"]
            if giver["stats"]["cash"] < amount:
                return False
            giver["stats"]["cash"] -= amount
            taker["stats"]["cash"] += amount
        elif op == "flag":
            row = proposed[effect["who"]]
            row["flags"][effect["key"]] = effect["value"]
            if effect["key"] == "detained":
                row["detained_until"] = pop["year"] + 2 if effect["value"] else None
        else:
            src, dest = ("actor", "target") if effect["direction"] == "actor_target" else ("target", "actor")
            row = proposed[src]
            other = ids[dest]
            if other not in row["relations"]:
                if len(row["relations"]) >= 6:
                    removable = [pid for pid, edge in row["relations"].items() if not _pending(edge)]
                    if not removable:
                        return False
                    del row["relations"][min(removable, key=lambda pid: row["relations"][pid]["affinity"])]
                row["relations"][other] = {"trust": 40, "affinity": 35, "tension": 10, "flags": {}, "last_event": None,
                                             "last_year": pop["year"], "known": False, "known_label": "认识的人"}
            edge = row["relations"][other]
            if op == "relation":
                edge[effect["key"]] = _clamp(edge[effect["key"]] + effect["delta"])
            else:
                edge["flags"][effect["key"]] = effect["value"]
                if effect["key"].endswith("pending") and effect["value"]:
                    edge["incident_year"] = pop["year"]
                    pending_new = True
            edge.update(last_event=event["id"], last_year=pop["year"])
    for role, row in proposed.items():
        pop["people"][ids[role]] = row
        pop["_edited"].add(ids[role])
    actor, target = proposed["actor"], proposed["target"]
    actor["event_years"][event["id"]] = pop["year"]
    text = event["text"].replace("{actor}", actor["name"]).replace("{target}", target["name"])
    visibility = event["visibility"]
    if visibility == "public":
        for row in (actor, target):
            row["knowledge"]["detained"] = bool(row["flags"].get("detained"))
    if visibility == "public" and any(row["knowledge"]["contact"] != "none" for row in (actor, target)):
        for row in (actor, target):
            if row["knowledge"]["contact"] == "none":
                _discover(pop, row["id"], "indirect", "共同事件的公开记录")
        for src, dest in ((actor_id, target_id), (target_id, actor_id)):
            edge = _edge(pop, src, dest)
            if edge is not None:
                edge.update(known=True, known_label="有过共同事件")
    _record(pop, [actor_id, target_id], "interaction", event["title"], text, visibility,
            source="共同事件的公开记录" if visibility == "public" else "当事人的私下经历",
            event_id=event["id"], actor=actor_id, target=target_id, kind=event["kind"])
    pop["counters"]["interactions"] += 1
    pop["counters"]["crimes"] += int(event["kind"] == "crime")
    pop["counters"]["consequences"] += int("case_followup" in event.get("tags", []))
    if pending_new:
        actor["flags"]["has_unresolved_incident"] = True
    for pid in (actor_id, target_id):
        if pop["people"][pid]["stats"]["health"] == 0:
            _mark_dead(pop, pid, "此前的健康负担未能恢复。")
    return True


def _simulate_year(pop, metrics, library):
    jobs = {item["id"]: item for item in library["occupations"]}
    for pid, original in list(pop["people"].items()):
        if original["anchor"] or original["status"] == "dead":
            continue
        age = pop["year"] - original["birth_year"]
        if age < 0:
            continue
        row = _edit(pop, pid)
        if row["status"] == "unborn":
            row.update(status="alive", birth_recorded=True)
            pop["counters"]["births"] += 1
            _record(pop, [pid], "birth", "一个新生命", f"{row['name']}在这一年出生。")
        if row["flags"].get("detained") and row["detained_until"] is not None and pop["year"] >= row["detained_until"]:
            row["flags"]["detained"] = False
            row["knowledge"]["detained"] = False
            row["detained_until"] = None
            pop["counters"]["consequences"] += 1
            _record(pop, [pid], "release", "限制结束后的生活", f"{row['name']}的临时行动限制已经结束；相关经历仍保留在记录中。")
        roll = _number(pop["seed"], pid, pop["year"], "annual")
        occupation = _occupation(library, age, pop["seed"], pid, pop["year"], row["occupation"])
        if occupation != row["occupation"]:
            row["occupation"] = occupation
            _record(pop, [pid], "career", "生活方向发生变化", f"{row['name']}这一年的身份转为{jobs[occupation]['label']}。")
        if 6 <= age <= 22 and occupation == "student":
            row["education"] = _clamp(row["education"] + 4)
        if age >= 18:
            income = jobs[occupation]["income"] * (90 + metrics.get("prosperity", 50) // 5) // 100
            income = 0 if row["flags"].get("detained") else income
            expenses = 8000 + metrics.get("cost_pressure", 50) * 60
            row["stats"]["cash"] = max(0, row["stats"]["cash"] + income - expenses)
            hardship = row["stats"]["cash"] == 0 and income < expenses
            row["stats"]["stress"] = _clamp(row["stats"]["stress"] + (3 if hardship else -1))
            row["stats"]["health"] = max(0, row["stats"]["health"] - int(age >= 68) - int(age >= 82) - int(hardship and age >= 55))
        if age >= 100 or row["stats"]["health"] <= 0 or age >= 65 and roll % 10000 < (40 if age < 75 else 160 if age < 85 else 700):
            _mark_dead(pop, pid, "人生在这一年告一段落。")
            continue
        if age >= 18 and roll // 10000 % 100 < 2 and not row["flags"].get("detained"):
            away = not row["flags"].get("moved_away", False)
            row["flags"]["moved_away"] = away
            row["location"] = "外地" if away else "青溪镇中心"
            _record(pop, [pid], "move", "生活地点改变", f"{row['name']}搬到了{row['location']}。后续来往需要按照实际距离安排。")
        if row["detailed"] or pid in pop["tracked"]:
            _record(pop, [pid], "annual", "这一年的近况", f"{row['name']}这一年以{jobs[occupation]['label']}的身份生活，居住在{row['location']}。",
                    "private", source="本次模拟的年度状态记录")
        if row["knowledge"]["contact"] == "direct" and pop["year"] - row["last_social_year"] > 2:
            row["knowledge"]["closeness"] = max(5, row["knowledge"]["closeness"] - 1)
        _refresh_identities(pop, row, library)
    _resolve_interactions(pop, metrics, library)


def _resolve_interactions(pop, metrics, library):
    events = library["interactions"]
    # Pending cases retain orientation and are revisited without inventing another victim.
    pending = [(pid, target) for pid, row in pop["people"].items() for target, edge in row["relations"].items() if _pending(edge)]
    for actor_id, target_id in pending:
        actor, target = pop["people"][actor_id], pop["people"][target_id]
        if actor["status"] == "dead" or target["status"] == "dead":
            edge = _edge(pop, actor_id, target_id)
            for key in edge["flags"]:
                if key.endswith("pending") or key == "entrusted_fund":
                    edge["flags"][key] = False
            edge["closed_reason"] = "当事人死亡，未完成的处理不能继续当面进行"
            pop["counters"]["consequences"] += 1
            _record(pop, [actor_id, target_id], "case_closed", "未完成事务留下记录", "当事人的死亡终止了这段需要其主动参与的处理；这不等于欠款已还或争议已获判定。", "private")
            continue
        candidates = [e for e in events if "case_followup" in e.get("tags", []) and _eligible_interaction(pop, actor_id, target_id, e, metrics, library)]
        if candidates:
            chosen = sorted(candidates, key=lambda e: e["id"])[_number(pop["seed"], actor_id, target_id, pop["year"], "case") % len(candidates)]
            _apply_interaction(pop, actor_id, target_id, chosen, metrics, library)
    living = [pid for pid, row in pop["people"].items() if not row["anchor"] and row["status"] == "alive" and _age(pop, row) >= 6]
    if len(living) < 2:
        return
    for index in range(min(36, len(living))):
        roll = _number(pop["seed"], pop["year"], index, "pair")
        actor_id = living[roll % len(living)]
        edges = [pid for pid in pop["people"][actor_id]["relations"] if pop["people"][pid]["status"] == "alive"]
        target_id = edges[(roll // 100) % len(edges)] if edges and roll % 3 else living[(roll // 1000) % len(living)]
        candidates = [e for e in events if "case_followup" not in e.get("tags", []) and _eligible_interaction(pop, actor_id, target_id, e, metrics, library)]
        if candidates:
            weight = sum(e["weight"] for e in candidates)
            draw = _number(pop["seed"], pop["year"], index, "interaction") % weight
            for selected in candidates:
                draw -= selected["weight"]
                if draw < 0:
                    break
            _apply_interaction(pop, actor_id, target_id, selected, metrics, library)


def _social_year(pop, plan):
    age = pop["year"] - pop["player_birth_year"]
    eligible = [p for p in pop["people"].values() if not p["anchor"] and p["status"] == "alive" and not p["flags"].get("detained")
                and not p["flags"].get("moved_away") and (abs(_age(pop, p) - age) <= 5 if age < 18 else _age(pop, p) >= 18)]
    known = [p for p in eligible if p["knowledge"]["contact"] == "direct"]
    unknown = [p for p in eligible if p["knowledge"]["contact"] != "direct"]
    # Stable cores grow through repeated contact; mature ties rotate out rather than monopolizing every year.
    known.sort(key=lambda p: (p["knowledge"]["ever_close"], -p["knowledge"]["closeness"], _number(pop["seed"], p["id"], pop["year"] // 4, plan)))
    unknown.sort(key=lambda p: _number(pop["seed"], p["id"], pop["year"], plan))
    core_count, new_count, frequency = {"balanced": (20, 16, 18), "family": (24, 4, 24), "work": (18, 24, 18), "community": (18, 32, 18), "guarded": (5, 2, 8)}[plan]
    if age < 18:
        core_count, new_count = min(core_count, 12), min(new_count, 8)
    selected = [(person, frequency) for person in known[:core_count]] + [(person, 2) for person in unknown[:new_count]]
    for person, meetings in selected:
        pid = person["id"]
        _discover(pop, pid, "direct", "实际参加的学校或邻里活动" if age < 18 else PLANS[plan])
        row = _edit(pop, pid)
        row["knowledge"]["closeness"] = min(85, row["knowledge"]["closeness"] + max(1, meetings // 2))
        row["last_social_year"] = pop["year"]
        _record(pop, [pid], "shared_time", "实际一起度过的时间", f"按照这一年的来往安排，你与{row['name']}共同参与了{meetings}次学习、工作交流或邻里活动。这些活动可多人同时参与。", "participants", True, "你亲自参与", frequency=meetings, plan=plan)
        _close_milestone(pop, row)
        referrals = [other for other in row["relations"] if pop["people"][other]["status"] == "alive" and pop["people"][other]["knowledge"]["contact"] == "none"]
        for other in referrals[:1]:
            _discover(pop, other, "indirect", f"{row['name']}的介绍")
            row["relations"][other].update(known=True, known_label="向你介绍过的联系人")


def advance_population(population, year, anchors, world_metrics=None, plan="balanced", library=None):
    library = _library(library)
    _require(_int(year) and year >= population["year"] and plan in PLANS, "人口时间或社交安排无效。")
    result = _copy(population)
    result["plan"] = plan
    metrics = world_metrics or {}
    while result["year"] < year:
        result["year"] += 1
        result["actions_used"] = 0
        _simulate_year(result, metrics, library)
        _social_year(result, plan)
        # Even batched advancement observes each age boundary. A known death date
        # takes effect at that year; it never makes the person dead beforehand.
        current_anchors = {}
        for pid, authority in anchors.items():
            current = dict(authority)
            if current.get("death_year") is not None and current["death_year"] > result["year"]:
                current.update(alive=True, death_year=None, death_age=None)
            current_anchors[pid] = current
        _sync_into(result, current_anchors)
    if population["year"] == year:
        _sync_into(result, anchors)
    return _done(result)


def _public_row(pop, row, library):
    job = next(item for item in library["occupations"] if item["id"] == row["occupation"])
    state = "dead" if row["status"] == "dead" else "detained" if row["knowledge"].get("detained") else "away" if row["location"] == "外地" else "alive"
    return {"id": row["id"], "name": row["name"], "age": _age(pop, row), "role": row.get("role", "相识的人"),
            "occupation": job["label"], "sector": job["sector"], "location": row["location"], "status": state,
            "closeness": row["knowledge"]["closeness"], "contact": row["knowledge"]["contact"],
            "important": row["id"] in pop["tracked"], "portrait_seed": row["portrait_seed"]}


def population_view(population, query="", group="known", offset=0, limit=24):
    library = load_library()
    _require(isinstance(query, str) and group in GROUPS and _int(offset) and offset >= 0 and _int(limit) and 1 <= limit <= 100, "人物查询条件无效。")
    known = [p for p in population["people"].values() if p["status"] != "unborn" and p["knowledge"]["contact"] != "none"]
    direct = [p for p in known if p["knowledge"]["contact"] == "direct"]
    close = [p for p in direct if p["status"] == "alive" and p["knowledge"]["closeness"] >= 60]
    rows = known if group == "known" else direct if group == "direct" else close if group == "close" else [p for p in known if p["id"] in population["tracked"]] if group == "important" else [p for p in known if p["status"] == "dead"]
    occupation_labels = {item["id"]: item["label"] for item in library["occupations"]}
    identity_labels = {item["id"]: item["label"] for item in library["identities"]}
    rows = [p for p in rows if query.casefold() in " ".join([p["name"], occupation_labels[p["occupation"]]]
            + [identity_labels[key] for key in p["knowledge"]["identities"] if key in identity_labels]).casefold()]
    rows.sort(key=lambda p: (p["status"] == "dead", -p["knowledge"]["closeness"], p["id"]))
    return {"year": population["year"], "capacity": population["capacity"], "focus_limit": population["focus_limit"],
            "known_count": len(known), "direct_count": len(direct), "close_count": len(close), "tracked_count": len(population["tracked"]),
            "close_ever_count": sum(p["knowledge"]["ever_close"] for p in known),
            "actions_used": population["actions_used"], "actions_limit": _limit(population["year"] - population["player_birth_year"]),
            "plan": population["plan"], "total": len(rows), "offset": offset, "limit": limit,
            "people": [_public_row(population, p, library) for p in rows[offset:offset + limit]], "news": deepcopy(population["news"][-30:]),
            "retention_note": "200个预置详细人物保留实际模拟记录；关注名单另有200人容量。外围只保留最近6条，后续关注不会补写遗失过去。相识计数包括已知亡者。"}


def _known_person(pop, pid):
    _require(pid in pop["people"] and pop["people"][pid]["status"] != "unborn"
             and pop["people"][pid]["knowledge"]["contact"] != "none", "你目前还不了解这个人。")
    return pop["people"][pid]


def person_view(population, npc_id):
    library = load_library()
    row = _known_person(population, npc_id)
    result = _public_row(population, row, library)
    job = next(item for item in library["occupations"] if item["id"] == row["occupation"])
    identities = {item["id"]: item["label"] for item in library["identities"]}
    records = {entry["id"]: entry for entry in row["history"] + row["recent"] if entry["visibility"] == "public" or entry["known"]}
    for eid, entry in list(records.items()):
        if entry["code"] == "annual" and "title" not in entry:
            old_job = _indices(library)[0][entry["occupation"]]["label"]
            records[eid] = {**entry, "title": "这一年的近况", "text": f"{row['name']}这一年以{old_job}的身份生活，居住在{entry['location']}。",
                            "source": "本次模拟的年度状态记录", "confidence": "recorded"}
    result.update(description=job["description"], identities=[identities[key] for key in row["knowledge"]["identities"] if key in identities],
                  known_traits=list(row["knowledge"]["traits"]), motivation=row["knowledge"]["motivation"],
                  timeline=[{key: record[key] for key in ("id", "year", "title", "text", "source", "confidence")}
                            for record in sorted(records.values(), key=lambda item: (item["year"], int(item["id"].rsplit("-", 1)[-1]) if item["id"].rsplit("-", 1)[-1].isdigit() else 0))],
                  relations=[{"id": pid, "name": population["people"][pid]["name"], "label": edge["known_label"]}
                             for pid, edge in row["relations"].items() if edge["known"] and population["people"][pid]["knowledge"]["contact"] != "none"])
    return result


def interaction_options(population, npc_id, player_age, player_stats):
    row = _known_person(population, npc_id)
    choices = [("meet", "正式认识", "通过已有介绍当面结识。", 0, 6),
               ("talk", "交谈与联系", "花时间了解近况并维持实际来往。", 0, 4),
               ("help", "提供一些实际帮助", "以一小笔生活帮助支持对方，需要双方成年。", 80, 6),
               ("boundary", "说明自己的界限", "在交往中明确自己能承担什么。", 0, 3),
               ("follow", "取消关注" if npc_id in population["tracked"] else "加入关注", "关注便于留存后续记录，不等同亲密关系。", 0, 1)]
    output = []
    for aid, label, description, cash, energy in choices:
        reason = None
        if row["anchor"] and aid != "follow":
            reason = "这段关系由人生事件推进。"
        elif aid != "follow" and row["status"] != "alive":
            reason = "对方已经去世，不能继续主动来往。"
        elif aid != "follow" and row["flags"].get("detained"):
            reason = "对方正在受到临时行动限制，暂时无法安排这次来往。" if row["knowledge"].get("detained") else "目前联系不到对方，暂时无法安排这次来往。"
        elif aid != "follow" and row["location"] == "外地":
            reason = "对方目前在外地，无法完成这次当面安排。"
        elif aid == "meet" and row["knowledge"]["contact"] != "indirect":
            reason = "你们已经直接相识。"
        elif aid in {"talk", "help", "boundary"} and row["knowledge"]["contact"] != "direct":
            reason = "先通过介绍正式相识，再安排这类来往。"
        elif aid == "help" and min(player_age, _age(population, row)) < 18:
            reason = "这项金钱帮助需要双方成年。"
        elif population["actions_used"] >= _limit(player_age):
            reason = "这一年的主动社交安排已经用完。"
        elif player_stats.get("cash", 0) < cash or player_stats.get("energy", 0) < energy:
            reason = "当前现金或精力不足。"
        output.append({"id": aid, "label": label, "description": description, "costs": {"cash": cash, "energy": energy},
                       "available": reason is None, "locked_reason": reason})
    return output


def interact(population, npc_id, action, player_age, player_stats, library=None):
    library = _library(library)
    choices = interaction_options(population, npc_id, player_age, player_stats)
    choice = next((item for item in choices if item["id"] == action), None)
    _require(choice is not None, "找不到这项社交安排。")
    _require(choice["available"], choice["locked_reason"])
    result = _copy(population)
    person = _edit(result, npc_id)
    knowledge = person["knowledge"]
    if action == "follow":
        if npc_id in result["tracked"]:
            result["tracked"].remove(npc_id)
            text = f"你取消了对{person['name']}后续记录的重点关注；过去的真实经历仍然保留。"
        else:
            _track(result, npc_id)
            text = f"你开始关注{person['name']}此后的经历。此前没有留下的记录不会被补写。"
    elif action == "meet":
        _discover(result, npc_id, "direct", "你主动安排的见面")
        text = f"你与{person['name']}通过已有介绍正式见面，开始直接来往。"
    elif action == "talk":
        knowledge["closeness"] = min(100, knowledge["closeness"] + 5)
        text = f"你与{person['name']}通过通信交换了近况。" if person["location"] == "外地" else f"你与{person['name']}花了一些时间交谈，彼此多了解了一点。"
        knowledge["identities"] = list(person["identities"])
        if len(knowledge["traits"]) < 3:
            observation = "这次交谈中，对方愿意分享近况。" if person["traits"]["sociability"] >= 50 else "这次交谈中，对方保留了较多私人细节。"
            if observation not in knowledge["traits"]:
                knowledge["traits"].append(observation)
        if person["traits"]["trust"] >= 60 and knowledge["closeness"] >= 30:
            motive = next(item for item in library["motivations"] if item["id"] == person["motivation"])
            knowledge["motivation"] = f"据本人这次谈话，近期在意的是{motive['label']}。"
    elif action == "help":
        person["stats"]["cash"] += choice["costs"]["cash"]
        knowledge["closeness"] = min(100, knowledge["closeness"] + 6)
        text = f"你向{person['name']}提供了80元实际帮助，对方收到了这笔钱。"
    else:
        knowledge["closeness"] = max(0, knowledge["closeness"] - 1)
        text = f"你向{person['name']}说明了自己的界限，把之后的来往安排说得更清楚。"
    person["last_social_year"] = result["year"]
    if action != "follow":
        _close_milestone(result, person)
    result["actions_used"] += 1
    result["action_counter"] += 1
    entry = _record(result, [npc_id], "focus" if action == "follow" else "player_social", choice["label"], text, "participants", True, "你亲自参与", action=action)
    return _done(result), {"npc_id": npc_id, "title": choice["label"], "text": text, "changes": ["精力 -" + str(choice["costs"]["energy"])] + (["现金 -80"] if action == "help" else []),
                            "costs": dict(choice["costs"]), "stat_deltas": {"stress": -2} if action in {"talk", "boundary"} else {}, "records": [deepcopy(entry)]}


def validate_population(population, anchors=None, expected_year=None, full=False, library=None):
    try:
        pop = population
        _require(pop["version"] == VERSION and pop["library_version"] == VERSION, "人口存档版本不兼容。")
        _require(_int(pop["source_seed"]) and pop["seed"] == _number(pop["source_seed"], "population-v05") and pop["seed"] <= 2**53 - 1, "人口随机种子无效。")
        _require(_int(pop["year"]) and _int(pop["start_year"]) and pop["year"] >= pop["start_year"] and (expected_year is None or pop["year"] == expected_year), "人口年份与人生不一致。")
        _require(pop["player_birth_year"] == pop["people"]["friend"]["birth_year"], "人口社会阶段与玩家出生年份不一致。")
        _require(_int(pop["capacity"]) and 4 <= pop["capacity"] <= 2000 and len(pop["people"]) == pop["capacity"] and ANCHORS <= set(pop["people"]), "人口池身份或容量不完整。")
        _require(_int(pop["focus_limit"]) and 4 <= pop["focus_limit"] <= 200 and len(pop["tracked"]) <= pop["focus_limit"] and len(set(pop["tracked"])) == len(pop["tracked"]), "人物关注容量无效。")
        _require(pop["plan"] in PLANS and _int(pop["actions_used"]) and 0 <= pop["actions_used"] <= _limit(pop["year"] - pop["player_birth_year"]), "主动社交次数或计划无效。")
        _require(_int(pop["sequence"]) and pop["sequence"] >= 0 and _int(pop["action_counter"]) and pop["action_counter"] >= 0, "人物记录序号无效。")
        if anchors is not None:
            for pid in ANCHORS:
                row, anchor = pop["people"][pid], anchors[pid]
                _require(row["anchor"] and row["name"] == anchor["name"] and row["birth_year"] == anchor["birth_year"]
                         and row["status"] == ("alive" if anchor["alive"] else "dead") and row["death_year"] == anchor.get("death_year")
                         and row["stats"]["cash"] == anchor["cash"] and row["knowledge"]["contact"] == ("direct" if anchor["met"] else "none")
                         and row["knowledge"]["closeness"] == (anchor["closeness"] if anchor["met"] else 0), "四位既有人物的镜像与人生事实不一致。")
        if not full:
            return
        library = _library(library)
        occupations = {item["id"] for item in library["occupations"]}
        identities = {item["id"]: item for item in library["identities"]}
        motivations = {item["id"] for item in library["motivations"]}
        for pid, row in pop["people"].items():
            _require(row["id"] == pid and row["anchor"] == (pid in ANCHORS) and isinstance(row["name"], str), "人物身份无效。")
            _require(isinstance(row["location"], str) and row["location"] and isinstance(row["detailed"], bool)
                     and _int(row["portrait_seed"]) and 0 <= row["portrait_seed"] <= 2**53 - 1, "人物展示身份字段无效。")
            _require(isinstance(row["identities"], list) and len(row["identities"]) == len(set(row["identities"]))
                     and all(key in identities for key in row["identities"]) and row["motivation"] in motivations, "人物身份标签或动机无效。")
            _require(_int(row["birth_year"]) and row["status"] in {"unborn", "alive", "dead"} and row["occupation"] in occupations, "人物生存状态或职业无效。")
            _require(set(row["traits"]) == set(AXES) and all(_int(v) and 0 <= v <= 100 for v in row["traits"].values()), "人物性格轴超出范围。")
            _require(set(row["stats"]) == STATS and all(_int(v) and v >= 0 and (key == "cash" or v <= 100) for key, v in row["stats"].items()), "人物资源超出范围。")
            _require(row["knowledge"]["contact"] in {"none", "indirect", "direct"} and _int(row["knowledge"]["closeness"]) and 0 <= row["knowledge"]["closeness"] <= 100, "人物已知关系无效。")
            knowledge = row["knowledge"]
            _require(isinstance(knowledge["ever_close"], bool) and isinstance(knowledge["detained"], bool)
                     and isinstance(knowledge["source"], str), "人物已知状态字段无效。")
            _require(isinstance(knowledge["traits"], list) and all(isinstance(value, str) for value in knowledge["traits"])
                     and isinstance(knowledge["identities"], list) and all(key in identities for key in knowledge["identities"])
                     and (knowledge["motivation"] is None or isinstance(knowledge["motivation"], str)), "人物已知资料类型无效。")
            _require((knowledge["first_close_year"] is None and not knowledge["ever_close"])
                     or (_int(knowledge["first_close_year"]) and pop["start_year"] <= knowledge["first_close_year"] <= pop["year"] and knowledge["ever_close"]), "曾密切关系缺少有效日期。")
            _require(knowledge["met_year"] is None or _int(knowledge["met_year"]) and pop["start_year"] <= knowledge["met_year"] <= pop["year"], "实际相识日期无效。")
            _require(all(isinstance(v, bool) for v in row["flags"].values()), "人物事实标记无效。")
            if row["status"] == "unborn":
                _require(row["birth_year"] > pop["year"] and row["death_year"] is None and row["knowledge"]["contact"] == "none"
                         and not row["history"] and not row["recent"] and not row["relations"], "未出生人物不能已有交往或经历。")
            elif row["status"] == "alive":
                _require(row["birth_year"] <= pop["year"] and row["death_year"] is None and not row["death_recorded"], "已经死亡的人物不能复活。")
            else:
                _require(_int(row["death_year"]) and row["birth_year"] <= row["death_year"] <= pop["year"] and row["death_recorded"], "人物死亡记录不一致。")
            if row["flags"].get("detained"):
                _require(row["status"] == "alive" and _int(row["detained_until"]) and pop["year"] < row["detained_until"] <= pop["year"] + 2, "临时行动限制缺少明确期限。")
            _require(len(row["recent"]) <= 6 and len(row["relations"]) <= 6, "外围记录或稀疏关系超过容量。")
            groups = [identities[key].get("exclusive_group") for key in row["identities"] if identities[key].get("exclusive_group")]
            _require(len(groups) == len(set(groups)), "人物身份包含互斥处境。")
            for target, edge in row["relations"].items():
                _require(target in pop["people"] and target != pid and pop["people"][target]["birth_year"] <= pop["year"], "人物关系指向未知或未出生的人。")
                _require(all(_int(edge[key]) and 0 <= edge[key] <= 100 for key in EDGE_STATS) and all(isinstance(value, bool) for value in edge["flags"].values()), "有向关系数值无效。")
                _require(isinstance(edge["known"], bool) and isinstance(edge["known_label"], str)
                         and _int(edge["last_year"]) and edge["last_year"] <= pop["year"], "人物已知关系说明或日期无效。")
            _require(isinstance(row["history"], list) and isinstance(row["recent"], list), "人物经历列表无效。")
            entries = row["history"] + row["recent"]
            if row["status"] == "alive":
                _require(not any(entry["code"] == "death" for entry in entries), "实际死亡记录不能被改成在世状态。")
            _require(len({entry["id"] for entry in entries}) == len(entries), "同一个人的经历记录重复。")
            for entry in entries:
                _require(isinstance(entry["id"], str) and entry["id"] and isinstance(entry["code"], str) and entry["code"], "人物经历身份无效。")
                _require(_int(entry["year"]) and pop["start_year"] <= entry["year"] <= pop["year"] and entry["year"] >= row["birth_year"]
                         and entry["visibility"] in {"private", "participants", "public"} and isinstance(entry["known"], bool), "人物经历包含未来或出生前事件。")
                if entry["code"] == "annual" and "title" not in entry:
                    _require(entry["occupation"] in occupations and isinstance(entry["location"], str)
                             and isinstance(entry["resources"], list) and len(entry["resources"]) == 4
                             and all(_int(value) and value >= 0 and (index == 0 or value <= 100) for index, value in enumerate(entry["resources"])), "紧凑年度事实记录无效。")
                else:
                    _require(all(isinstance(entry[key], str) and bool(entry[key]) for key in ("title", "text", "source", "confidence")), "人物经历缺少可读叙事字段。")
                if entry["code"] in {"interaction", "shared_time", "player_social", "career", "annual"} and row["death_year"] is not None:
                    _require(entry["year"] <= row["death_year"], "已故人物仍在参与后续活动。")
        _require(all(pid in pop["people"] and pop["people"][pid]["knowledge"]["contact"] != "none" for pid in pop["tracked"]), "关注名单包含尚未认识的人。")
        _require(isinstance(pop["news"], list) and all(_int(entry["year"]) and pop["start_year"] <= entry["year"] <= pop["year"]
                 and entry["visibility"] in {"participants", "public"}
                 and all(isinstance(entry[key], str) and bool(entry[key]) for key in ("id", "title", "text", "source")) for entry in pop["news"]), "公开消息缺少叙事字段或泄漏了未知的私人事实。")
    except PopulationError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PopulationError("人口存档缺少字段或存在不一致。") from exc
