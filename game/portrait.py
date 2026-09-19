"""Grounded Chinese biographies from committed life records.

This module describes the fictional character's recorded actions.  It deliberately
does not turn event annotations into psychometric scores or infer hidden motives.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
from typing import Any


DIMENSION_FILE = Path(__file__).resolve().parents[1] / "content" / "personality-dimensions.json"
STAGES = (
    ("童年与少年", 0, 17),
    ("青年", 18, 35),
    ("中年", 36, 59),
    ("晚年", 60, None),
)
BEHAVIOR_LABELS = {
    "negotiated_extension": "延长还款期限",
    "deferred_confrontation": "暂时结束催促",
    "everyday_learning": "在日常中学习新东西",
    "material_support": "提供借款支持",
    "partial_material_support": "提供部分借款",
    "practical_support_attempt": "尝试寻找其他帮助办法",
    "declined_this_request": "拒绝这一次借款请求",
    "accept_financial_exposure": "承担这笔借款的资金风险",
    "limit_financial_exposure": "减少出借金额",
}
MAJOR_CATEGORIES = {"升学", "学业", "职业", "关系", "婚恋", "家庭", "住房", "借款",
                    "转行", "转业", "退休", "照顾", "健康", "生计"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value: Any, field: str, *, empty: bool = True) -> str:
    _require(isinstance(value, str), f"{field} 必须是文字")
    _require(empty or bool(value.strip()), f"{field} 不能为空")
    return value.strip()


@lru_cache(maxsize=1)
def _dimensions() -> tuple[tuple[str, str], ...]:
    data = json.loads(DIMENSION_FILE.read_text(encoding="utf-8"))
    result = tuple((item["id"], item["label"]) for item in data["dimensions"])
    _require(len(result) == 8 and len({item[0] for item in result}) == 8,
             "人物画像定义必须包含八个不同维度")
    return result


@lru_cache(maxsize=1)
def _dimension_specs() -> dict[str, dict]:
    data = json.loads(DIMENSION_FILE.read_text(encoding="utf-8"))
    catalog = data.get("subdimension_catalog", {})
    return {item["id"]: {
        "subdimensions": list(catalog.get(item["id"], [])),
        "behavior_categories": list(item.get("behavior_categories", [])),
        "subcontexts": list(item.get("subcontexts", [])),
    } for item in data.get("dimensions", [])}


def _validate(state: dict) -> tuple[list[dict], dict, tuple[tuple[str, str], ...]]:
    """Reject contradictory supplied data; missing optional evidence is allowed."""
    _require(isinstance(state, dict), "人物志输入必须是对象")
    _text(state.get("name"), "name", empty=False)
    _require(_integer(state.get("age")) and state["age"] >= 0, "age 必须是非负整数")
    for field in ("year", "born_year"):
        if field in state:
            _require(_integer(state[field]), f"{field} 必须是整数")
    if "finished" in state:
        _require(isinstance(state["finished"], bool), "finished 必须是布尔值")
    if state.get("death_reason") is not None:
        _text(state["death_reason"], "death_reason")
    timeline = state.get("timeline", [])
    _require(isinstance(timeline, list), "timeline 必须是列表")
    dimensions = _dimensions()
    dimension_ids = {item[0] for item in dimensions}
    seen = set()
    previous_age = -1
    previous_year = None
    for index, entry in enumerate(timeline):
        _require(isinstance(entry, dict), f"timeline[{index}] 必须是对象")
        record_id = _text(entry.get("id"), f"timeline[{index}].id", empty=False)
        _require(record_id not in seen, f"时间线记录 ID 重复：{record_id}")
        seen.add(record_id)
        age = entry.get("age")
        _require(_integer(age) and 0 <= age <= state["age"], f"{record_id} 的年龄超出已发生的人生")
        _require(age >= previous_age, f"时间线年龄顺序错误：{record_id}")
        previous_age = age
        if "year" in entry:
            year = entry["year"]
            _require(_integer(year), f"{record_id}.year 必须是整数")
            _require("year" not in state or year <= state["year"], f"{record_id} 位于未来")
            _require(previous_year is None or year >= previous_year, f"时间线年份顺序错误：{record_id}")
            previous_year = year
        for field in ("title", "text", "kind"):
            if field in entry:
                _text(entry[field], f"{record_id}.{field}")
        for field in ("choice", "choice_id", "event_id"):
            if entry.get(field) is not None:
                _text(entry[field], f"{record_id}.{field}")
        if entry.get("episode_id") is not None:
            _text(entry["episode_id"], f"{record_id}.episode_id", empty=False)
        if "npc_ids" in entry:
            _require(isinstance(entry["npc_ids"], list)
                     and all(isinstance(pid, str) for pid in entry["npc_ids"]),
                     f"{record_id}.npc_ids 必须是字符串列表")
        observations = entry.get("observations", [])
        _require(isinstance(observations, list), f"{record_id}.observations 必须是列表")
        _require(not observations or (entry.get("kind") == "choice" and bool(entry.get("choice"))),
                 f"{record_id} 的行为观察缺少真实选择记录")
        for observation in observations:
            _require(isinstance(observation, dict), f"{record_id} 的观察必须是对象")
            dimension = observation.get("dimension", observation.get("dimension_id"))
            _require(dimension in dimension_ids, f"{record_id} 含未知观察维度：{dimension}")
            _text(observation.get("behavior"), f"{record_id}.behavior", empty=False)
            if observation.get("facet") is not None:
                allowed_facets = set(_dimension_specs().get(dimension, {}).get("subdimensions", [])) | {"general"}
                _require(observation["facet"] in allowed_facets,
                         f"{record_id} 含未知观察子维度：{observation['facet']}")
        context = entry.get("context")
        if context is None:
            continue
        _require(isinstance(context, dict), f"{record_id}.context 必须是对象")
        if "opportunity" in context:
            _require(isinstance(context["opportunity"], bool), f"{record_id}.opportunity 必须是布尔值")
        available = context.get("available_choice_ids")
        if available is not None:
            _require(isinstance(available, list) and all(isinstance(item, str) for item in available),
                     f"{record_id}.available_choice_ids 必须是字符串列表")
            _require(len(available) == len(set(available)), f"{record_id} 的可行选项重复")
            if entry.get("choice_id"):
                _require(entry["choice_id"] in available, f"{record_id} 所选选项不在可行选项中")
            if "opportunity" in context:
                _require(context["opportunity"] == (len(available) >= 2),
                         f"{record_id} 的选择机会标记与可行选项不一致")
        locked = context.get("locked_options", [])
        _require(isinstance(locked, list), f"{record_id}.locked_options 必须是列表")
        for option in locked:
            _require(isinstance(option, dict) and isinstance(option.get("id"), str),
                     f"{record_id} 的锁定选项格式错误")
            _require(option["id"] != entry.get("choice_id"), f"{record_id} 选择了锁定选项")
            _require(available is None or option["id"] not in available,
                     f"{record_id} 的同一选项同时可行且锁定")
        if "context_tags" in context:
            _require(isinstance(context["context_tags"], list)
                     and all(isinstance(tag, str) for tag in context["context_tags"]),
                     f"{record_id}.context_tags 必须是字符串列表")
        if "opportunity_dimensions" in context:
            _require(isinstance(context["opportunity_dimensions"], list)
                     and all(item in dimension_ids for item in context["opportunity_dimensions"]),
                     f"{record_id}.opportunity_dimensions 含未知维度")
        if "assessment_context" in context:
            _require(isinstance(context["assessment_context"], dict)
                     and all(isinstance(value, str) for value in context["assessment_context"].values()),
                     f"{record_id}.assessment_context 格式错误")
    npcs = state.get("npcs", {})
    _require(isinstance(npcs, dict), "npcs 必须是对象")
    for npc_id, npc in npcs.items():
        _require(isinstance(npc_id, str) and isinstance(npc, dict), "NPC 记录格式错误")
        _text(npc.get("name"), f"npcs.{npc_id}.name", empty=False)
        for field in ("alive", "met"):
            if field in npc:
                _require(isinstance(npc[field], bool), f"npcs.{npc_id}.{field} 必须是布尔值")
        if npc.get("death_year") is not None:
            _require(_integer(npc["death_year"]), f"npcs.{npc_id}.death_year 必须是整数")
            _require(npc.get("alive") is not True, f"{npc_id} 仍健在却已有死亡年份")
            _require("year" not in state or npc["death_year"] <= state["year"], f"{npc_id} 的死亡记录位于未来")
    for entry in timeline:
        for npc_id in entry.get("npc_ids", []):
            _require(npc_id in npcs, f"{entry['id']} 引用了不存在的 NPC：{npc_id}")
    return timeline, npcs, dimensions


def _record_sentence(entry: dict) -> str:
    """Quote recorded facts; never synthesize an unrecorded outcome."""
    stamp = f"{entry['age']}岁"
    if "year" in entry:
        stamp += f"（{entry['year']}年）"
    title = entry.get("title", "").strip()
    choice = entry.get("choice")
    body = f"{stamp}，{title}。" if title else f"{stamp}。"
    if choice:
        body += f"你选择了「{choice}」。"
    recorded_text = entry.get("text", "").strip()
    if recorded_text:
        body += recorded_text
        if recorded_text[-1] not in "。！？!?…":
            body += "。"
    if not title and not choice and not recorded_text:
        body += "这一条记录没有留下具体内容。"
    return body


def _highlights(records: list[dict], limit: int = 5, *, relationship: bool = False) -> list[dict]:
    """Select a small, chronological set; the original timeline stays untouched."""
    candidates = [entry for entry in records if entry.get("kind") != "annual"]
    if len(candidates) <= limit:
        return candidates
    selected = []

    def add(entry):
        if len(selected) < limit and entry not in selected:
            selected.append(entry)

    if relationship:
        # A real settlement and a death take precedence over repeated interactions.
        deaths = [entry for entry in candidates if entry.get("kind") == "npc_death"]
        settlements = [entry for entry in candidates if entry.get("choice_id") in {"repay", "accept_repayment"}
                       or entry.get("kind") == "debt"]
        if deaths:
            add(deaths[-1])
        if settlements:
            add(settlements[-1])
    else:
        for entry in candidates:
            if entry.get("kind") in {"birth", "death"}:
                add(entry)
    choices = [entry for entry in candidates if entry.get("kind") == "choice"]
    if choices:
        add(choices[0])
        add(choices[-1])

    def importance(entry):
        kind = entry.get("kind")
        if kind == "npc_death":
            return 90
        if kind in {"family", "retirement", "debt"}:
            return 80
        if kind == "choice":
            tags = set(entry.get("context", {}).get("context_tags", []))
            return 75 if tags & MAJOR_CATEGORIES else 60
        if kind in {"hardship", "aid"}:
            return 70
        return 50

    while len(selected) < limit:
        remaining = [entry for entry in candidates if entry not in selected]
        if not remaining:
            break
        # Repeated hardship/aid headlines do not crowd out distinct turning points.
        titles = {entry.get("title") for entry in selected}
        remaining.sort(key=lambda entry: (
            entry.get("title") in titles,
            -importance(entry),
            -min((abs(entry["age"] - old["age"]) for old in selected), default=0),
            entry["age"],
        ))
        add(remaining[0])
    selected_ids = {entry["id"] for entry in selected}
    return [entry for entry in candidates if entry["id"] in selected_ids]


def _chapters(state: dict, timeline: list[dict]) -> list[dict]:
    chapters = []
    for title, start, end in STAGES:
        records = [entry for entry in timeline if entry["age"] >= start
                   and (end is None or entry["age"] <= end)]
        highlights = _highlights(records)
        if highlights:
            text = "\n\n".join(_record_sentence(entry) for entry in highlights)
        elif records:
            text = "这一阶段的日常成长与生活收支，留在完整年表中。"
        elif state["age"] < start:
            text = (f"这段人生停在{state['age']}岁，没有进入这一阶段。"
                    if state.get("finished", False) else "这一阶段尚未到来。")
        else:
            text = "这一阶段没有留下具体事件记录，不能据此补写经历。"
        age_range = f"{start}—{end}岁" if end is not None else f"{start}岁以后"
        chapters.append({"title": f"{title} · {age_range}", "text": text,
                         "event_ids": [entry["id"] for entry in highlights]})
    return chapters


def _observation_status(entry: dict) -> str:
    context = entry.get("context") or {}
    if context.get("opportunity") is False or context.get("locked_options"):
        return "constrained"
    available = context.get("available_choice_ids")
    if (context.get("opportunity") is not True or not isinstance(available, list)
            or len(available) < 2 or not entry.get("choice_id")
            or entry["choice_id"] not in available):
        return "missing_context"
    return "recorded_action"


def _patterns(timeline: list[dict], dimensions: tuple) -> tuple[list[dict], Counter]:
    result = []
    exclusions = Counter()
    specs = _dimension_specs()
    for dimension_id, label in dimensions:
        entries = []
        constrained = 0
        missing_context = 0
        eligible_opportunities = 0
        opportunity_context_counts = Counter()
        dimension_excluded_ids = set()
        for entry in timeline:
            observations = [item for item in entry.get("observations", [])
                            if item.get("dimension", item.get("dimension_id")) == dimension_id]
            context = entry.get("context") or {}
            opportunity_dimensions = context.get("opportunity_dimensions")
            relevant_opportunity = (dimension_id in opportunity_dimensions
                                    if isinstance(opportunity_dimensions, list)
                                    else bool(observations))
            if not relevant_opportunity:
                continue
            status = _observation_status(entry)
            if status == "constrained":
                constrained += 1
                exclusions[(entry["id"], status)] = 1
                dimension_excluded_ids.add(entry["id"])
                continue
            if status == "missing_context":
                missing_context += 1
                exclusions[(entry["id"], status)] = 1
                dimension_excluded_ids.add(entry["id"])
                continue
            eligible_opportunities += 1
            tags = tuple(sorted(str(tag) for tag in context.get("context_tags", [])))
            opportunity_context_counts[tags] += 1
            if not observations:
                continue
            behaviors = tuple(sorted({item["behavior"] for item in observations}))
            entries.append((entry, behaviors))
        evidence_ids = []
        counter_ids = []
        behavior_counts = Counter()
        context_counts = Counter()
        facet_counts = Counter()
        pressure_counts = Counter()
        relationship_counts = Counter()
        information_counts = Counter()
        horizon_counts = Counter()
        episode_ids = set()
        for entry, behaviors in entries:
            for behavior in behaviors:
                behavior_counts[behavior] += 1
            context = entry.get("context") or {}
            context_counts[tuple(sorted(str(tag) for tag in context.get("context_tags", [])))] += 1
            assessment_context = context.get("assessment_context") or {}
            pressure_counts[assessment_context.get("pressure_band", "unknown")] += 1
            relationship_counts[assessment_context.get("relationship_scope", "unknown")] += 1
            information_counts[assessment_context.get("information_level", "unknown")] += 1
            horizon_counts[assessment_context.get("time_horizon", "unknown")] += 1
            for observation in entry.get("observations", []):
                if observation.get("dimension", observation.get("dimension_id")) == dimension_id:
                    facet_counts[observation.get("facet") or observation.get("subdimension") or "general"] += 1
            episode_ids.add(str(entry.get("episode_id") or entry.get("event_instance_id")
                                or entry.get("event_id") or entry["id"]))
        if entries:
            # Preserve one different strategy in a comparable authored context.
            baseline, baseline_behaviors = entries[0]
            baseline_tags = tuple(sorted(baseline["context"].get("context_tags", [])))
            counter = None
            if baseline_tags:
                for entry, behaviors in entries[1:]:
                    tags = tuple(sorted(entry["context"].get("context_tags", [])))
                    if tags == baseline_tags and behaviors != baseline_behaviors:
                        counter = (entry, behaviors)
            remaining = [item for item in entries if counter is None or item[0]["id"] != counter[0]["id"]]
            selected = [remaining[0]]
            if len(remaining) > 1:
                selected.append(remaining[-1])
            seen_behaviors = {behaviors for _, behaviors in selected}
            for item in remaining[1:-1]:
                if item[1] not in seen_behaviors and len(selected) < 3:
                    selected.append(item)
                    seen_behaviors.add(item[1])
            selected_ids = {entry["id"] for entry, _ in selected}
            selected = [item for item in entries if item[0]["id"] in selected_ids]
            evidence_ids = [entry["id"] for entry, _ in selected]
            text = "；".join(_behavior_sentence(entry, behaviors) for entry, behaviors in selected) + "。"
            if counter is not None:
                entry, behaviors = counter
                counter_ids = [entry["id"]]
                text += f"另一次做法是：{_behavior_sentence(entry, behaviors)}。"
            coverage = "有限"
        else:
            text = ("相关选择受当时条件限制，暂不归纳。" if constrained else
                    "相关记录的选择条件不完整，暂不归纳。" if missing_context else
                    "这一方面还没有留下可供归纳的选择。")
            coverage = "未观察"
        spec = specs.get(dimension_id, {})
        limitations = []
        if constrained:
            limitations.append(f"{constrained} 次选择受条件限制，未计入自由偏好")
        if missing_context:
            limitations.append(f"{missing_context} 次记录缺少完整选择上下文")
        if not entries:
            limitations.append("尚无满足条件的有效观察机会")
        if eligible_opportunities and not entries:
            limitations.append("遇到过相关机会，但所选方案没有留下该维度的行为标注")
        if len(episode_ids) < 2 and entries:
            limitations.append("目前只有一个独立剧情，不能检验跨剧情稳定性")
        if len(behavior_counts) > 1:
            limitations.append("同一维度出现了不同做法，需要结合各自处境理解")
        excluded_ids = sorted(dimension_excluded_ids)
        if len(episode_ids) >= 2 and len(behavior_counts) <= 1:
            evidence_level = "跨剧情重复观察"
        elif eligible_opportunities >= 2:
            evidence_level = "重复观察"
        elif eligible_opportunities == 1:
            evidence_level = "单次观察"
        else:
            evidence_level = "材料不足"
        result.append({"dimension": dimension_id, "label": label, "text": text,
                       "evidence_ids": evidence_ids, "counter_evidence_ids": counter_ids,
                       "coverage": coverage,
                       "subdimensions": spec.get("subdimensions", []),
                       "eligible_opportunities": eligible_opportunities,
                       "independent_episodes": len(episode_ids),
                       "behavior_counts": dict(behavior_counts),
                       "context_counts": {"|".join(tags): count for tags, count in context_counts.items()},
                       "opportunity_context_counts": {"|".join(tags): count for tags, count in opportunity_context_counts.items()},
                       "facet_counts": dict(facet_counts),
                       "pressure_counts": dict(pressure_counts),
                       "relationship_counts": dict(relationship_counts),
                       "information_counts": dict(information_counts),
                       "horizon_counts": dict(horizon_counts),
                       "evidence_level": evidence_level,
                       "excluded_evidence_ids": excluded_ids,
                       "limitations": limitations})
    return result, exclusions


def _behavior_sentence(entry: dict, behaviors: tuple[str, ...]) -> str:
    phrases = []
    for behavior in behaviors:
        if behavior in BEHAVIOR_LABELS:
            phrase = BEHAVIOR_LABELS[behavior]
        elif any("\u4e00" <= char <= "\u9fff" for char in behavior):
            phrase = behavior.rstrip("。；;")
        else:
            # An unknown internal identifier is not player-facing prose.
            phrase = f"选择「{entry['choice']}」"
        if phrase not in phrases:
            phrases.append(phrase)
    return f"{entry['age']}岁时，你" + "，也".join(phrases)


def _relationships(state: dict, timeline: list[dict], npcs: dict) -> list[dict]:
    relationships = []
    for npc_id, npc in npcs.items():
        name = npc["name"].strip()
        records = []
        for entry in timeline:
            explicit = npc_id in entry.get("npc_ids", [])
            named = name in " ".join(str(entry.get(field) or "")
                                     for field in ("title", "text", "choice"))
            if explicit or named:
                records.append(entry)
        if not npc.get("met", bool(records)):
            continue
        highlights = _highlights(records, limit=4, relationship=True)
        if highlights:
            text = "\n\n".join(_record_sentence(entry) for entry in highlights)
        else:
            text = "档案记下了这位与你相识的人，但没有留下可引用的共同事件。"
        if npc.get("alive") is False and not any(entry.get("kind") == "npc_death" for entry in highlights):
            if npc.get("death_year") is not None:
                text += f"\n档案记载，{name}于{npc['death_year']}年离世。"
            else:
                text += f"\n档案末尾，{name}已离世；具体时间没有记录。"
        # No repayment or forgiveness is inferred from the NPC's death or from
        # a surviving claim. Those facts must appear as committed timeline text.
        relationships.append({"name": name, "text": text,
                              "event_ids": [entry["id"] for entry in highlights]})
    return relationships


def build_biography(state: dict) -> dict:
    """Return a deterministic, read-only biography for the UI.

    Required: name, age.  Optional: year, born_year, finished, death_reason,
    timeline and npcs. Present records are validated instead of silently repaired.
    Every event/evidence reference is an ID of an existing timeline record.
    """
    timeline, npcs, dimensions = _validate(state)
    name = state["name"].strip()
    age = state["age"]
    finished = state.get("finished", False)
    subtitle = f"{age}岁 · {'人生已落笔' if finished else '人生仍在继续'}"
    if "born_year" in state and "year" in state:
        subtitle = f"{state['born_year']}—{state['year']}年 · " + subtitle
    choices = sum(entry.get("kind") == "choice" and bool(entry.get("choice"))
                  for entry in timeline)
    if timeline:
        summary = f"{name}走到{age}岁，留下{len(timeline)}则人生记录，其中{choices}则记下了当时的选择。"
    else:
        summary = f"{name}的人生记录到{age}岁。尚无具体经历可供回看。"
    if finished:
        reason = state.get("death_reason")
        summary += f"人生结束的记录为：{reason}。" if reason else "人生已经结束，原因未记录。"
    else:
        summary += "故事仍在继续，这份小传只写已经发生的部分。"
    patterns, exclusions = _patterns(timeline, dimensions)
    notes = [
        "小传精选每阶段最多五个片段；完整经历与年度收支仍保存在年表中。",
        "行动画像只描述本局角色，不分析现实玩家，也不把次数换成人格分数。“有限”表示材料有限，“未观察”表示尚无可用记录。",
        "锁定选项不算拒绝，受限选择不作为自由偏好的证据；能够选择两个方案，也不足以证明稳定人格。",
        "不同做法保留了变化与反例，不代表善恶高低；类似场景仍可能有不同的资源、信息与压力。",
    ]
    if exclusions:
        constrained_count = sum(status == "constrained" for _, status in exclusions)
        missing_count = sum(status == "missing_context" for _, status in exclusions)
        notes.append(f"另有{constrained_count}次受限选择、{missing_count}次条件记录不足的选择未进入行动画像，可在完整年表中回看。")
    closing = (f"那些决定各有当时的处境。已经留下的记录，是{name}这段人生可被回看的部分；没有记下的地方，留作空白。"
               if finished else f"这一页停在{name}的{age}岁。已经走过的路留在这里，余下的故事尚未发生。")
    return {"title": f"{name}小传", "subtitle": subtitle, "summary": summary,
            "chapters": _chapters(state, timeline), "patterns": patterns,
            "relationships": _relationships(state, timeline, npcs),
            "closing": closing, "notes": notes}
