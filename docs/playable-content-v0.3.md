# 可玩人生内容包 v0.3

内容库升级为 `0.3.0`：新增 **16 个事件、48 个选择**，共 **65 个事件、195 个选择**。沿用虚构青溪镇、1988 年出生的玩家与四名主要 NPC；这些是有限的手工内容，不代表完整世界，也不会在一局里全部播放。

## 新增事件与真实前提

下表的旗标必须由此前的实际选择或引擎年结建立；缺少前序时，对应后续不能触发。每项三个选择，至少一个在现金和精力为零时仍可执行。

| ID | 标题 | 年龄窗口 | 前序条件 |
|---|---|---|---|
| `teen.repair_request` | 有人看见你会修东西 | 15—26 | repair_interest，技能 ≥ 15 |
| `adult.repair_referral` | 从一张木凳开始的介绍 | 23—46 | repair_project_completed，技能 ≥ 25 |
| `teen.reading_circle` | 借来的书，新的问题 | 12—23 | library_card + school_interest |
| `adult.study_recommendation` | 一篇旧文章带来的邀请 | 23—50 | reading_project + qualification |
| `adult.returned_support` | 周远也想搭把手 | 26—55 | friend_support，周远健在 |
| `adult.friend_boundary` | 互相帮忙，也要能说不 | 34—65 | mutual_support，周远健在 |
| `adult.home_check` | 当年的住房清单 | 30—55 | home_goal，尚未 settled_home |
| `adult.shared_budget` | 搬进去之后的账 | 34—65 | settled_home + budget_reviewed + partnered，陈安健在 |
| `adult.work_pace` | 给工作留多少力气 | 20—60 | 已有非退休职业，尚未 work_pace_chosen |
| `adult.pace_reflection` | 忙了这些年以后 | 30—60 | 当前 push，work_push_seen，work_push_years ≥ 2，已有非退休职业 |
| `later.mentor_return` | 一份旧说明的新问题 | 55—75 | mentor |
| `later.single_network` | 把自己的支持安排说清 | 55—80 | emergency_fund，当前无伴侣、无孩子 |
| `later.neighbor_checkin` | 一通按约而来的问候 | 65—82 | support_circle_confirmed |
| `later.river_notebook` | 把散页装成一本 | 65—82 | shared_notes |
| `later.community_handover` | 你帮过的小屋又换了一班人 | 60—80 | community_participant |
| `later.quiet_accounts` | 以前的准备，今天的日子 | 65—82 | retirement_planned + budget_reviewed，已退休 |

## 因果与状态约定

- **手艺与学习：** 早期兴趣进入具体修整或阅读作品，再产生工作、教学或有限分享的机会。兴趣不替代学识、技能与资格门槛。
- **朋友互助：** 以前帮助过周远，才会出现他主动帮忙的后续；接受或共同分工建立 `mutual_support`，之后仍可协商或暂停。互助不改变既存债务。
- **住房与预算：** `home_goal` 接入住房计划，真正搬迁才设置 `settled_home`。既有 `adult.housing/move`、`adult.housing/prepare` 和 `later.retirement_plan/budget` 三个确实核账的选项，仅追加 `budget_reviewed=true`，原条件和代价不变。内容文件不追写旧人生的经历。
- **工作节奏：** 首次选择设置 `work_pace=steady/push/rest` 与 `work_pace_chosen=true`，不直接制造年度收入。实际收入与恢复代价由引擎按职业结算。反思必须读取引擎记录的 `work_push_seen` 和至少两个实际 `push` 年度；“选择过”不等于“经历过多年”。
- **晚年生活：** 无伴侣、无孩子的人可以建立有限支持网络，再调整联系频率。实际留下的说明形成 `shared_notes`，才可整理、分享或私人保存散页；指导和社区参与也有对应的交接后续。

沿用现有操作与八个行为方向，每个选择最多两条观察。标签描述行动，不是性格分数；锁定选项不能算拒绝。系统恢复事件、年度风险和调度优先级由引擎负责。数值仍是待平衡假设，尚无开放人口或自动生成与审核内容的平台。

## 验证

新增局部内容契约测试位于 `tests/test_causal_chains.py`，五项测试均通过：

1. 16 个新增事件、48 个选择通过当前契约检查。
2. 构造满足前提且资源充分的场景，48 个选项全部可试算。
3. 将现金与精力置零，16 项仍各有可执行退路。
4. 对 15 个因果后续移除关键前序旗标，事件均不可触发；首次工作节奏是明确的入口例外。
5. 三个有指定活人参与的新场景，在相应 NPC 死亡后均不可出现或执行。

运行：

```powershell
python -X utf8 -m unittest discover -s tests -p test_causal_chains.py -v
```

这些测试使用独立声明的局部状态，**不模拟完整前史，也不证明真实调度必然到达每条链**。完整人生、旧存档迁移和经济平衡仍由项目整体测试验证。
