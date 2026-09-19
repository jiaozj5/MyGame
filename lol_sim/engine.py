"""Seeded, inspectable approximation of a solo top lane, not Riot game code.

Champion numbers come from the separately versioned catalogue. Movement, minion
AI and opponent policies are explicitly reduced models. No unsupported champion
is silently mapped to a generic fighter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import itertools
import math
import random
import statistics


MODEL_VERSION = "approximate-lane-v1"
POLICIES = {"farm": "稳健补刀", "short_trade": "短换血", "all_in": "持续追击", "poke": "技能消耗"}
WAVES = {"freeze": "控线补尾刀", "slow_push": "慢推", "fast_push": "快速推线"}
RUNES = {"conqueror": "征服者", "grasp": "不灭之握", "press_the_attack": "强攻", "fleet": "迅捷步法", "fleet_footwork": "迅捷步法", "comet": "奥术彗星", "phase_rush": "相位猛冲"}
SUMMONERS = {"flash": "闪现", "ignite": "点燃", "teleport": "传送", "barrier": "屏障", "exhaust": "虚弱"}
DEFAULT_CONFIG = {
    "player": {"champion": "Garen", "level": 1, "skill_order": ["Q", "E", "W", "E", "E", "R"],
               "items": ["1055"], "rune": "conqueror", "summoners": ["flash", "ignite"],
               "policy": "short_trade", "wave": "slow_push", "combo": ["Q", "AA", "E", "W", "R"]},
    "opponent": {"champion": "Darius", "level": 1, "skill_order": ["W", "Q", "E", "Q", "Q", "R"],
                 "items": ["1055"], "rune": "conqueror", "summoners": ["flash", "ghost"],
                 "policy": "all_in", "wave": "slow_push", "combo": ["E", "AA", "W", "Q", "R"]},
    "duration": 240, "seed": 42, "start_time": 90, "accuracy": 0.8,
    "opponent_accuracy": 0.8, "distance": 300, "mode": "lane", "starting_gold": 500,
}
SUMMONERS["ghost"] = "疾跑"
WARNINGS = [
    "这是可复现的近似对线模型，不是 Riot 游戏服务器；分数仅用于本模型、同条件方案比较。",
    "兵线位置、走位命中、回城/复活返线和防御塔为简化模型；不包含打野、视野、碰撞、仇恨拉扯和逐帧取消后摇。",
    "天赋仅模拟主系基石的近似效果；未选择副系、属性碎片及其他天赋。召唤师施放由固定策略控制。",
    "装备只结算目录列出的基础属性；特殊被动与触发伤害没有完整接入。",
    "优化仅搜索明确列出的候选与种子，对手为固定策略，并非全局最优或真实对局胜率。",
]
CHAMPION_APPROXIMATIONS = {
    "Garen": "盖伦：E 转数固定，削甲按整次施法处理；W 被动双抗叠层、Q 加速和解除减速尚未模拟。",
    "Darius": "德莱厄斯：Q 外圈统一按命中率近似，未逐帧判定斧柄/斧刃；流血、血怒与 R 刷新窗口是简化实现。",
    "Jax": "贾克斯：反击风暴没有逐次闪避增伤；被动攻速、R 三击和抗性按简化规则处理。",
    "Malphite": "墨菲特：花岗岩护盾、W 护甲按简化规则处理；Q 移速窃取、W 持续锥形伤害未完整复现。",
}


class ValidationError(ValueError):
    """Invalid, unsupported or computationally excessive scenario."""


def _catalog():
    from .catalog import get_catalog
    return get_catalog()


def _finite(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValidationError(f"{label} 必须在 {low} 到 {high} 之间。")
    return value


def _ranked(value, rank, default=0):
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return value[min(max(rank - 1, 0), len(value) - 1)] if value else default
    return value


def _growth(base, per_level, level):
    # Riot's non-linear growth curve, distinct from the reduced movement model.
    return base + per_level * (0.7025 + 0.0175 * (level - 1)) * (level - 1)


def damage_after_resistance(raw, resistance):
    multiplier = 100 / (100 + resistance) if resistance >= 0 else 2 - 100 / (100 - resistance)
    return max(0, raw) * multiplier


def _skill_order(order):
    if not isinstance(order, list) or len(order) != 6:
        raise ValidationError("skill_order 必须包含 1–6 级的六次加点。")
    ranks = dict.fromkeys("QWER", 0)
    for level, slot in enumerate(order, 1):
        if slot not in ranks:
            raise ValidationError("技能加点仅支持 Q/W/E/R。")
        ranks[slot] += 1
        cap = 1 if slot == "R" and level >= 6 else 0 if slot == "R" else (level + 1) // 2
        if ranks[slot] > cap:
            raise ValidationError(f"{level} 级不能这样升级 {slot}。")


def normalize_config(config, catalog=None):
    catalog = _catalog() if catalog is None else catalog
    if not isinstance(catalog, dict) or not isinstance(catalog.get("champions"), dict) or not isinstance(catalog.get("items"), dict):
        raise ValidationError("catalog 必须包含 champions 和 items 对象。")
    if not isinstance(config, dict):
        raise ValidationError("场景需要 JSON 对象。")
    result = deepcopy(DEFAULT_CONFIG)
    for key, value in config.items():
        if key in {"player", "opponent"}:
            if not isinstance(value, dict):
                raise ValidationError(f"{key} 必须是对象。")
            result[key].update(deepcopy(value))
        else:
            result[key] = deepcopy(value)
    # A compact mirror scenario such as {"opponent": {"champion":
    # "Garen"}} is useful for checking random/side bias. When both sides name
    # the same champion, inherit omitted player-side choices so the shorthand
    # really is a mirror instead of silently selecting the opponent defaults.
    if (isinstance(config.get("player"), dict) and isinstance(config.get("opponent"), dict)
            and config["player"].get("champion") == config["opponent"].get("champion")):
        for key in ("level", "skill_order", "items", "rune", "summoners", "policy", "wave", "combo", "hp_ratio", "mana_ratio"):
            if key not in config["opponent"] and key in result["player"]:
                result["opponent"][key] = deepcopy(result["player"][key])
    _finite(result["duration"], "duration", 1, 600)
    _finite(result["start_time"], "start_time", 0, 600)
    _finite(result["accuracy"], "accuracy", 0, 1)
    _finite(result["opponent_accuracy"], "opponent_accuracy", 0, 1)
    _finite(result["distance"], "distance", 0, 1200)
    _finite(result["starting_gold"], "starting_gold", 0, 10000)
    if type(result["seed"]) is not int or not 0 <= result["seed"] < 2**32:
        raise ValidationError("seed 必须是 0–4294967295 的整数。")
    if result["mode"] not in {"lane", "duel"}:
        raise ValidationError("mode 只能是 lane 或 duel。")
    for side in ("player", "opponent"):
        spec = result[side]
        if spec["champion"] not in catalog["champions"]:
            raise ValidationError(f"尚未实现英雄 {spec['champion']}，不能生成可靠技能模拟。")
        champion = catalog["champions"][spec["champion"]]
        if not all(slot in champion.get("abilities", {}) for slot in "QWER"):
            raise ValidationError(f"英雄 {spec['champion']} 的技能模型不完整。")
        if type(spec["level"]) is not int or not 1 <= spec["level"] <= 6:
            raise ValidationError("英雄等级仅支持 1–6。")
        _skill_order(spec["skill_order"])
        if spec["policy"] not in POLICIES or spec["wave"] not in WAVES or spec["rune"] not in RUNES:
            raise ValidationError("未知的对线策略、兵线策略或基石天赋。")
        if not isinstance(spec["summoners"], list) or len(spec["summoners"]) != 2 or len(set(spec["summoners"])) != 2 or any(x not in SUMMONERS for x in spec["summoners"]):
            raise ValidationError("必须选择两个不同的召唤师技能。")
        if not isinstance(spec["combo"], list) or not 1 <= len(spec["combo"]) <= 12 or any(x not in {"Q", "W", "E", "R", "AA"} for x in spec["combo"]):
            raise ValidationError("combo 需要 1–12 项 Q/W/E/R/AA，按顺序循环尝试。")
        if not isinstance(spec["items"], list) or len(spec["items"]) > 6 or any(str(x) not in catalog["items"] for x in spec["items"]):
            raise ValidationError("装备不存在或超出六格。")
        spec["items"] = [str(x) for x in spec["items"]]
        cost = sum(_item_cost(catalog["items"][x]) for x in spec["items"])
        if cost > result["starting_gold"]:
            raise ValidationError(f"{side} 装备共 {cost} 金，超过 starting_gold={result['starting_gold']}。")
        _finite(spec.get("hp_ratio", 1), "hp_ratio", 0.01, 1)
        _finite(spec.get("mana_ratio", 1), "mana_ratio", 0, 1)
    return result


def _item_cost(item):
    gold = item.get("gold", 0)
    return gold.get("total", 0) if isinstance(gold, dict) else gold


@dataclass
class Fighter:
    side: str
    spec: dict
    champion: dict
    catalog: dict
    level: int = 1
    hp: float = 0
    mana: float = 0
    xp: float = 0
    gold: float = 0
    cs: int = 0
    kills: int = 0
    deaths: int = 0
    recalls: int = 0
    damage_dealt: float = 0
    damage_taken: float = 0
    cooldowns: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)
    ranks: dict = field(default_factory=lambda: dict.fromkeys("QWER", 0))
    next_attack: float = 0
    busy_until: float = 0
    absent_until: float = 0
    last_damage: float = -100
    last_combat: float = -100
    combo_index: int = 0
    next_trade: float = 0
    trade_until: float = 0
    x: float = 0
    shield: float = 0
    shield_until: float = 0
    bleed: int = 0
    bleed_until: float = 0
    last_bleed_tick: float = 0
    rune_stacks: int = 0
    rune_expiry: float = 0
    attack_count: int = 0
    potion_charges: int = 0
    potion_until: float = 0
    xp_start: float = 0

    def base_stat(self, key, growth=None):
        stats = self.champion["stats"]
        return _growth(stats.get(key, 0), stats.get(growth or key + "perlevel", 0), self.level)

    def item_stat(self, key):
        aliases = {"hp": "FlatHPPoolMod", "ad": "FlatPhysicalDamageMod", "ap": "FlatMagicDamageMod", "armor": "FlatArmorMod", "mr": "FlatSpellBlockMod", "attack_speed": "PercentAttackSpeedMod", "lifesteal": "PercentLifeStealMod", "mana": "FlatMPPoolMod"}
        return sum(self.catalog["items"][x].get("stats", {}).get(key, self.catalog["items"][x].get("stats", {}).get(aliases.get(key, ""), 0)) for x in self.spec["items"])

    @property
    def item_value(self):
        """Value of the selected inventory, used so build searches are fair.

        Starting gold is reduced by purchases when the fighter is created. The
        score must add that inventory value back; otherwise a candidate that
        buys a stronger item is penalised by its purchase price before combat
        even starts.
        """
        return sum(_item_cost(self.catalog["items"][x]) for x in self.spec["items"])

    @property
    def max_hp(self):
        return self.base_stat("hp") + self.item_stat("hp") + self.effects.get("grasp_hp", 0)

    @property
    def max_mana(self):
        return self.base_stat("mp") + self.item_stat("mana")

    @property
    def bonus_ad(self):
        return self.item_stat("ad") + (self.rune_stacks * (1.08 + 0.06 * (self.level - 1)) if self.spec["rune"] == "conqueror" else 0) + self.effects.get("noxian_might", 0)

    @property
    def ad(self):
        return self.base_stat("attackdamage") + self.bonus_ad

    @property
    def armor(self):
        value = self.base_stat("armor") + self.item_stat("armor")
        if self.spec["champion"] == "Malphite" and self.ranks["W"]:
            ability = self.champion["abilities"].get("W", {})
            ratio = _ranked(ability.get("passive_armor_ratio", .1), self.ranks["W"])
            value *= 1 + ratio
        if self.effects.get("jax_r_until", 0) > 0:
            value += self.effects.get("jax_r_armor", 0)
        return value

    @property
    def magic_resist(self):
        value = self.base_stat("spellblock") + self.item_stat("mr")
        if self.effects.get("jax_r_until", 0) > 0:
            value += self.effects.get("jax_r_mr", 0)
        return value

    @property
    def attack_speed(self):
        bonus = self.champion["stats"].get("attackspeedperlevel", 0) * (0.7025 + 0.0175 * (self.level - 1)) * (self.level - 1) / 100
        if self.spec["champion"] == "Jax":
            bonus += min(8, self.effects.get("jax_stacks", 0)) * (0.035 + self.level * 0.0025)
        return min(2.5, self.champion["stats"].get("attackspeed", 0.65) * (1 + bonus + self.item_stat("attack_speed")))

    def summary(self):
        return {"champion": self.spec["champion"], "level": self.level, "hp": round(max(0, self.hp), 1), "max_hp": round(self.max_hp, 1),
                "mana": round(self.mana, 1), "max_mana": round(self.max_mana, 1), "cs": self.cs, "gold": round(self.gold, 1), "xp": round(self.xp, 1),
                "kills": self.kills, "deaths": self.deaths, "damage_dealt": round(self.damage_dealt, 1), "damage_taken": round(self.damage_taken, 1), "recalls": self.recalls,
                "net_worth": round(self.gold + self.item_value, 1), "skill_ranks": dict(self.ranks), "shield": round(self.shield, 1), "position": round(self.x, 1)}


class LaneSimulation:
    DT = 0.25
    XP_THRESHOLDS = [0, 280, 660, 1140, 1720, 2400]

    def __init__(self, config, catalog):
        self.catalog = catalog
        self.config = normalize_config(config, catalog)
        self.rng = random.Random(self.config["seed"])
        self.now = self.config["start_time"]
        self.end = self.now + self.config["duration"]
        self.timeline = []
        self.snapshots = []
        self.wave = {"position": 500., "blue": [], "red": []}
        self.next_wave = self.now if self.config["mode"] == "lane" else math.inf
        self.wave_number = max(1, int(max(0, self.now - 90) / 30) + 1)
        self.pending = []
        self.fighters = []
        for side, direction in (("player", -1), ("opponent", 1)):
            spec = self.config[side]
            fighter = Fighter(side, spec, self.catalog["champions"][spec["champion"]], self.catalog, level=spec["level"])
            fighter.hp = fighter.max_hp * spec.get("hp_ratio", 1)
            fighter.mana = fighter.max_mana * spec.get("mana_ratio", 1)
            fighter.xp = self.XP_THRESHOLDS[fighter.level - 1]
            fighter.xp_start = fighter.xp
            fighter.gold = self.config["starting_gold"] - sum(_item_cost(self.catalog["items"][x]) for x in spec["items"])
            fighter.x = 500 + direction * self.config["distance"] / 2
            fighter.potion_charges = sum(1 for x in spec["items"] if x == "2003")
            for slot in spec["skill_order"][:fighter.level]:
                fighter.ranks[slot] += 1
            if spec["champion"] == "Malphite":
                fighter.shield = fighter.max_hp * fighter.champion.get("passive", {}).get("shield_ratio", .1)
                fighter.shield_until = math.inf
            self.fighters.append(fighter)

    def event(self, event, actor=None, target=None, value=None, text=""):
        if len(self.timeline) < 2500:
            self.timeline.append({"time": round(self.now, 2), "event": event, "actor": actor.side if isinstance(actor, Fighter) else actor,
                                  "target": target.side if isinstance(target, Fighter) else target, "value": round(value, 2) if isinstance(value, (float, int)) else value, "text": text})

    def active(self, fighter):
        return fighter.hp > 0 and fighter.absent_until <= self.now

    def heal(self, fighter, amount):
        if fighter.effects.get("grievous_until", 0) > self.now:
            amount *= 0.6
        old = fighter.hp
        fighter.hp = min(fighter.max_hp, fighter.hp + max(0, amount))
        return fighter.hp - old

    def hit(self, attacker, target, raw, kind="physical", source="AA", basic=False):
        if not self.active(target):
            return 0
        if basic and target.effects.get("dodge_until", 0) > self.now:
            self.event("dodge", target, attacker, text="反击风暴闪避普攻")
            return 0
        if attacker and attacker.effects.get("exhaust_until", 0) > self.now:
            raw *= 0.65
        if attacker and attacker.effects.get("pta_amp_until", 0) > self.now:
            raw *= 1.08
        resist = target.armor if kind == "physical" else target.magic_resist
        if kind == "physical":
            if target.effects.get("armor_shred_until", 0) > self.now:
                resist *= 1 - target.effects.get("armor_shred_value", .25)
            if attacker and attacker.spec["champion"] == "Darius" and attacker.ranks["E"]:
                ability = attacker.champion["abilities"]["E"]
                resist *= 1 - _ranked(ability.get("armor_pen", [0.15, .2, .25, .3, .35]), attacker.ranks["E"])
        damage = raw if kind == "true" else damage_after_resistance(raw, resist)
        if kind != "true" and target.effects.get("reduction_until", 0) > self.now:
            damage *= 1 - target.effects.get("reduction", .3)
        absorbed = min(target.shield, damage)
        target.shield -= absorbed
        damage -= absorbed
        actual = min(target.hp, damage)
        target.hp -= actual
        target.damage_taken += actual
        target.last_damage = self.now
        target.last_combat = self.now
        if attacker:
            attacker.damage_dealt += actual
            attacker.last_combat = self.now
            if attacker.spec["rune"] == "conqueror" and source not in {"bleed", "ignite", "comet"}:
                attacker.rune_stacks = min(12, attacker.rune_stacks + 2)
                attacker.rune_expiry = self.now + 5
                if attacker.rune_stacks == 12:
                    self.heal(attacker, actual * .05)
            # Zero-damage casts (shields, misses, an empty-rank W) cannot add bleed.
            if actual > 0 and attacker.spec["champion"] == "Darius" and (basic or source in {"Q", "W"}):
                target.bleed = min(5, target.bleed + 1)
                target.bleed_until = self.now + 5
                if target.bleed == 5:
                    passive = attacker.champion.get("passive", {})
                    attacker.effects["noxian_might"] = _ranked(passive.get("bonus_ad", [30, 35, 40, 45, 50]), attacker.level)
                    attacker.effects["noxian_until"] = self.now + 5
        self.event("damage", attacker, target, actual, f"{source} · {kind}" + (f" · 护盾吸收 {absorbed:.0f}" if absorbed else ""))
        if target.hp <= 0:
            target.deaths += 1
            target.absent_until = self.now + 30 + target.level * 2
            target.shield = 0
            target.bleed = 0
            if attacker:
                attacker.kills += 1
                attacker.gold += 300
            self.event("death", attacker, target, text="击杀，按简化复活返线时间计算")
        return actual

    def _basic(self, actor, opponent):
        if self.now < actor.next_attack or abs(actor.x - opponent.x) > actor.champion["stats"].get("attackrange", 125) + 45:
            return False
        actor.next_attack = self.now + 1 / actor.attack_speed
        actor.attack_count += 1
        damage = self.hit(actor, opponent, actor.ad, basic=True)
        self.heal(actor, damage * actor.item_stat("lifesteal"))
        self._on_attack(actor, opponent, damage)
        actor.effects["minion_aggro_until"] = self.now + 2.5
        return True

    def _on_attack(self, actor, opponent, damage):
        if damage <= 0:
            return
        if actor.spec["champion"] == "Jax":
            actor.effects["jax_stacks"] = min(8, actor.effects.get("jax_stacks", 0) + 1)
            actor.effects["jax_until"] = self.now + 2.5
            if actor.ranks["R"] and actor.attack_count % 3 == 0:
                self.hit(actor, opponent, _ranked(actor.champion["abilities"]["R"].get("onhit_damage", 80), actor.ranks["R"]) + actor.item_stat("ap") * .6, "magic", "R被动")
        rune = actor.spec["rune"]
        if rune == "press_the_attack":
            actor.rune_stacks += 1
            actor.rune_expiry = self.now + 4
            if actor.rune_stacks >= 3 and actor.cooldowns.get("rune", 0) <= self.now:
                self.hit(actor, opponent, 40 + 7 * (actor.level - 1), "physical", "强攻")
                actor.effects["pta_amp_until"] = self.now + 6
                actor.cooldowns["rune"] = self.now + 6
                actor.rune_stacks = 0
        elif rune == "grasp" and self.now - actor.effects.get("grasp_last", self.config["start_time"] - 4) >= 4:
            self.hit(actor, opponent, actor.max_hp * .035, "magic", "不灭之握")
            self.heal(actor, actor.max_hp * .013)
            actor.effects["grasp_hp"] = actor.effects.get("grasp_hp", 0) + 5
            actor.effects["grasp_last"] = self.now
        elif rune == "fleet" and actor.cooldowns.get("rune", 0) <= self.now:
            self.heal(actor, 10 + actor.level * 3 + actor.bonus_ad * .1)
            actor.cooldowns["rune"] = self.now + 12
        elif rune == "fleet_footwork" and actor.cooldowns.get("rune", 0) <= self.now:
            self.heal(actor, 10 + actor.level * 3 + actor.bonus_ad * .1)
            actor.cooldowns["rune"] = self.now + 12
        elif rune == "phase_rush":
            actor.rune_stacks += 1
            actor.rune_expiry = self.now + 4
            if actor.rune_stacks >= 3:
                actor.effects["phase_until"] = self.now + 3
                actor.rune_stacks = 0

    def _cast(self, actor, opponent, slot):
        rank = actor.ranks[slot]
        if not rank or self.now < actor.cooldowns.get(slot, 0):
            return False
        ability = actor.champion["abilities"][slot]
        cost = _ranked(ability.get("cost", 0), rank)
        if actor.mana < cost:
            return False
        attack_reset = ability.get("auto_reset", False) or (actor.spec["champion"], slot) in {("Garen", "Q"), ("Darius", "W"), ("Jax", "W"), ("Malphite", "W")}
        max_range = ability.get("range", 250)
        max_range = _ranked(max_range, rank)
        if max_range == 0:
            max_range = 250
        if attack_reset:
            max_range = actor.champion["stats"].get("attackrange", 125) + 75
        defensive = slot == "W" and actor.spec["champion"] == "Garen"
        if not defensive and abs(actor.x - opponent.x) > max_range:
            return False
        if defensive and actor.hp > actor.max_hp * .9:
            return False
        actor.mana -= cost
        actor.cooldowns[slot] = self.now + _ranked(ability.get("cooldown", [10]), rank)
        actor.busy_until = self.now + ability.get("cast_time", .25)
        self.event("cast", actor, opponent, text=f"{slot} · {ability.get('name', slot)}")
        if ability.get("shield"):
            bonus_health = max(0, actor.max_hp - actor.base_stat("hp"))
            actor.shield += (_ranked(ability["shield"], rank)
                             + ability.get("shield_hp_ratio", 0) * actor.max_hp
                             + ability.get("shield_bonus_hp_ratio", 0) * bonus_health)
            actor.shield_until = self.now + ability.get("shield_duration", .75)
        if defensive:
            actor.effects.update(reduction_until=self.now + ability.get("reduction_duration", 2),
                                 reduction=_ranked(ability.get("damage_reduction", .3), rank))
        if actor.spec["champion"] == "Jax" and slot == "E":
            actor.effects["dodge_until"] = self.now + 2
        accuracy = self.config["accuracy" if actor.side == "player" else "opponent_accuracy"]
        targeted = attack_reset or ability.get("targeted", False) or (actor.spec["champion"], slot) in {("Darius", "R"), ("Malphite", "Q"), ("Jax", "Q")}
        if not defensive and not targeted and self.rng.random() > accuracy:
            self.event("miss", actor, opponent, text=f"{slot} 未命中")
            return True
        bonus_raw = (_ranked(ability.get("damage", 0), rank) + _ranked(ability.get("ad_ratio", 0), rank) * actor.ad
                     + _ranked(ability.get("bonus_ad_ratio", 0), rank) * actor.bonus_ad + _ranked(ability.get("ap_ratio", 0), rank) * actor.item_stat("ap")
                     + _ranked(ability.get("armor_ratio", 0), rank) * actor.armor)
        bonus_raw += opponent.max_hp * _ranked(ability.get("target_max_hp_ratio", 0), rank)
        bonus_raw += (opponent.max_hp - opponent.hp) * _ranked(ability.get("target_missing_hp_ratio", 0), rank)
        if actor.spec["champion"] == "Darius" and slot == "Q" and abs(actor.x - opponent.x) < ability.get("outer_min_range", 225):
            bonus_raw *= ability.get("inner_ratio", .35)
        raw = bonus_raw
        packet_source = "Q_inner" if actor.spec["champion"] == "Darius" and slot == "Q" and abs(actor.x - opponent.x) < ability.get("outer_min_range", 225) else slot
        if actor.spec["champion"] == "Darius" and slot == "R":
            bleed_amp = _ranked(ability.get("bleed_amp", 0), rank)
            bleed_amp += ability.get("bleed_amp_bonus_ad_ratio", 0) * actor.bonus_ad
            raw += bleed_amp * opponent.bleed
        if attack_reset:
            actor.next_attack = self.now + 1 / actor.attack_speed
            actor.attack_count += 1
            actor.effects["minion_aggro_until"] = self.now + 2.5
        delay = ability.get("delay", 2 if actor.spec["champion"] == "Jax" and slot == "E" else 0)
        ticks = ability.get("ticks", 1)
        channel = ability.get("channel", 0)
        if channel and ticks > 1:
            actor.busy_until = self.now + channel
            if ability.get("damage_per_tick", False):
                raw *= ticks
            for index in range(ticks):
                self.pending.append((self.now + channel * (index + 1) / ticks, actor, opponent, raw / ticks, ability.get("damage_type", "physical"), slot, False))
        elif delay:
            self.pending.append((self.now + delay, actor, opponent, raw, ability.get("damage_type", "physical"), slot, False))
        elif raw > 0 or attack_reset:
            # An empowered attack has two packets: the normal physical hit and
            # the spell's bonus packet. This avoids turning the 1x AD basic hit
            # into magic/true damage when a W/Q tooltip uses that type.
            damage = self.hit(actor, opponent, actor.ad, "physical", slot + "·普攻", basic=True) if attack_reset else 0
            if raw > 0:
                damage += self.hit(actor, opponent, raw, ability.get("damage_type", "physical"), packet_source, basic=False)
            if attack_reset:
                self._on_attack(actor, opponent, damage)
        if ability.get("cc", 0) and not delay:
            opponent.effects["cc_until"] = self.now + ability["cc"]
        if ability.get("slow", 0):
            opponent.effects["slow_until"] = self.now + ability.get("slow_duration", 2)
        if actor.spec["champion"] == "Garen" and slot == "E":
            # The shred is applied only after six completed spins; while the
            # channel is active the target keeps its original armor.
            opponent.effects["armor_shred_pending"] = self.now + (ability.get("channel", 3) * 6 / max(ability.get("ticks", 7), 1))
            opponent.effects["armor_shred_value"] = _ranked(ability.get("armor_shred", .25), rank)
        if actor.spec["champion"] == "Garen" and slot == "Q":
            opponent.effects["silence_until"] = self.now + 1.5
        if actor.spec["champion"] == "Darius" and slot == "E":
            opponent.x = actor.x + (70 if opponent.x > actor.x else -70)
        if actor.spec["champion"] == "Jax" and slot == "R":
            actor.effects["jax_r_armor"] = _ranked(ability.get("armor_bonus", 0), rank)
            actor.effects["jax_r_mr"] = _ranked(ability.get("mr_bonus", 0), rank)
            actor.effects["jax_r_until"] = self.now + ability.get("duration", 8)
        if (actor.spec["champion"], slot) in {("Jax", "Q"), ("Malphite", "R")}:
            actor.x = opponent.x + (-60 if actor.side == "player" else 60)
        healing = ability.get("heal_missing", .15 if actor.spec["champion"] == "Darius" and slot == "Q" else 0)
        q_inner = actor.spec["champion"] == "Darius" and slot == "Q" and abs(actor.x - opponent.x) < ability.get("outer_min_range", 225)
        if healing and not q_inner:
            self.heal(actor, (actor.max_hp - actor.hp) * healing)
        if actor.spec["rune"] == "comet" and raw > 0 and actor.cooldowns.get("rune", 0) <= self.now:
            actor.cooldowns["rune"] = self.now + 20 - actor.level * .5
            if self.rng.random() < accuracy:
                self.hit(actor, opponent, 30 + actor.level * 4 + actor.item_stat("ap") * .05, "magic", "comet")
        return True

    def _summoners(self, actor, opponent):
        for spell in actor.spec["summoners"]:
            if actor.cooldowns.get(spell, 0) > self.now:
                continue
            distance = abs(actor.x - opponent.x)
            if spell == "ignite" and opponent.hp < opponent.max_hp * .48 and distance <= 600:
                actor.cooldowns[spell] = self.now + 180
                opponent.effects["grievous_until"] = self.now + 5
                for offset in range(1, 6):
                    self.pending.append((self.now + offset, actor, opponent, (50 + actor.level * 20) / 5, "true", "ignite", True))
            elif spell == "barrier" and actor.hp < actor.max_hp * .3:
                actor.cooldowns[spell] = self.now + 180
                actor.shield += 100 + actor.level * 20
                actor.shield_until = self.now + 2.5
            elif spell == "exhaust" and distance <= 650 and actor.hp < actor.max_hp * .55:
                actor.cooldowns[spell] = self.now + 240
                opponent.effects["exhaust_until"] = self.now + 3
                opponent.effects["slow_until"] = self.now + 3
            elif spell == "flash" and actor.hp < actor.max_hp * .18 and distance < 350:
                actor.cooldowns[spell] = self.now + 300
                actor.x = max(0, min(1000, actor.x + (-400 if actor.side == "player" else 400)))
                actor.next_trade = self.now + 12
            elif spell == "ghost" and actor.spec["policy"] == "all_in" and distance > 250 and opponent.hp < opponent.max_hp * .65:
                actor.cooldowns[spell] = self.now + 240
                actor.effects["ghost_until"] = self.now + 10
            else:
                continue
            self.event("summoner", actor, opponent, text=SUMMONERS[spell])

    def _decision(self, actor, opponent):
        if not self.active(actor):
            return
        if actor.effects.get("cc_until", 0) > self.now:
            return
        self._summoners(actor, opponent) if self.active(opponent) else None
        if actor.hp < actor.max_hp * .7 and actor.potion_charges and actor.potion_until <= self.now:
            actor.potion_charges -= 1
            actor.potion_until = self.now + 15
            self.event("potion", actor, value=120, text="使用生命药水")
        policy = actor.spec["policy"]
        lane = self.config["mode"] == "lane"
        if lane and actor.hp < actor.max_hp * .16 and self.now - actor.last_damage > 5:
            actor.recalls += 1
            teleport = "teleport" in actor.spec["summoners"] and actor.cooldowns.get("teleport", 0) <= self.now
            actor.absent_until = self.now + (12 if teleport else 30)
            actor.effects["returning"] = 1
            if teleport:
                actor.cooldowns["teleport"] = self.now + 360
            self.event("recall", actor, text="回城补给" + ("并传送返线" if teleport else "并步行返线"))
            return
        health_gate = actor.hp / actor.max_hp > (0.15 if policy == "all_in" else .3)
        wants_trade = self.active(opponent) and health_gate and self.now >= actor.next_trade and policy != "farm"
        if not lane:
            wants_trade = self.active(opponent) and self.now >= actor.next_trade
        if wants_trade and policy in {"short_trade", "poke"}:
            if actor.trade_until == 0:
                actor.trade_until = self.now + (3.5 if policy == "short_trade" else 1)
                actor.combo_index = 0
            elif self.now >= actor.trade_until:
                actor.next_trade = self.now + (8 if policy == "short_trade" else 5)
                actor.trade_until = 0
                wants_trade = False
        own_sign = -1 if actor.side == "player" else 1
        if wants_trade:
            reach = actor.champion["stats"].get("attackrange", 125) + 20
            if policy == "poke":
                learned = [actor.champion["abilities"][x] for x in "QWER" if actor.ranks[x]]
                reach = min(600, max([_ranked(x.get("range", 125), 1) for x in learned] + [125])) * .85
            destination = opponent.x + own_sign * reach
        else:
            destination = self.wave["position"] + own_sign * (220 if actor.hp < actor.max_hp * .3 else 115)
        speed = actor.champion["stats"].get("movespeed", 340)
        if actor.effects.get("slow_until", 0) > self.now:
            speed *= .65
        if actor.effects.get("ghost_until", 0) > self.now:
            speed *= 1.3
        if actor.effects.get("phase_until", 0) > self.now:
            speed *= 1.4
        actor.x += max(-speed * self.DT, min(speed * self.DT, destination - actor.x))
        actor.x = max(0, min(1000, actor.x))
        if self.now < actor.busy_until:
            return
        if wants_trade:
            combo = actor.spec["combo"]
            for _ in range(len(combo)):
                action = combo[actor.combo_index % len(combo)]
                actor.combo_index = (actor.combo_index + 1) % len(combo)
                done = self._basic(actor, opponent) if action == "AA" else (False if actor.effects.get("silence_until", 0) > self.now else self._cast(actor, opponent, action))
                if done:
                    return
        if lane:
            self._farm(actor)

    def _farm(self, actor):
        if self.now < actor.next_attack or abs(actor.x - self.wave["position"]) > 360:
            return
        enemies = self.wave["red" if actor.side == "player" else "blue"]
        enemies = [x for x in enemies if x["hp"] > 0]
        if not enemies:
            return
        target = min(enemies, key=lambda x: x["hp"])
        wave = actor.spec["wave"]
        if wave == "freeze" and target["hp"] > actor.ad:
            return
        if wave == "slow_push" and target["hp"] > actor.ad and self.now < actor.effects.get("push_next", 0):
            return
        actor.effects["push_next"] = self.now + 3
        actor.next_attack = self.now + 1 / actor.attack_speed
        target["hp"] -= actor.ad
        if target["hp"] <= 0:
            self._minion_dies(target, actor, True)
        if actor.spec["champion"] == "Jax":
            actor.effects["jax_stacks"] = min(8, actor.effects.get("jax_stacks", 0) + 1)
            actor.effects["jax_until"] = self.now + 2.5

    def _minion_dies(self, minion, owner, last_hit):
        if minion.get("resolved"):
            return
        minion["resolved"] = True
        if not self.active(owner) or abs(owner.x - self.wave["position"]) > 800:
            return
        owner.xp += minion["xp"]
        if last_hit:
            owner.cs += 1
            owner.gold += minion["gold"]
            self.event("last_hit", owner, value=minion["gold"], text=minion["kind"])
        while owner.level < 6 and owner.xp >= self.XP_THRESHOLDS[owner.level]:
            hp_before, mana_before = owner.max_hp, owner.max_mana
            owner.level += 1
            slot = owner.spec["skill_order"][owner.level - 1]
            owner.ranks[slot] += 1
            owner.hp += owner.max_hp - hp_before
            owner.mana += owner.max_mana - mana_before
            self.event("level_up", owner, value=owner.level, text=f"升至 {owner.level} 级，学习 {slot}")

    def _waves(self):
        if self.now >= self.next_wave:
            self.next_wave += 30
            for team in ("blue", "red"):
                for kind, count, hp, damage, xp, gold in (("近战兵", 3, 477, 12, 60.45, 21), ("远程兵", 3, 296, 24, 29.44, 14), ("炮车", 1 if self.wave_number % 3 == 0 else 0, 912, 41, 93, 60)):
                    for _ in range(count):
                        self.wave[team].append({"kind": kind, "hp": hp, "damage": damage, "xp": xp, "gold": gold, "next": self.now + 1.2})
            self.event("wave_spawn", value=self.wave_number, text=f"第 {self.wave_number} 波兵线抵达（简化刷新）")
            self.wave_number += 1
        teams = [("blue", "red", self.fighters[1], self.fighters[0]), ("red", "blue", self.fighters[0], self.fighters[1])]
        self.rng.shuffle(teams)
        for team, enemy, enemy_champ, ally in teams:
            for minion in self.wave[team]:
                if minion["hp"] <= 0 or self.now < minion["next"]:
                    continue
                minion["next"] = self.now + 1.2
                if enemy_champ.effects.get("minion_aggro_until", 0) > self.now and self.active(enemy_champ) and abs(enemy_champ.x - self.wave["position"]) < 300:
                    self.hit(None, enemy_champ, minion["damage"], source="小兵")
                else:
                    target = next((x for x in self.wave[enemy] if x["hp"] > 0), None)
                    if target:
                        target["hp"] -= minion["damage"]
                        if target["hp"] <= 0:
                            self._minion_dies(target, ally, False)
        for team in ("blue", "red"):
            self.wave[team] = [x for x in self.wave[team] if x["hp"] > 0]
        difference = len(self.wave["blue"]) - len(self.wave["red"])
        self.wave["position"] = max(110, min(890, self.wave["position"] + difference * .9 * self.DT))
        # The turret accelerates wave removal; no turret plate economy is invented.
        if self.wave["position"] <= 130 or self.wave["position"] >= 870:
            team = "red" if self.wave["position"] <= 130 else "blue"
            owner = self.fighters[0] if team == "red" else self.fighters[1]
            if self.wave[team] and self.now >= owner.effects.get("turret_next", 0):
                owner.effects["turret_next"] = self.now + 1
                target = self.wave[team][0]
                target["hp"] -= 200
                if target["hp"] <= 0:
                    self._minion_dies(target, owner, False)
            if not self.wave[team]:
                self.wave["position"] += 10 if team == "red" else -10
        for actor, opponent in (self.fighters, self.fighters[::-1]):
            under_enemy = actor.x > 870 if actor.side == "player" else actor.x < 130
            if self.active(actor) and under_enemy and actor.effects.get("minion_aggro_until", 0) > self.now and actor.effects.get("tower_next", 0) <= self.now:
                actor.effects["tower_next"] = self.now + 1.2
                self.hit(None, actor, 180, source="防御塔")

    def _tick_status(self, actor, opponent):
        # Passive gold accrues during deaths and recalls as well as on the lane.
        if self.now >= 110 and self.config["mode"] == "lane":
            actor.gold += 2.04 * self.DT
        if actor.absent_until and actor.absent_until <= self.now:
            actor.absent_until = 0
            actor.hp, actor.mana = actor.max_hp, actor.max_mana
            actor.x = self.wave["position"] + (-150 if actor.side == "player" else 150)
            actor.effects.clear()
            actor.bleed = 0
            self.event("return", actor, text="补满状态返线")
        if not self.active(actor):
            return
        if actor.shield_until <= self.now:
            actor.shield = 0
        if actor.rune_expiry <= self.now:
            actor.rune_stacks = 0
        if actor.effects.get("jax_until", 0) <= self.now:
            actor.effects.pop("jax_stacks", None)
        if actor.effects.get("noxian_until", 0) <= self.now:
            actor.effects.pop("noxian_might", None)
        if actor.effects.get("jax_r_until", 0) <= self.now:
            actor.effects.pop("jax_r_until", None)
            actor.effects.pop("jax_r_armor", None)
            actor.effects.pop("jax_r_mr", None)
        if actor.effects.get("armor_shred_pending", 0) and actor.effects["armor_shred_pending"] <= self.now:
            actor.effects["armor_shred_until"] = self.now + 6
            actor.effects.pop("armor_shred_pending", None)
        if actor.bleed_until <= self.now:
            actor.bleed = 0
        if actor.bleed and self.now >= actor.last_bleed_tick + 1:
            actor.last_bleed_tick = self.now
            passive = opponent.champion.get("passive", {}) if opponent.spec["champion"] == "Darius" else {}
            base = _ranked(passive.get("damage_level", passive.get("damage", 15)), opponent.level)
            bonus_ratio = passive.get("bonus_ad_ratio", .06)
            # Catalogue values are five-second total per stack; this is the
            # one-second tick packet used by the reduced timeline.
            self.hit(opponent, actor, actor.bleed * (base + opponent.bonus_ad * bonus_ratio) / 5, source="bleed")
        self.heal(actor, actor.base_stat("hpregen") / 5 * self.DT)
        actor.mana = min(actor.max_mana, actor.mana + actor.base_stat("mpregen") / 5 * self.DT)
        if actor.potion_until > self.now:
            self.heal(actor, 120 / 15 * self.DT)
        if actor.spec["champion"] == "Garen" and self.now - actor.last_damage >= 8:
            self.heal(actor, actor.max_hp * (.015 + actor.level * .001) / 5 * self.DT)
        if actor.spec["champion"] == "Malphite" and self.now - actor.last_damage >= 8:
            actor.shield = max(actor.shield, actor.max_hp * actor.champion.get("passive", {}).get("shield_ratio", .1))
            actor.shield_until = math.inf

    def run(self, detailed=True):
        next_snapshot = self.now
        while self.now < self.end - 1e-9:
            for actor, opponent in (self.fighters, self.fighters[::-1]):
                self._tick_status(actor, opponent)
            due, self.pending = [x for x in self.pending if x[0] <= self.now], [x for x in self.pending if x[0] > self.now]
            for _, actor, opponent, raw, kind, source, persistent in due:
                if (persistent or self.active(actor)) and self.active(opponent):
                    self.hit(actor, opponent, raw, kind, source)
                    if actor.spec["champion"] == "Jax" and source == "E":
                        opponent.effects["cc_until"] = self.now + 1
            order = [0, 1]
            self.rng.shuffle(order)
            for index in order:
                self._decision(self.fighters[index], self.fighters[1-index])
            if self.config["mode"] == "lane":
                self._waves()
            if self.now >= next_snapshot and detailed:
                self.snapshots.append({"time": round(self.now, 2), "player": self.fighters[0].summary(), "opponent": self.fighters[1].summary(),
                                       "wave": {"position": round(self.wave["position"], 1), "blue": len(self.wave["blue"]), "red": len(self.wave["red"])}})
                next_snapshot += 5
            self.now += self.DT
            if self.config["mode"] == "duel" and any(x.hp <= 0 for x in self.fighters):
                break
        player, opponent = self.fighters
        hp_difference = player.hp / player.max_hp - opponent.hp / opponent.max_hp
        # Inventory value is restored here because starting gold was spent on
        # the build. This keeps build candidates comparable instead of making
        # an empty inventory win on cash alone.
        net_worth_difference = (player.gold + player.item_value) - (opponent.gold + opponent.item_value)
        score = net_worth_difference + .25 * ((player.xp-player.xp_start) - (opponent.xp-opponent.xp_start)) + hp_difference * 200 + 120 * (player.kills-opponent.kills)
        summary = {"player": player.summary(), "opponent": opponent.summary(), "score": round(score, 2), "winner": "player" if score > 25 else "opponent" if score < -25 else "even",
                   "duration": round(self.now - self.config["start_time"], 2), "cs_diff": player.cs-opponent.cs, "hp_diff": round(hp_difference, 4), "kill_diff": player.kills-opponent.kills,
                   "gold_diff": round(player.gold-opponent.gold, 2), "net_worth_diff": round(net_worth_difference, 2), "xp_diff": round((player.xp-player.xp_start)-(opponent.xp-opponent.xp_start), 2)}
        warnings = list(WARNINGS)
        for actor in self.fighters:
            warnings.extend(actor.champion.get("sim_notes", []))
            if actor.spec["champion"] in CHAMPION_APPROXIMATIONS:
                warnings.append(CHAMPION_APPROXIMATIONS[actor.spec["champion"]])
            for item_id in actor.spec["items"]:
                item = self.catalog["items"][item_id]
                if item.get("modelled_passives"):
                    warnings.append(f"装备 {item.get('name', item_id)} 在本引擎仅结算已接入的基础属性；特殊被动尚未完整校准。")
        return {"config": self.config, "patch": self.catalog.get("patch", "unknown"), "model": MODEL_VERSION, "summary": summary,
                "timeline": self.timeline if detailed else [], "snapshots": self.snapshots, "warnings": list(dict.fromkeys(warnings))}


def simulate(config, catalog=None):
    """Run one deterministic scenario. Optional catalogue supports verified overrides."""
    return LaneSimulation(config, _catalog() if catalog is None else catalog).run()


def optimize(config, catalog=None):
    """Evaluate a finite Cartesian set with shared random seeds, returning its best."""
    catalog = _catalog() if catalog is None else catalog
    base = normalize_config(config, catalog)
    search = config.get("search", {})
    if not isinstance(search, dict):
        raise ValidationError("search 必须是对象。")
    seeds = search.get("seeds", [0, 1, 2, 3, 4])
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= 32 or any(type(x) is not int or not 0 <= x < 2**32 for x in seeds):
        raise ValidationError("search.seeds 需要 1–32 个有效整数种子。")
    if len(set(seeds)) != len(seeds):
        raise ValidationError("search.seeds 不可重复，重复种子不会增加证据。")
    dimensions = {"runes": "rune", "policies": "policy", "waves": "wave", "items": "items", "skill_orders": "skill_order", "summoners": "summoners", "combos": "combo"}
    unknown = set(search) - set(dimensions) - {"seeds", "objective", "max_candidates"}
    if unknown:
        raise ValidationError("未知搜索维度：" + ", ".join(sorted(unknown)))
    objective = search.get("objective", "mean")
    if objective not in {"mean", "robust"}:
        raise ValidationError("objective 仅支持 mean（平均分）或 robust（最差分）。")
    max_candidates = search.get("max_candidates", 256)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 256:
        raise ValidationError("search.max_candidates 需要是 1–256 的整数。")
    keys, choices = [], []
    for plural, singular in dimensions.items():
        values = search.get(plural, [base["player"][singular]])
        if not isinstance(values, list) or not values:
            raise ValidationError(f"search.{plural} 必须是非空候选列表。")
        keys.append(singular)
        choices.append(values)
    total = math.prod(len(values) for values in choices)
    if total > max_candidates or total * len(seeds) > 1024:
        raise ValidationError(f"候选 {total} × 种子 {len(seeds)} 超过上限（256 候选 / 1024 次模拟），请缩小搜索。")
    ranking = []
    configs = []
    # Validate the complete grid before executing, avoiding partial search results.
    for combination in itertools.product(*choices):
        candidate = deepcopy(base)
        candidate.pop("search", None)
        candidate["player"].update(dict(zip(keys, combination)))
        configs.append(normalize_config(candidate, catalog))
    for candidate in configs:
        results = []
        for seed in seeds:
            candidate["seed"] = seed
            results.append(LaneSimulation(candidate, catalog).run(detailed=False)["summary"])
        candidate["seed"] = base["seed"]
        scores = [x["score"] for x in results]
        ranking.append({"config": deepcopy(candidate), "mean_score": round(statistics.fmean(scores), 2), "worst_score": min(scores),
                        "stddev": round(statistics.pstdev(scores), 2), "win_rate": round(sum(x["winner"] == "player" for x in results)/len(results), 3),
                        "mean_cs_diff": round(statistics.fmean(x["cs_diff"] for x in results), 2), "mean_hp_diff": round(statistics.fmean(x["hp_diff"] for x in results), 4),
                        "mean_kill_diff": round(statistics.fmean(x["kill_diff"] for x in results), 2), "seed_scores": dict(zip(map(str, seeds), scores))})
    ranking.sort(key=lambda x: (x["worst_score"] if objective == "robust" else x["mean_score"], x["mean_score"]), reverse=True)
    return {"best": ranking[0], "ranking": ranking, "search": {"candidates": total, "seeds": seeds, "trials": total * len(seeds), "objective": objective,
            "score_formula": "净资产差（金币+已购装备价值） + 0.25×新增经验差 + 200×剩余生命比例差 + 120×击杀差"},
            "patch": catalog.get("patch", "unknown"), "model": MODEL_VERSION, "warnings": list(WARNINGS)}
