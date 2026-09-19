"""Executable design proof, not a complete life simulator.

Only trusted, reviewed catalog actions may mutate state. No model/network calls.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
RULESET = "smalltown-v0.1"
OPS = {"transfer", "adjust", "set_fact", "adjust_relation", "create_loan",
       "settle_loan", "reschedule_loan"}
DIMENSIONS = {"exploration", "persistence", "social_initiative", "care", "fairness",
              "conflict_style", "risk_taking", "help_seeking"}


class RuleError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RuleError(message)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_world(state):
    """Domain invariants for the explicitly supported prototype state."""
    require(state["schema_version"] == VERSION, "unsupported state schema")
    require(state["ruleset_id"] == RULESET, "unsupported ruleset")
    require(integer(state["day"]) and state["day"] >= 0, "invalid day")
    require(integer(state["revision"]) and state["revision"] >= 0, "invalid revision")
    people = state["persons"]
    require(state["player_id"] in people, "missing player")
    for pid, person in people.items():
        require(person["id"] == pid, "person id mismatch")
        require(integer(person["birth_day"]) and person["birth_day"] <= state["day"], "invalid birth")
        require(isinstance(person["alive"], bool), "alive must be boolean")
        for field in ("cash", "housing_reserve"):
            require(integer(person[field]) and person[field] >= 0, f"invalid {pid}.{field}")
        for field in ("energy", "health", "stress"):
            require(integer(person[field]) and 0 <= person[field] <= 100, f"invalid {pid}.{field}")
        if person["alive"]:
            require(person["death_day"] is None, "living person has death date")
        else:
            death = person["death_day"]
            require(integer(death) and person["birth_day"] <= death <= state["day"], "invalid death date")
        for fid, day in person["knowledge"].items():
            require(fid in state["historical_facts"], "unknown knowledge reference")
            fact = state["historical_facts"][fid]
            require(integer(day) and max(fact["day"], person["birth_day"]) <= day <= state["day"], "impossible knowledge time")
            require(person["death_day"] is None or day <= person["death_day"], "knowledge acquired after death")
    seen_relations = set()
    for relation in state["relationships"]:
        require(relation["from"] in people and relation["to"] in people, "unknown relation actor")
        require(relation["from"] != relation["to"], "self relationship unsupported")
        key = (relation["from"], relation["to"], relation["kind"])
        require(key not in seen_relations, "duplicate relationship")
        seen_relations.add(key)
        for field in ("trust", "closeness"):
            require(integer(relation[field]) and 0 <= relation[field] <= 100, "relation out of bounds")
    inverse = {"friend": "friend", "parent": "child", "child": "parent"}
    for source, target, kind in seen_relations:
        require(kind in inverse, "unsupported relationship kind")
        require((target, source, inverse[kind]) in seen_relations, "missing inverse relationship")
    for fact in state["historical_facts"].values():
        require(integer(fact["day"]) and fact["day"] <= state["day"], "future historical fact")
        for pid in fact["participants"]:
            require(pid in people, "unknown historical participant")
            person = people[pid]
            require(person["birth_day"] <= fact["day"], "fact before participant birth")
            require(person["death_day"] is None or fact["day"] <= person["death_day"], "active participation after death")
    for artifact in state["artifacts"].values():
        require(artifact["author"] in people, "unknown artifact author")
        author = people[artifact["author"]]
        created = artifact["created_day"]
        require(integer(created) and author["birth_day"] <= created <= state["day"], "invalid artifact date")
        require(author["death_day"] is None or created <= author["death_day"], "artifact created after death")
        for fid in artifact["fact_ids"]:
            require(fid in author["knowledge"] and author["knowledge"][fid] <= created, "artifact contains unknown future fact")
    for lid, loan in state["loans"].items():
        require(lid == loan["id"], "loan id mismatch")
        require(loan["creditor"] in people and loan["debtor"] in people, "unknown loan actor")
        require(loan["creditor"] != loan["debtor"], "self loan unsupported")
        require(integer(loan["amount"]) and loan["amount"] > 0, "invalid loan amount")
        require(integer(loan["created_day"]) and 0 <= loan["created_day"] <= state["day"], "invalid loan creation")
        require(integer(loan["due_day"]) and loan["due_day"] >= loan["created_day"], "invalid loan due date")
        require(loan["status"] in {"outstanding", "repaid", "deceased_pending"}, "unknown loan status")
        if loan["status"] == "outstanding":
            require(people[loan["creditor"]]["alive"] and people[loan["debtor"]]["alive"], "active loan has deceased party")
    seen_tasks = set()
    for task in state["tasks"]:
        require(task["id"] not in seen_tasks, "duplicate task")
        seen_tasks.add(task["id"])
        require(task["loan_id"] in state["loans"], "task missing loan")
        require(integer(task["due_day"]) and task["due_day"] >= 0, "invalid task date")
        require(task["status"] in {"pending", "resolved", "cancelled"}, "invalid task status")
        for pid in task["requires_alive"]:
            require(pid in people, "task has unknown actor")
            if task["status"] == "pending":
                require(people[pid]["alive"], "pending task requires dead actor")
        loan = state["loans"][task["loan_id"]]
        require(task["bindings"] == {"player": loan["creditor"], "friend": loan["debtor"]}, "task/loan binding mismatch")
        require(len(task["requires_alive"]) == 2 and set(task["requires_alive"]) == {loan["creditor"], loan["debtor"]}, "task life dependencies do not match loan parties")
        if task["status"] == "pending":
            require(loan["status"] == "outstanding" and task["due_day"] == loan["due_day"], "pending task/loan mismatch")


def validate_catalog(catalog):
    require(catalog["schema_version"] == VERSION and catalog["ruleset_id"] == RULESET, "catalog version mismatch")
    ids = set()
    for event in catalog["events"]:
        require(event["id"] not in ids, "duplicate event id")
        ids.add(event["id"])
        require(integer(event["version"]) and event["version"] > 0, "invalid event version")
        require(event["trigger"] in {"ambient", "scheduled"}, "invalid trigger")
        require(event["age_range"][0] <= event["age_range"][1], "invalid age range")
        choices = set()
        conditions = list(event["preconditions"])
        for choice in event["choices"]:
            require(choice["id"] not in choices, "duplicate choice id")
            choices.add(choice["id"])
            conditions.extend(choice["requirements"])
            for effect in choice["effects"]:
                require(effect["op"] in OPS, "unreviewed action opcode")
            for evidence in choice["evidence"]:
                require(evidence["dimension_id"] in DIMENSIONS, "unknown observation dimension")
                require(evidence["strength"] in {"limited", "ambiguous"}, "unsupported evidence strength")
        require(len(choices) >= 2, "event needs at least two authored choices")
        for condition in conditions:
            require(condition["op"] in {"eq", "gte", "lte"}, "unsupported condition operator")
    creates_loans = any(effect["op"] == "create_loan" for event in catalog["events"] for choice in event["choices"] for effect in choice["effects"])
    if creates_loans:
        require(any(event["id"] == "friend.loan_due" and event["trigger"] == "scheduled" for event in catalog["events"]), "create_loan requires loan_due catalog dependency")


@dataclass(frozen=True)
class Offer:
    event_id: str
    event_version: int
    revision: int
    bindings: dict
    task_id: str | None = None


class Engine:
    def __init__(self, state, catalog):
        validate_world(state)
        validate_catalog(catalog)
        self.state = deepcopy(state)
        self.catalog = deepcopy(catalog)
        self.events = {event["id"]: event for event in self.catalog["events"]}
        for task in self.state["tasks"]:
            require(task["event_id"] in self.events and self.events[task["event_id"]]["trigger"] == "scheduled", "task references unknown scheduled event")
        self.log = []

    def _task(self, state, task_id):
        return next((task for task in state["tasks"] if task["id"] == task_id), None)

    def _context(self, state, offer):
        context = dict(state)
        for role, pid in offer.bindings.items():
            require(pid in state["persons"], "unknown bound person")
            context[role] = state["persons"][pid]
        if offer.task_id:
            task = self._task(state, offer.task_id)
            require(task is not None, "missing scheduled task")
            context["loan"] = state["loans"][task["loan_id"]]
        return context

    def _resolve(self, state, offer, path):
        current = self._context(state, offer)
        try:
            for part in path.split("."):
                current = current[part]
        except (KeyError, TypeError):
            raise RuleError(f"missing fact: {path}") from None
        return current

    def _value(self, state, offer, value):
        if isinstance(value, dict):
            require(set(value) == {"ref"}, "unsupported dynamic value")
            return self._resolve(state, offer, value["ref"])
        return value

    def _condition(self, state, offer, condition):
        left = self._resolve(state, offer, condition["path"])
        right = self._value(state, offer, condition["value"])
        op = condition["op"]
        if op == "eq":
            passed = type(left) is type(right) and left == right
        else:
            require(integer(left) and integer(right), "numeric condition requires integers")
            passed = left >= right if op == "gte" else left <= right
        require(passed, f"{condition['path']} {op} {right}（当前：{left}）")

    def _event_valid(self, state, offer):
        require(offer.event_id in self.events, "unknown event")
        event = self.events[offer.event_id]
        require(event["version"] == offer.event_version, "event version changed")
        require(event["setting_id"] == state["setting_id"], "wrong setting")
        require(set(offer.bindings) == {"player", *event["actors"]}, "unexpected actor bindings")
        require(offer.bindings["player"] == state["player_id"], "wrong player binding")
        player = state["persons"][state["player_id"]]
        require(player["alive"], "player has died")
        age = (state["day"] - player["birth_day"]) // 365
        require(event["age_range"][0] <= age <= event["age_range"][1], "age out of range")
        require(len(set(offer.bindings.values())) == len(offer.bindings), "actor roles must be distinct")
        for role, selector in event["actors"].items():
            pid = offer.bindings[role]
            require(pid in state["persons"], "actor not found")
            person = state["persons"][pid]
            require(person["alive"] == selector["alive"], f"{role} alive constraint")
            require(any(r["from"] == player["id"] and r["to"] == pid and r["kind"] == selector["relation"] for r in state["relationships"]), "required relationship missing")
            if selector["same_location"]:
                require(person["location"] == player["location"], "actors are not co-located")
        if event["trigger"] == "scheduled":
            task = self._task(state, offer.task_id)
            require(task is not None and task["status"] == "pending", "task not pending")
            require(task["event_id"] == event["id"] and task["bindings"] == offer.bindings, "task binding mismatch")
            require(task["due_day"] <= state["day"], "task not due")
        else:
            require(offer.task_id is None, "ambient event cannot bind a task")
        for condition in event["preconditions"]:
            self._condition(state, offer, condition)

    def offer(self, event_id, bindings, task_id=None):
        require(event_id in self.events, "unknown event")
        offer = Offer(event_id, self.events[event_id]["version"], self.state["revision"], deepcopy(bindings), task_id)
        self._event_valid(self.state, offer)
        return offer

    def available_events(self):
        """Hard filtering only. Dramatic scheduling and generalized casting are future work."""
        offers = []
        for event in self.events.values():
            if event["trigger"] == "ambient":
                require(set(event["actors"]) == {"friend"}, "prototype supports one friend role")
                candidates = [(None, {"player": self.state["player_id"], "friend": pid}) for pid in sorted(self.state["persons"]) if pid != self.state["player_id"]]
            else:
                candidates = [(task["id"], task["bindings"]) for task in sorted(self.state["tasks"], key=lambda t: t["due_day"]) if task["event_id"] == event["id"] and task["status"] == "pending"]
            for task_id, bindings in candidates:
                try:
                    offers.append(self.offer(event["id"], bindings, task_id))
                except RuleError:
                    continue
        return offers

    def _actor(self, state, offer, role):
        require(role in offer.bindings, "unknown effect role")
        person = state["persons"][offer.bindings[role]]
        require(person["alive"], "active effect requires living actor")
        return person

    def _effect(self, state, offer, effect, transfer_trace=None):
        op = effect["op"]
        if op == "transfer":
            amount = self._value(state, offer, effect["amount"])
            require(integer(amount) and amount > 0, "invalid transfer amount")
            source = self._actor(state, offer, effect["from"])
            target = self._actor(state, offer, effect["to"])
            require(source["id"] != target["id"], "self transfer unsupported")
            require(source["cash"] >= amount, "insufficient cash")
            source["cash"] -= amount
            target["cash"] += amount
            if transfer_trace is not None:
                transfer_trace.append({"from":source["id"], "to":target["id"], "amount":amount})
        elif op == "adjust":
            require(effect["field"] in {"energy", "health", "stress"}, "numeric field is not writable")
            require(integer(effect["delta"]), "delta must be integer")
            actor = self._actor(state, offer, effect["actor"])
            actor[effect["field"]] += effect["delta"]
            require(0 <= actor[effect["field"]] <= 100, "immediate resource cost or gain out of bounds")
        elif op == "set_fact":
            require(isinstance(effect["value"], (bool, str, int)), "unsupported mutable fact value")
            state["facts"][effect["key"]] = effect["value"]
        elif op == "adjust_relation":
            require(effect["field"] in {"trust", "closeness"} and integer(effect["delta"]), "invalid relation adjustment")
            source = self._actor(state, offer, effect["from"])["id"]
            target = self._actor(state, offer, effect["to"])["id"]
            relation = next((r for r in state["relationships"] if r["from"] == source and r["to"] == target and r["kind"] == "friend"), None)
            require(relation is not None, "missing directional friendship")
            relation[effect["field"]] += effect["delta"]
            require(0 <= relation[effect["field"]] <= 100, "immediate relationship change out of bounds")
        elif op == "create_loan":
            creditor = self._actor(state, offer, effect["creditor"])["id"]
            debtor = self._actor(state, offer, effect["debtor"])["id"]
            amount, delay = effect["amount"], effect["due_in_days"]
            require(integer(amount) and amount > 0 and integer(delay) and delay > 0, "invalid loan terms")
            lid = f"loan-{state['revision'] + 1}-{len(state['loans']) + 1}"
            state["loans"][lid] = {"id":lid, "creditor":creditor, "debtor":debtor, "amount":amount, "created_day":state["day"], "due_day":state["day"] + delay, "status":"outstanding"}
            state["tasks"].append({"id":f"task-{lid}", "event_id":"friend.loan_due", "loan_id":lid, "due_day":state["day"] + delay, "bindings":{"player":creditor,"friend":debtor}, "requires_alive":[creditor,debtor], "status":"pending", "cancellation_reason":None})
        elif op in {"settle_loan", "reschedule_loan"}:
            require(offer.task_id is not None, "loan operation requires scheduled context")
            task = self._task(state, offer.task_id)
            loan = state["loans"][task["loan_id"]]
            require(loan["status"] == "outstanding", "loan not outstanding")
            if op == "settle_loan":
                require(self._actor(state, offer, "friend").get("repayment_willing") is True, "NPC does not agree to repay")
                self._effect(state, offer, {"op":"transfer", "from":"friend", "to":"player", "amount":loan["amount"]}, transfer_trace)
                loan["status"] = "repaid"
            else:
                delay = effect["days"]
                require(integer(delay) and delay > 0, "extension must be positive")
                task["due_day"] = state["day"] + delay
                loan["due_day"] = task["due_day"]
        else:
            raise RuleError("unreviewed action opcode")

    def _simulate(self, offer, choice, base_state=None, transfer_trace=None):
        candidate = deepcopy(self.state if base_state is None else base_state)
        self._event_valid(candidate, offer)
        for condition in choice["requirements"]:
            self._condition(candidate, offer, condition)
        # Each newly created debt must correspond to a transfer in this same choice.
        transfers = Counter()
        for effect in choice["effects"]:
            if effect["op"] == "transfer":
                transfers[(effect["from"], effect["to"], self._value(candidate, offer, effect["amount"]))] += 1
            if effect["op"] == "create_loan":
                key = (effect["creditor"], effect["debtor"], effect["amount"])
                require(transfers[key] > 0, "loan creation requires matching prior transfer")
                transfers[key] -= 1
            self._effect(candidate, offer, effect, transfer_trace)
        if offer.task_id:
            task = self._task(candidate, offer.task_id)
            if task["due_day"] <= candidate["day"]:
                task["status"] = "resolved"
        validate_world(candidate)
        return candidate

    def choices(self, offer):
        require(offer.revision == self.state["revision"], "stale offer")
        self._event_valid(self.state, offer)
        result = []
        for choice in self.events[offer.event_id]["choices"]:
            reason = None
            try:
                self._simulate(offer, choice)
            except RuleError as error:
                reason = str(error)
            result.append({"id":choice["id"], "label":choice["label"], "available":reason is None, "locked_reason":reason})
        return result

    def description(self, offer):
        self._event_valid(self.state, offer)
        return re.sub(r"\{([a-zA-Z0-9_.]+)\}", lambda match: str(self._resolve(self.state, offer, match[1])), self.events[offer.event_id]["description"])

    def _commit(self, candidate, kind, payload):
        candidate["revision"] = self.state["revision"] + 1
        validate_world(candidate)
        entry = {"sequence":candidate["revision"], "kind":kind, "day":candidate["day"], "before_hash":digest(self.state), "payload":deepcopy(payload), "state_after":deepcopy(candidate), "after_hash":digest(candidate)}
        entry["previous_entry_hash"] = self.log[-1]["entry_hash"] if self.log else "0" * 64
        entry["entry_hash"] = digest(entry)
        self.state = candidate
        self.log.append(entry)
        return deepcopy(entry)

    def choose(self, offer, choice_id):
        require(offer.revision == self.state["revision"], "stale offer")
        available = self.choices(offer)
        chosen = next((item for item in available if item["id"] == choice_id), None)
        require(chosen is not None, "unknown choice")
        require(chosen["available"], chosen["locked_reason"] or "unavailable choice")
        event = self.events[offer.event_id]
        choice = next(item for item in event["choices"] if item["id"] == choice_id)
        transfers = []
        candidate = self._simulate(offer, choice, transfer_trace=transfers)
        player = self.state["persons"][self.state["player_id"]]
        total_cost = sum(transfer["amount"] for transfer in transfers if transfer["from"] == player["id"])
        payload = {"event_id":event["id"], "event_version":event["version"], "choice_id":choice_id, "choice_label":choice["label"], "bindings":offer.bindings, "task_id":offer.task_id, "options":available, "opportunity":sum(item["available"] for item in available) >= 2, "context_tags":event["context_tags"], "age":(self.state["day"] - player["birth_day"]) // 365, "resources_before":{field:player[field] for field in ("cash","energy","health","stress","housing_reserve")}, "player_knowledge":player["knowledge"], "presented_facts":self.description(offer), "cash_cost":total_cost, "cash_cost_share":total_cost / player["cash"] if player["cash"] else None, "below_housing_reserve_after":candidate["persons"][player["id"]]["cash"] < player["housing_reserve"], "observations":choice["evidence"]}
        return self._commit(candidate, "choice", payload)

    def _cancel_invalid_due(self, candidate):
        cancelled = []
        for task in candidate["tasks"]:
            if task["status"] != "pending" or task["due_day"] > candidate["day"]:
                continue
            event = self.events[task["event_id"]]
            offer = Offer(event["id"], event["version"], candidate["revision"], task["bindings"], task["id"])
            try:
                self._event_valid(candidate, offer)
                executable = False
                for choice in event["choices"]:
                    try:
                        self._simulate(offer, choice, candidate)
                        executable = True
                        break
                    except RuleError:
                        continue
                require(executable, "no executable choices")
            except RuleError as error:
                task.update(status="cancelled", cancellation_reason=f"precondition_invalid:{error}")
                cancelled.append(task["id"])
        return cancelled

    def advance(self, days):
        require(integer(days) and days > 0, "advance must be positive integer days")
        require(self.state["persons"][self.state["player_id"]]["alive"], "player has died")
        candidate = deepcopy(self.state)
        cancelled = self._cancel_invalid_due(candidate)
        pending = [t for t in candidate["tasks"] if t["status"] == "pending"]
        require(not any(t["due_day"] <= self.state["day"] for t in pending), "resolve due tasks before advancing")
        target = self.state["day"] + days
        due = [t["due_day"] for t in pending if t["due_day"] <= target]
        if due:
            target = min(due)
        candidate["day"] = target
        cancelled.extend(self._cancel_invalid_due(candidate))
        return self._commit(candidate, "time_advanced", {"requested_days":days, "elapsed_days":target - self.state["day"], "cancelled_tasks":cancelled})

    def mark_dead(self, pid, cause):
        require(pid in self.state["persons"] and self.state["persons"][pid]["alive"], "person already dead or missing")
        require(isinstance(cause, str) and bool(cause.strip()), "death must have a recorded cause")
        candidate = deepcopy(self.state)
        person = candidate["persons"][pid]
        person.update(alive=False, death_day=candidate["day"], health=0)
        for task in candidate["tasks"]:
            if task["status"] == "pending" and pid in task["requires_alive"]:
                task.update(status="cancelled", cancellation_reason=f"required_actor_died:{pid}")
        for loan in candidate["loans"].values():
            if loan["status"] == "outstanding" and pid in {loan["creditor"], loan["debtor"]}:
                loan["status"] = "deceased_pending"
        return self._commit(candidate, "person_died", {"person_id":pid,"cause":cause})

    def observations(self):
        rows = []
        for entry in self.log:
            payload = entry["payload"]
            if entry["kind"] != "choice" or not payload["opportunity"]:
                continue
            for observation in payload["observations"]:
                rows.append({**observation, "evidence_id":f"decision-{entry['sequence']}", "event_id":payload["event_id"], "context_tags":payload["context_tags"], "resources_before":payload["resources_before"], "cash_cost":payload["cash_cost"], "locked_options":[x["id"] for x in payload["options"] if not x["available"]]})
        return rows


def replay(initial_state, log):
    """Restore recorded snapshots; never regenerate events or rerun future rules."""
    state = deepcopy(initial_state)
    validate_world(state)
    previous_entry_hash = "0" * 64
    for entry in log:
        require(entry["previous_entry_hash"] == previous_entry_hash, "log chain mismatch")
        require(entry["entry_hash"] == digest({key:value for key,value in entry.items() if key != "entry_hash"}), "log entry contents changed")
        require(entry["before_hash"] == digest(state), "replay before-state mismatch")
        require(entry["sequence"] == state["revision"] + 1, "replay sequence mismatch")
        candidate = deepcopy(entry["state_after"])
        require(candidate["revision"] == entry["sequence"], "snapshot revision mismatch")
        require(entry["after_hash"] == digest(candidate), "snapshot hash mismatch")
        validate_world(candidate)
        state = candidate
        previous_entry_hash = entry["entry_hash"]
    return state


def load_engine():
    state = json.loads((ROOT / "examples/world.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "content/events.json").read_text(encoding="utf-8"))
    return Engine(state, catalog)
