# LOL 上路 1–6 级对线实验室

这是一个独立于原有“浮生”项目的本地实验器。它把一局上路前六级拆成可重复的配置，支持四位首批英雄：盖伦、德莱厄斯、贾克斯、墨菲特。每一局可以指定等级、技能加点、技能循环、基石天赋、召唤师技能、出门装备、对线策略、兵线处理、命中率、起始距离和随机种子。

截至 2026-09-18，PC 正式服按 Riot 日程仍是 26.18（26.18 于 2026-09-10 发布，26.19 计划 2026-09-23）。英雄基础属性与技能快照来自 Riot Data Dragon 16.18.1；补丁页、静态数据地址和统计站链接会随 `/api/catalog` 一起返回。当前目录不是实时客户端数据，补丁更新后需要重新抓取并复核。

## 启动

在项目根目录运行：

```powershell
python -X utf8 -m lol_sim serve --port 8767
```

然后打开 <http://127.0.0.1:8767/>。Windows 也可以双击 [启动上路模拟器.cmd](../启动上路模拟器.cmd)。原有的人生游戏仍使用 8766 端口，这个模拟器使用 8767。

## 直接调用

```python
from lol_sim import simulate, optimize

scenario = {
    "player": {
        "champion": "Garen", "level": 1,
        "skill_order": ["E", "Q", "W", "E", "E", "R"],
        "items": ["1055"], "rune": "conqueror",
        "summoners": ["flash", "ignite"],
        "policy": "short_trade", "wave": "freeze",
        "combo": ["Q", "AA", "E"],
    },
    "opponent": {
        "champion": "Darius", "level": 1,
        "skill_order": ["Q", "W", "E", "Q", "Q", "R"],
        "items": ["1055"], "rune": "conqueror",
        "summoners": ["flash", "ghost"],
        "policy": "all_in", "wave": "freeze",
        "combo": ["Q", "AA", "W", "E"],
    },
    "duration": 180, "start_time": 90, "accuracy": 0.8,
    "opponent_accuracy": 0.75, "distance": 300,
    "mode": "lane", "seed": 42, "starting_gold": 500,
}

one_game = simulate(scenario)
search = optimize({**scenario, "search": {
    "runes": ["conqueror", "grasp"],
    "policies": ["farm", "short_trade", "all_in"],
    "waves": ["freeze", "slow_push"],
    "seeds": [0, 1, 2, 3],
    "objective": "robust",
}})
print(one_game["summary"])
print(search["best"])
```

CLI 等价入口：

```powershell
python -X utf8 -m lol_sim catalog --output reports/lol/catalog-26.18.json
python -X utf8 -m lol_sim simulate --config examples/lol-garen-vs-darius.json --output reports/lol/garen-vs-darius.json
python -X utf8 -m lol_sim optimize --config examples/lol-garen-vs-darius.json --output reports/lol/garen-vs-darius-search.json
```

HTTP 接口是 `GET /api/catalog`、`POST /api/simulate` 和 `POST /api/optimize`。请求体就是上面的 JSON；`optimize` 的搜索维度可以是 `runes`、`policies`、`waves`、`items`、`skill_orders`、`summoners`、`combos`，最多 256 个候选、1024 次候选×种子试验。

## 如何读“最优”

`summary.score` 是模型内的比较分：净资产差（剩余金币加已购装备价值）、新增经验差、剩余生命比例差和击杀差的加权和。`optimize` 在同一个固定对手和同一批随机种子下比较候选，返回均值、最差分、标准差、胜出率、补刀差和击杀差。它回答的是“在这组假设里哪项更稳”，不回答所有玩家、所有打野和所有命中率下的唯一答案。排名只搜索玩家一侧，对手配置保持固定；要换对手，重新提交 `opponent`。

配置中 `accuracy` 和 `opponent_accuracy` 是有意暴露的变量。建议先用 0.7、0.8、0.9 各跑一组，再看最优方案是否稳定；如果排名随命中率轻微变化就反复翻转，实战应按更稳的控线/回合方案执行，而不是只看一次均值。

## 首批对位的实战起点

这些是给模拟器的初始搜索范围，需用你自己的命中率、距离和对手策略重跑：

- 盖伦对德莱厄斯：先按 `E-Q-W-E-E-R`、征服者或不灭之握、塔前控线和短换血测试。Q 沉默后接 E，W 留给外圈 Q、引燃或长换血；德莱厄斯带疾跑并进入五层流血时不要继续追。
- 德莱厄斯对盖伦：按 `Q-W-E-Q-Q-R`、征服者/相位猛冲、闪现+疾跑和控线测试。把 Q 外圈命中率单独跑 0.7/0.8/0.9；没有外圈或五层血怒时，模型不会把断头台当成稳定击杀线。
- 贾克斯对近战 AD：按 E-Q-W-Q-Q-R、征服者或不灭之握、铁板靴前的短换血测试。E 的普攻闪避窗口和 W 强化普攻是核心变量，纯 `all_in` 在较低命中率下通常不如短换血。
- 墨菲特对 AD 近战：按 Q-E-W-Q-Q-R，奥术彗星+多兰戒用于消耗，或不灭之握+多兰盾用于承伤；E 的攻速降低应留给对手准备长换血时使用，六级后再把 R 的命中率纳入搜索。

以上建议来自首批近似机制和常见构筑统计，不是对位保证。未实现的英雄会直接报错，不会被默默替换成通用战士；物品特殊被动、打野、视野、碰撞、塔下逐帧仇恨和动画取消仍在结果警告中明确列出。

四个代表性对位的可复现实验结果保存在 [reports/lol/benchmark-26.18.md](../reports/lol/benchmark-26.18.md)，完整排名在 [benchmark-26.18.json](../reports/lol/benchmark-26.18.json)。它们只用于验证搜索管线和比较方向，不能直接当成排位胜率。

## 数据和测试

当前数据文件在 `lol_sim/data/`，版本登记在 `lol_sim/data/version.json`；目录还保留了中英文 Data Dragon 原始响应，方便复核。运行：

```powershell
python -X utf8 -m unittest discover -s tests -v
```

测试覆盖可复现单局、非法技能加点、未知英雄拒绝、搜索上限、HTTP 接口、CLI、静态页面和同源/请求大小校验。
