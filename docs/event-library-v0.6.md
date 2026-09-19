# 事件库评价覆盖 v0.6

## 目标

事件库不再只回答“这个事件能不能触发”，还要回答“它在什么评价情境下观察了哪个行为”。本版保留事件原有的规则、资源消耗和因果链，只增加可审计的画像元数据。

## 新增元数据

个人事件和社会响应事件现在统一包含：

- `episode_group`：同一条剧情连续追问时使用同一个分组，避免把一个处境的多次后续选择当作多次独立人格证据。
- `assessment_context.life_stage`：童年、少年、青年、中年、晚年或跨阶段。
- `assessment_context.pressure_band`：低、中、高压力；高压力用于生计、灾害、健康和其他基本需求受到威胁的情境。
- `assessment_context.relationship_scope`：自我、家庭、朋友、邻里、机构或群体。
- `assessment_context.scale`：个人、家庭或社区尺度。
- `assessment_context.information_level`：已知、部分已知或不确定。
- `assessment_context.time_horizon`：即时、短期或长期。
- 选择观察项的 `facet`：对应八个维度中的三个工作子维度之一。

这些字段是编辑者对事件的声明，不改变选项是否可执行，也不把结果倒推成动机。

## 覆盖矩阵

`content/personality-coverage.json` 为八个维度各列出至少四个真实事件入口，并同时标记年龄、压力、关系尺度、信息条件和时间范围。静态检查会验证：

1. 引用的事件编号存在；
2. 每个维度都有足够的事件入口；
3. 矩阵列出的维度确实出现在事件选项的观察标注中；
4. 所有画像观察项都有合法子维度。

运行：

```powershell
python -X utf8 -m game.content_check
python -X utf8 -m game.personality_report --output reports/personality-coverage-v0.6
```

报告同时输出 JSON 和 Markdown，统计每个维度的事件数、标注选择数、子维度、年龄阶段、压力、关系和信息条件分布。它描述的是**内容入口覆盖**，不是玩家人格结论。

## 仍需扩展的内容

覆盖矩阵保证每个维度有入口，但不声称穷尽现实。下一轮内容制作应优先补充：

- 同一维度在相同信息条件下的低/中/高压力成对事件；
- 同一行为在亲属、朋友、陌生人和机构关系中的对照；
- 不同生命阶段的重复机会；
- 现实中会出现但不应美化的操纵、背叛、剥削、违法和伤害行为，并为每类行为写清受害者状态、法律后果和可见信息边界；
- 同一 `episode_group` 的后果链，确保 NPC 死亡、离开或关系断裂后不会再次作为可行动角色出现。
