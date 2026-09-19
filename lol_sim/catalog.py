"""Patch-pinned data catalog for the 1-6 level top-lane lab.

Numbers are sourced from Riot Data Dragon 16.18.1 (the PC game 26.18 data
snapshot) and simplified for a deterministic lane model. The catalog exposes
provenance and limitations so callers can distinguish measured data from
model assumptions.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent / "data"
PATCH = "26.18"
DDRAGON_VERSION = "16.18.1"


def _raw_stats(champion: str) -> dict[str, Any]:
    path = ROOT / f"{champion}.en_US.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload["data"][champion]
    stats = source["stats"]
    # Keep a small, explicit schema that the engine can validate.
    return {
        "hp": stats["hp"], "hpperlevel": stats["hpperlevel"],
        "mp": stats["mp"], "mpperlevel": stats["mpperlevel"],
        "attackdamage": stats["attackdamage"], "attackdamageperlevel": stats["attackdamageperlevel"],
        "armor": stats["armor"], "armorperlevel": stats["armorperlevel"],
        "spellblock": stats["spellblock"], "spellblockperlevel": stats["spellblockperlevel"],
        "attackspeed": stats["attackspeed"], "attackspeedperlevel": stats["attackspeedperlevel"],
        "hpregen": stats["hpregen"], "hpregenperlevel": stats["hpregenperlevel"],
        "mpregen": stats["mpregen"], "mpregenperlevel": stats["mpregenperlevel"],
        "attackrange": stats["attackrange"], "movespeed": stats["movespeed"],
    }


def _spell(name: str, *, damage=None, ad_ratio=0.0, bonus_ad_ratio=0.0,
           ap_ratio=0.0, cooldown=None, cost=None, damage_type="physical",
           range_=300, **extra) -> dict[str, Any]:
    return {
        "name": name,
        "damage": damage or [0, 0, 0, 0, 0],
        "ad_ratio": ad_ratio,
        "bonus_ad_ratio": bonus_ad_ratio,
        "ap_ratio": ap_ratio,
        "cooldown": cooldown or [0, 0, 0, 0, 0],
        "cost": cost or [0, 0, 0, 0, 0],
        "range": range_,
        "damage_type": damage_type,
        "cast_time": 0.25,
        **extra,
    }


def _champions() -> dict[str, dict[str, Any]]:
    return {
        "Garen": {
            "id": "Garen", "name": "盖伦", "role": "近战战士",
            "stats": _raw_stats("Garen"),
            "abilities": {
                "Q": _spell("致命打击", damage=[30, 60, 90, 120, 150], ad_ratio=.5,
                    cooldown=[8, 8, 8, 8, 8], auto_reset=True, silence=1.5,
                    notes="强化下一次普攻；解除减速"),
                "W": _spell("勇气", cooldown=[22, 19.5, 17, 14.5, 12], shield=[65, 85, 105, 125, 145], shield_bonus_hp_ratio=.18,
                    shield_duration=.75, reduction_duration=4, damage_reduction=[.25, .29, .33, .37, .41], tenacity=.6,
                    notes="前0.75秒盾与60%韧性，随后减伤持续至4秒；被动击杀单位叠双抗未在模型中逐个计数"),
                "E": _spell("审判", damage=[4, 7, 10, 13, 16], ad_ratio=[.01, .02, .03, .04, .05],
                    cooldown=[9, 8.25, 7.5, 6.75, 6], duration=3, channel=3, ticks=7,
                    damage_per_tick=True, armor_shred=.25, notes="每级7次旋转伤害；最近目标伤害提高25%，未在引擎中展开"),
                "R": _spell("德玛西亚正义", damage=[150, 250, 350], ap_ratio=0,
                    cooldown=[120, 100, 80], damage_type="true", missing_health_ratio=.25,
                    range_=400, target_missing_hp_ratio=[.25, .30, .35], notes="按目标已损失生命值增加真实伤害"),
            },
            "passive": {"name": "坚韧", "regen_after": 8, "regen_ratio": .015},
            "recommended": {"skill_order": ["E", "Q", "W", "E", "E", "R"],
                "runes": ["conqueror", "grasp"], "summoners": [["flash", "ignite"], ["flash", "teleport"]],
                "items": [["1055"], ["1055", "3047"], ["1055", "3067"]]},
        },
        "Darius": {
            "id": "Darius", "name": "德莱厄斯", "role": "近战战士",
            "stats": _raw_stats("Darius"),
            "abilities": {
                "Q": _spell("大杀四方", damage=[50, 80, 110, 140, 170], ad_ratio=1.0,
                    cooldown=[9, 8, 7, 6, 5], cost=[25, 30, 35, 40, 45], outer_ratio=1.0,
                    inner_ratio=.35, heal_missing=.15, range_=425,
                    notes="外圈命中伤害/回血并施加流血；内圈低伤且不叠层"),
                "W": _spell("致残打击", cooldown=[5, 5, 5, 5, 5], cost=[40]*5,
                    auto_reset=True, slow=.9, ad_ratio=[.4, .45, .5, .55, .6], range_=300,
                    notes="强化普攻并重置攻击"),
                "E": _spell("无情铁手", cooldown=[26, 23.5, 21, 18.5, 16], cost=[70,60,50,40,30],
                    armor_pen=[.15, .2, .25, .3, .35], range_=535, notes="被动护甲穿透；主动拉回"),
                "R": _spell("诺克萨斯断头台", damage=[125, 250, 375], bonus_ad_ratio=[.75, .75, .75],
                    cooldown=[120, 100, 80], cost=[100,100,0], damage_type="true", range_=460,
                    bleed_amp=[25, 50, 75], bleed_amp_bonus_ad_ratio=.15, notes="每层流血额外25/50/75 (+15% bonus AD)真伤；击杀可刷新"),
            },
            "passive": {"name": "出血", "stacks": 5, "duration": 5,
                "damage": [16.25, 20, 23.75, 27.5, 31.25, 35, 37.5],
                "bonus_ad": [30, 50, 70, 90, 110, 130, 150, 170, 190, 210, 230],
                "bonus_ad_ratio": .075},
            "recommended": {"skill_order": ["Q", "W", "E", "Q", "Q", "R"],
                "runes": ["conqueror", "phase_rush"], "summoners": [["flash", "ghost"], ["flash", "teleport"]],
                "items": [["1055"], ["1055", "3047"], ["1055", "3071"]]},
        },
        "Jax": {
            "id": "Jax", "name": "贾克斯", "role": "近战战士",
            "stats": _raw_stats("Jax"),
            "abilities": {
                "Q": _spell("跳斩", damage=[65, 105, 145, 185, 225], bonus_ad_ratio=1.0,
                    ap_ratio=.6, cooldown=[8, 7.5, 7, 6.5, 6], cost=[50]*5, range_=700),
                "W": _spell("蓄力一击", damage=[50, 85, 120, 155, 190], ap_ratio=.6, damage_type="magic",
                    cooldown=[7, 6, 5, 4, 3], cost=[30]*5, auto_reset=True, range_=300),
                "E": _spell("反击风暴", damage=[40, 70, 100, 130, 160], ap_ratio=.7, target_max_hp_ratio=.04,
                    cooldown=[17, 15, 13, 11, 9], cost=[50,60,70,80,90], duration=2,
                    dodge=True, stun=1, damage_type="magic", range_=300, notes="闪避普攻后晕眩；每次闪避提高20%，上限100%"),
                "R": _spell("宗师之威", damage=[100, 175, 250], onhit_damage=[75, 130, 185], ap_ratio=1.0,
                    cooldown=[110, 100, 90], cost=[100]*3, onhit_every=3,
                    armor_bonus=[45, 60, 75], mr_bonus=[27, 36, 45], duration=8, damage_type="magic", range_=375),
            },
            "passive": {"name": "无情突袭", "attack_speed_per_stack": .03, "stacks": 8},
            "recommended": {"skill_order": ["E", "Q", "W", "Q", "Q", "R"],
                "runes": ["grasp", "conqueror"], "summoners": [["flash", "ignite"], ["flash", "teleport"]],
                "items": [["1055"], ["1055", "3047"], ["1055", "3078"]]},
        },
        "Malphite": {
            "id": "Malphite", "name": "墨菲特", "role": "坦克/法师",
            "stats": _raw_stats("Malphite"),
            "abilities": {
                "Q": _spell("地震碎片", damage=[70, 120, 170, 220, 270], ap_ratio=.6,
                    cooldown=[8]*5, cost=[70,75,80,85,90], damage_type="magic", range_=625,
                    notes="偷取移速 3 秒"),
                "W": _spell("雷霆拍击", damage=[30, 40, 50, 60, 70], ap_ratio=.2,
                    cooldown=[10, 9.5, 9, 8.5, 8], cost=[30,35,40,45,50],
                    auto_reset=True, cone_damage_ratio=.15, armor_ratio=.15, passive_armor_ratio=[.10, .15, .20, .25, .30], shield_multiplier=3,
                    range_=400),
                "E": _spell("大地震颤", damage=[60, 95, 130, 165, 200], ap_ratio=.6,
                    cooldown=[7]*5, cost=[50,55,60,65,70], damage_type="magic", armor_ratio=.4,
                    attack_speed_slow=[.30, .35, .40, .45, .50], slow_duration=3, range_=400),
                "R": _spell("势不可挡", damage=[200, 300, 400], ap_ratio=.9,
                    cooldown=[130, 115, 100], cost=[100]*3, damage_type="magic", range_=1000,
                    knockup=1.5),
            },
            "passive": {"name": "花岗岩护盾", "shield_ratio": .10, "recharge": 8},
            "recommended": {"skill_order": ["Q", "E", "W", "Q", "Q", "R"],
                "runes": ["comet", "grasp"], "summoners": [["flash", "teleport"], ["flash", "ignite"]],
                "items": [["1056"], ["1056", "3047"], ["1056", "3068"]]},
        },
    }


def _items() -> dict[str, dict[str, Any]]:
    # Stats are the parts used by the lane model. Item proc passives are omitted
    # until the engine has an explicit implementation for their patch values.
    return {
        "1054": {"id": "1054", "name": "多兰之盾", "gold": 450, "stats": {"hp": 110, "hp_regen": .8}},
        "1055": {"id": "1055", "name": "多兰之刃", "gold": 450, "stats": {"hp": 80, "ad": 10, "lifesteal": .025}},
        "1056": {"id": "1056", "name": "多兰之戒", "gold": 400, "stats": {"hp": 90, "ap": 18}},
        "1036": {"id": "1036", "name": "长剑", "gold": 350, "stats": {"ad": 10}},
        "1028": {"id": "1028", "name": "红水晶", "gold": 400, "stats": {"hp": 150}},
        "3047": {"id": "3047", "name": "铁板靴", "gold": 1200, "stats": {"armor": 25, "movespeed": 45}},
        "3111": {"id": "3111", "name": "水银之靴", "gold": 1250, "stats": {"mr": 20, "movespeed": 45, "tenacity": .3}},
        "3009": {"id": "3009", "name": "轻灵之靴", "gold": 1000, "stats": {"movespeed": 55}},
        "3067": {"id": "3067", "name": "燃烧宝石", "gold": 800, "stats": {"hp": 200, "haste": 10}},
        "3071": {"id": "3071", "name": "黑色切割者", "gold": 3000, "stats": {"hp": 400, "ad": 45, "haste": 20}},
        "3078": {"id": "3078", "name": "三相之力", "gold": 3333, "stats": {"hp": 333, "ad": 36, "attack_speed": .3, "haste": 15}},
        "3068": {"id": "3068", "name": "日炎圣盾", "gold": 2800, "stats": {"hp": 350, "armor": 50, "haste": 10}},
        "2003": {"id": "2003", "name": "生命药水", "gold": 50, "stats": {}},
    }


def _runes() -> dict[str, dict[str, Any]]:
    return {
        "conqueror": {"name": "征服者", "tree": "精密", "effects": {"adaptive_per_stack": 1.08, "stacks": 12, "heal_at_max": .05}, "notes": "持续战斗叠层；模型以命中事件近似"},
        "grasp": {"name": "不灭之握", "tree": "坚决", "effects": {"magic_damage_max_hp": .03, "heal_max_hp": .013, "hp_melee": 7}, "notes": "战斗中每4秒充能一次"},
        "press_the_attack": {"name": "强攻", "tree": "精密", "effects": {"amp": .08, "hits": 3}},
        "fleet": {"name": "迅捷步法", "tree": "精密", "effects": {"heal": 0.0, "move_speed": .2}},
        "comet": {"name": "奥术彗星", "tree": "巫术", "effects": {"damage": 30, "ap_ratio": .05, "ad_ratio": .1, "cooldown": 20}, "notes": "技能命中后触发；落点命中在模型中按 accuracy 处理"},
        "phase_rush": {"name": "相位猛冲", "tree": "巫术", "effects": {"move_speed": .4, "hits": 3}},
        "fleet_footwork": {"name": "迅捷步法", "tree": "精密", "effects": {"move_speed": .2}},
    }


def _summoners() -> dict[str, dict[str, Any]]:
    return {
        "flash": {"name": "闪现", "cooldown": 300, "effect": "位移/追击/脱离", "modelled": False},
        "ignite": {"name": "引燃", "cooldown": 180, "damage": 410, "damage_type": "true", "duration": 5, "modelled": True},
        "teleport": {"name": "传送", "cooldown": 360, "effect": "回线/支援", "modelled": "economy_only"},
        "ghost": {"name": "幽灵疾步", "cooldown": 240, "effect": "持续移速", "modelled": "engage_probability"},
        "barrier": {"name": "屏障", "cooldown": 180, "shield": 120, "modelled": True},
        "exhaust": {"name": "虚弱", "cooldown": 210, "effect": "减速/减伤", "modelled": "damage_reduction"},
    }


def get_catalog() -> dict[str, Any]:
    champions = _champions()
    return {
        "patch": PATCH,
        "ddragon_version": DDRAGON_VERSION,
        "model": "approximate-lane-v1",
        "checked_at": "2026-09-18",
        "sources": [
            {"title": "Riot Patch 26.18 Notes", "url": "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-18-notes/", "kind": "patch", "status": "official"},
            {"title": "Riot Data Dragon", "url": "https://ddragon.leagueoflegends.com/cdn/16.18.1/data/en_US/champion/", "kind": "champion-data", "status": "official-static-snapshot"},
            {"title": "Riot Patch Schedule", "url": "https://support-leagueoflegends.riotgames.com/hc/en-us/articles/360018987893-Patch-Schedule", "kind": "schedule", "status": "official"},
            {"title": "U.GG Darius rune table", "url": "https://u.gg/lol/champions/darius/runes-table", "kind": "build-statistics", "status": "community-aggregate"},
            {"title": "U.GG Jax build", "url": "https://u.gg/lol/champions/jax/build", "kind": "build-statistics", "status": "community-aggregate"},
            {"title": "U.GG Malphite build", "url": "https://u.gg/lol/champions/malphite/build", "kind": "build-statistics", "status": "community-aggregate"},
        ],
        "data_quality": {
            "scope": "PC Summoner's Rift top-lane levels 1-6",
            "official_values": "base stats and spell tooltip snapshots",
            "approximation": "animation, hitbox, wave aggro, exact rune/item proc scripts, jungle pressure and player mind games are simplified",
            "optimization_claim": "best among submitted model candidates and seeds; not a universal matchup truth",
            "refresh": "re-run the Data Dragon fetch and update checked_at when a new patch is live",
        },
        "champions": champions,
        "items": _items(),
        "runes": _runes(),
        "summoners": _summoners(),
        "policies": {"farm": "只补刀，避免主动换血", "short_trade": "短换血后拉开", "all_in": "有击杀线时持续追击", "poke": "远程/技能消耗后控线"},
        "waves": {"freeze": "塔前控线", "slow_push": "叠大波推线", "fast_push": "快速清线抢回合"},
        "defaults": {
            "player": {"champion": "Garen", "level": 1, "skill_order": ["E", "Q", "W", "E", "E", "R"], "items": ["1055"], "rune": "conqueror", "summoners": ["flash", "ignite"], "policy": "short_trade", "wave": "freeze", "combo": ["Q", "AA", "E"]},
            "opponent": {"champion": "Darius", "level": 1, "skill_order": ["Q", "W", "E", "Q", "Q", "R"], "items": ["1055"], "rune": "conqueror", "summoners": ["flash", "ghost"], "policy": "all_in", "wave": "freeze", "combo": ["Q", "AA", "W", "E"]},
            "duration": 180, "seed": 42, "start_time": 90, "accuracy": .8, "opponent_accuracy": .75, "distance": 300, "mode": "lane",
        },
        "controls": {"levels": [1, 2, 3, 4, 5, 6], "duration_range": [30, 300], "accuracy_range": [0, 1], "supported_champions": list(champions)},
    }


def load_catalog() -> dict[str, Any]:
    return get_catalog()


def clone_catalog() -> dict[str, Any]:
    return copy.deepcopy(get_catalog())
