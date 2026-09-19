# v0.4 架空世界批量验证

从新历 1 年开始，128 个种子分别推进 82 年。
出现 105 / 120 个宏观事件，形成 128 条不同的事件序列。

每个世界均检查：前提与冷却、按历史重放状态、时间不倒退、模式互斥、指标范围、原输入不变、分段推进及 JSON 接续与一次推进完全一致。

| 领域 | 编写事件 | 本批出现 | 触发总次数 |
| --- | ---: | ---: | ---: |
| 经济与机会 | 6 | 6 | 273 |
| 劳动与就业 | 6 | 6 | 398 |
| 住房与城市 | 6 | 5 | 236 |
| 教育与知识 | 6 | 6 | 293 |
| 公共卫生与照护 | 6 | 3 | 117 |
| 人口与迁移 | 6 | 5 | 149 |
| 文化与共同生活 | 6 | 5 | 258 |
| 信息与传播 | 6 | 5 | 213 |
| 治理与公共能力 | 6 | 6 | 383 |
| 权利与公民生活 | 6 | 5 | 136 |
| 国际贸易与往来 | 6 | 6 | 184 |
| 战争与和平 | 6 | 6 | 190 |
| 能源转型 | 6 | 3 | 203 |
| 食物与农业 | 6 | 5 | 236 |
| 基础设施 | 6 | 6 | 448 |
| 生态与资源 | 6 | 6 | 334 |
| 气候与适应 | 6 | 6 | 647 |
| 自然灾害与修复 | 6 | 6 | 364 |
| 技术与人工智能 | 6 | 6 | 168 |
| 太空与前沿 | 6 | 3 | 18 |

## 出现过的发展模式

- energy：集中供能、分布式供能、混合供能
- governance：集中治理、分散治理、协商治理
- trade：开放贸易、区域贸易、受限贸易
- technology：开放技术网络、平台主导、受限技术网络

## 本批未触发的事件

culture.cultural_closure, energy.advanced_trial, energy.trial_failure, energy.trial_success, food.lowwater_trials, health.infection_wave, health.mobile_care, health.shared_procurement, housing.vacancy_hollowing, information.network_outage, population.mobility_barrier, rights.sunset_review, space.closed_loop_trial, space.outpost_withdrawal, space.research_outpost

覆盖只表示这批确定种子曾触发的资产；未出现不等于不可达，出现也不证明叙事质量、现实真实性或全部未来覆盖。

此报告单独验证宏观世界；个人事件和 NPC 的接续、一致性由单元测试与试玩检查。

## 复现

```powershell
python -X utf8 -m game.world_report --seeds 128 --years 82 --output reports/world-v0.4
```

### 文件 SHA-256

- `game/world.py`：`04ded154bf968f01e28b8225415da97bb3d1ffe6038f7ec27a2e101777799ff7`
- `game/world_report.py`：`3ab60454388d30c9bc6e3fad36dd0bb9093f6757ae4b8a31f3eca56ba6861f1f`
- `content/world-events.json`：`9b04885413063cc2aa0a1c9460f4d3cf4c5100be2a73b5ba4353a688f5a99570`
