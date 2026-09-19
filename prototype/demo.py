"""Generate three reproducible example runs and their factual review report."""
from copy import deepcopy
import json
from pathlib import Path
import sys

from prototype.engine import Engine, ROOT, digest, load_engine, replay


def choice(engine, event_id, option):
    offer = next(o for o in engine.available_events() if o.event_id == event_id)
    return engine.choose(offer, option)


def scenarios():
    runs = []
    normal = load_engine()
    initial = deepcopy(normal.state)
    choice(normal, "friend.loan_request", "lend_partial")
    normal.advance(60)  # Stops at the first due day, 30.
    choice(normal, "friend.loan_due", "accept_repayment")
    runs.append(("提供部分借款，随后整笔归还", initial, normal))

    loss = load_engine()
    initial = deepcopy(loss.state)
    choice(loss, "friend.loan_request", "lend_full")
    loss.advance(5)
    loss.mark_dead("f", "独立于借款选择的演示系统事件；用于检查死亡边界")
    choice(loss, "friend.old_letter", "read")
    loss.advance(60)
    runs.append(("借款后朋友去世，原还款计划取消", initial, loss))

    constrained = load_engine()
    initial = deepcopy(constrained.state)
    initial["persons"]["p"].update(cash=0, energy=0)
    constrained = Engine(initial, constrained.catalog)
    choice(constrained, "friend.loan_request", "decline")
    runs.append(("资金与精力不足，只剩一个可行选项", initial, constrained))
    return runs


def write_reports(output_dir: Path | None = None):
    output = output_dir or ROOT / "reports"
    output.mkdir(parents=True, exist_ok=True)
    markdown = ["# 规则样例运行报告", "", "此报告由 `python -m prototype.demo` 从实际状态与日志生成。三条路径是指定输入的规则演示，尚未构成完整人生或心理测量。", "", "借款本金与转账在原型中真实结算；住房备用金仅为预算目标。本轮没有模拟日常支出、就业收入或完整经济活动。死亡路径是独立的系统测试输入，不能解释为借钱导致死亡。", ""]
    saves = {"format_version":"0.1.0", "ruleset_id":"smalltown-v0.1", "runs":[]}
    for index, (title, initial, engine) in enumerate(scenarios(), 1):
        assert replay(initial, engine.log) == engine.state
        state = engine.state
        player, friend = state["persons"]["p"], state["persons"]["f"]
        markdown.extend([f"## {index}. {title}", "", "| 项目 | 最终状态 |", "| --- | --- |", f"| 日期 | 第 {state['day']} 天 |", f"| 玩家现金 | {player['cash']} |", f"| 朋友现金 | {friend['cash']} |", f"| 朋友健在 | {'是' if friend['alive'] else '否'} |", f"| 人际关系记录 | 保留 {len(state['relationships'])} 条有方向的关系 |", "", "### 事实记录", ""])
        for entry in engine.log:
            payload = entry["payload"]
            if entry["kind"] == "choice":
                markdown.append(f"- 第 {entry['day']} 天：{payload['choice_label']}。证据编号 `decision-{entry['sequence']}`，事件 `{payload['event_id']}`。")
                if payload["cash_cost"]:
                    markdown.append(f"  - 该次实际支出 {payload['cash_cost']} 元，占选择前现金的 {payload['cash_cost_share']:.1%}；选择后{'低于' if payload['below_housing_reserve_after'] else '不低于'}住房预算目标。")
                locked = [x for x in payload["options"] if not x["available"]]
                for option in locked:
                    markdown.append(f"  - 锁定「{option['label']}」：`{option['locked_reason']}`。")
            elif entry["kind"] == "time_advanced":
                markdown.append(f"- 日期推进 {payload['elapsed_days']} 天；请求推进 {payload['requested_days']} 天。途中到期事项会暂停进一步推进。")
            else:
                markdown.append(f"- 第 {entry['day']} 天：系统记录 {state['persons'][payload['person_id']]['name']} 去世。{payload['cause']}。")
        markdown.extend(["", "### 债务与计划", ""])
        if not state["loans"]:
            markdown.append("- 没有建立债务。")
        for loan in state["loans"].values():
            unpaid = 0 if loan["status"] == "repaid" else loan["amount"]
            markdown.append(f"- `{loan['id']}`：固定本金 {loan['amount']}，未偿本金 {unpaid}，状态 `{loan['status']}`。")
        for task in state["tasks"]:
            markdown.append(f"- `{task['id']}`：状态 `{task['status']}`；取消原因 `{task['cancellation_reason']}`。")
        if state["facts"]["letter_read"]:
            markdown.extend(["", "### 已读取的生前信件", "", f"> {state['artifacts']['letter_f']['text']}"])
        observations = engine.observations()
        markdown.extend(["", "### 选择证据", ""])
        if observations:
            for observation in observations:
                markdown.append(f"- `{observation['evidence_id']}` / `{observation['dimension_id']}`：记录行为 `{observation['behavior']}`，证据标注 `{observation['strength']}`。")
            markdown.append("- 这些是按事件预先标注的候选行为记录，尚未通过逐维度的有效机会评估；不合成人格分数，不据此判断玩家本人。")
        else:
            markdown.append("- 没有输出候选画像证据。只有一个可行选项时，系统保留受限处境和行动事实，不能把它当成自愿偏好。")
        markdown.extend(["", "回放检查：已记录的快照与最终世界状态一致；日志内容与前后状态通过哈希链检查。此检查用于发现记录损坏，不是防恶意伪造的安全机制。", ""])
        saves["runs"].append({"title":title, "initial_state":initial, "catalog_hash":digest(engine.catalog), "catalog_snapshot":engine.catalog, "log":engine.log, "final_state":state, "observations":observations})
    report_path = output / "rules-demo.md"
    log_path = output / "rules-demo.json"
    report_path.write_text("\n".join(markdown), encoding="utf-8")
    log_path.write_text(json.dumps(saves, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path, log_path


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for path in write_reports():
        print(path)
