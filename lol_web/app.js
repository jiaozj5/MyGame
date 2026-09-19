const $ = (id) => document.getElementById(id);
let catalog;
let defaults;

const esc = (value) => String(value ?? "").replace(/[&<>\"]/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[ch]));
const unique = (values) => [...new Map(values.map((v) => [JSON.stringify(v), v])).values()];

function optionList(values, selected) {
  return values.map((value) => `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(value)}</option>`).join("");
}
function multiOptions(values, selected) {
  const set = new Set(selected || []);
  return values.map((id) => `<option value="${esc(id)}" ${set.has(id) ? "selected" : ""}>${esc(id)} · ${esc(catalog.items[id]?.name || "")}</option>`).join("");
}
function sideCard(side, title, spec) {
  const champions = Object.keys(catalog.champions);
  const runes = Object.keys(catalog.runes);
  const summoners = Object.keys(catalog.summoners);
  const policies = Object.keys(catalog.policies);
  const waves = Object.keys(catalog.waves);
  const champ = catalog.champions[spec.champion];
  $(`${side}-card`).innerHTML = `
    <div class="card-head"><div><p class="eyebrow">${side === "player" ? "PLAYER" : "OPPONENT"}</p><h2>${title}</h2></div><span class="muted">1–6级</span></div>
    <div class="form-grid">
      <label>英雄<select id="${side}-champion">${champions.map((x) => `<option value="${esc(x)}" ${x === spec.champion ? "selected" : ""}>${esc(x)} · ${esc(catalog.champions[x].name)}</option>`).join("")}</select></label>
      <label>等级<select id="${side}-level">${[1,2,3,4,5,6].map((x) => `<option value="${x}" ${x === spec.level ? "selected" : ""}>${x}级</option>`).join("")}</select></label>
      <label class="wide">技能加点（六级依次）<input id="${side}-skill-order" value="${esc(spec.skill_order.join(" "))}" placeholder="Q E W E E R"></label>
      <label>基石天赋<select id="${side}-rune">${optionList(runes, spec.rune)}</select></label>
      <label>对线策略<select id="${side}-policy">${policies.map((x) => `<option value="${esc(x)}" ${x === spec.policy ? "selected" : ""}>${esc(x)} · ${esc(catalog.policies[x])}</option>`).join("")}</select></label>
      <label>兵线处理<select id="${side}-wave">${waves.map((x) => `<option value="${esc(x)}" ${x === spec.wave ? "selected" : ""}>${esc(x)} · ${esc(catalog.waves[x])}</option>`).join("")}</select></label>
      <label>技能循环<input id="${side}-combo" value="${esc(spec.combo.join(" "))}" placeholder="Q AA E"></label>
      <label>召唤师 1<select id="${side}-sum1">${optionList(summoners, spec.summoners[0])}</select></label>
      <label>召唤师 2<select id="${side}-sum2">${optionList(summoners, spec.summoners[1])}</select></label>
      <label class="wide">起始装备（Ctrl/⌘ 可多选）<select id="${side}-items" multiple>${multiOptions(Object.keys(catalog.items), spec.items)}</select></label>
    </div>
    <p class="muted tip" id="${side}-tip"></p>`;
  $(`${side}-champion`).addEventListener("change", () => {
    const chosen = catalog.champions[$(`${side}-champion`).value];
    $(`${side}-tip`).textContent = `${chosen.name}：${chosen.role}。技能：${Object.entries(chosen.abilities).map(([k,v]) => `${k} ${v.name}`).join(" · ")}`;
  });
  $(`${side}-champion`).dispatchEvent(new Event("change"));
}
function readMulti(id) { return [...$(id).selectedOptions].map((x) => x.value); }
function readOrder(id) { return $(id).value.trim().toUpperCase().split(/[\s,，>→-]+/).filter(Boolean); }
function readSide(side) {
  return {
    champion: $(`${side}-champion`).value,
    level: Number($(`${side}-level`).value),
    skill_order: readOrder(`${side}-skill-order`),
    items: readMulti(`${side}-items`),
    rune: $(`${side}-rune`).value,
    summoners: [$(`${side}-sum1`).value, $(`${side}-sum2`).value],
    policy: $(`${side}-policy`).value,
    wave: $(`${side}-wave`).value,
    combo: readOrder(`${side}-combo`),
  };
}
function readConfig() {
  return {
    player: readSide("player"), opponent: readSide("opponent"),
    duration: Number($("duration").value), start_time: Number($("start-time").value),
    accuracy: Number($("accuracy").value), opponent_accuracy: Number($("opponent-accuracy").value),
    distance: Number($("distance").value), mode: $("mode").value, seed: Number($("seed").value),
    starting_gold: Number($("starting-gold").value),
  };
}
function setScenario(config) {
  $("duration").value = config.duration; $("start-time").value = config.start_time;
  $("accuracy").value = config.accuracy; $("opponent-accuracy").value = config.opponent_accuracy;
  $("distance").value = config.distance; $("mode").value = config.mode; $("seed").value = config.seed;
  $("starting-gold").value = config.starting_gold ?? 500;
}
function metric(label, value, className = "") { return `<div class="metric ${className}"><small>${esc(label)}</small><b>${esc(value)}</b></div>`; }
function fighterTable(label, fighter) {
  return `<div class="subpanel"><h3>${esc(label)} · ${esc(fighter.champion)}</h3><table><tbody>
    <tr><td>等级 / 生命</td><td>${fighter.level} / ${fighter.hp} / ${fighter.max_hp}</td></tr>
    <tr><td>补刀 / 金币</td><td>${fighter.cs} / ${fighter.gold}</td></tr>
    <tr><td>造成 / 承受伤害</td><td>${fighter.damage_dealt} / ${fighter.damage_taken}</td></tr>
    <tr><td>击杀 / 死亡 / 回城</td><td>${fighter.kills} / ${fighter.deaths} / ${fighter.recalls}</td></tr>
    <tr><td>技能等级</td><td>${esc(JSON.stringify(fighter.skill_ranks))}</td></tr>
  </tbody></table></div>`;
}
function renderSimulation(data) {
  const s = data.summary, w = s.winner;
  const wc = w === "player" ? "winner-player" : w === "opponent" ? "winner-opponent" : "winner-even";
  const events = (data.timeline || []).slice(0, 80).map((e) => `<li><b>${esc(e.time)}s</b>　${esc(e.text || e.event)}${e.value == null ? "" : `　<span>${esc(e.value)}</span>`}</li>`).join("");
  $("result").className = "result";
  $("result").innerHTML = `<div class="summary-grid">
    ${metric("模型判定", w === "player" ? "玩家领先" : w === "opponent" ? "对手领先" : "接近均势", wc)}
    ${metric("分数", s.score)}${metric("补刀差", s.cs_diff)}${metric("击杀差", s.kill_diff)}
    ${metric("金币差", s.gold_diff)}${metric("经验差", s.xp_diff)}${metric("生命比例差", s.hp_diff)}${metric("时长", `${s.duration}s`)}
  </div><div class="columns">${fighterTable("玩家", s.player)}${fighterTable("对手", s.opponent)}</div>
  <details><summary>时间线（前 ${Math.min(80, (data.timeline || []).length)} 条）</summary><ul class="timeline">${events || "<li>无事件</li>"}</ul></details>
  <details><summary>模型警告与限制</summary><ul>${(data.warnings || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>
  <details><summary>完整 JSON</summary><pre>${esc(JSON.stringify(data, null, 2))}</pre></details>`;
}
function renderOptimize(data) {
  const rows = (data.ranking || []).slice(0, 12).map((row, i) => `<tr><td>${i + 1}</td><td>${esc(row.config.player.rune)} / ${esc(row.config.player.policy)} / ${esc(row.config.player.wave)}</td><td>${row.mean_score}</td><td>${row.worst_score}</td><td>${(row.win_rate * 100).toFixed(0)}%</td><td>${row.mean_cs_diff}</td></tr>`).join("");
  $("result").className = "result";
  $("result").innerHTML = `<div class="summary-grid">${metric("候选数", data.search.candidates)}${metric("试验次数", data.search.trials)}${metric("目标", data.search.objective)}${metric("模型", data.model)}</div>
    <div class="subpanel"><h3>前 12 名（同一对手、同一批种子）</h3><table><thead><tr><th>#</th><th>符文 / 策略 / 兵线</th><th>均值分</th><th>最差分</th><th>胜出率</th><th>补刀差</th></tr></thead><tbody>${rows}</tbody></table></div>
    <details><summary>排名第 1 的完整配置</summary><pre>${esc(JSON.stringify(data.best, null, 2))}</pre></details>
    <details><summary>模型警告与限制</summary><ul>${(data.warnings || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>`;
}
async function run(path, config, renderer) {
  $("busy").textContent = "计算中…"; $("simulate").disabled = true; $("optimize").disabled = true;
  try {
    const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(config)});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    renderer(data);
  } catch (error) { $("result").className = "result empty"; $("result").textContent = `配置未运行：${error.message}`; }
  finally { $("busy").textContent = ""; $("simulate").disabled = false; $("optimize").disabled = false; }
}
function optimizeConfig() {
  const base = readConfig();
  const p = base.player;
  const alt = (current, values) => unique([current, ...values]);
  return {...base, search: {
    seeds: [0, 1, 2, 3], objective: "mean",
    runes: alt(p.rune, ["conqueror", "grasp"]),
    policies: alt(p.policy, ["short_trade"]), waves: alt(p.wave, ["freeze"]),
    items: alt(p.items, [["1055"], ["1054"]]),
    summoners: alt(p.summoners, [["flash", "ignite"], ["flash", "teleport"]]),
    combos: alt(p.combo, [["Q", "AA", "E"], ["AA"]]),
    skill_orders: [p.skill_order],
  }};
}
async function init() {
  try {
    const response = await fetch("/api/catalog"); catalog = await response.json();
    defaults = catalog.defaults;
    $("version").textContent = `正式服 ${catalog.patch} · 模型 ${catalog.model}`;
    sideCard("player", "玩家配置", defaults.player); sideCard("opponent", "对手配置", defaults.opponent); setScenario(defaults);
    $("simulate").addEventListener("click", () => run("/api/simulate", readConfig(), renderSimulation));
    $("optimize").addEventListener("click", () => run("/api/optimize", optimizeConfig(), renderOptimize));
    $("reset").addEventListener("click", () => { sideCard("player", "玩家配置", defaults.player); sideCard("opponent", "对手配置", defaults.opponent); setScenario(defaults); $("result").className = "result empty"; $("result").textContent = "已恢复默认配置。"; });
    $("copy-config").addEventListener("click", async () => { await navigator.clipboard.writeText(JSON.stringify(readConfig(), null, 2)); $("busy").textContent = "配置 JSON 已复制"; setTimeout(() => $("busy").textContent = "", 1600); });
  } catch (error) { $("result").textContent = `目录读取失败：${error.message}`; }
}
init();
