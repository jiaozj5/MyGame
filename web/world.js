const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const scopeLabels={national:'国家与社会',international:'国际关系',planetary:'行星环境',frontier:'前沿探索'};
export const calendarYear=(world,year)=>`${world?.calendar||'纪年'} ${year} 年`;
const delta=value=>`${value>0?'+':''}${value}`;

export function worldPreview(world){
  if(!world)return '';
  const recent=(world.history||[]).slice(-2).reverse();
  return `<aside class="world-preview"><div class="world-preview-heading"><span class="eyebrow">小城之外</span><button data-tab="world">时代纪事 ↗</button></div>${recent.length?recent.map(item=>`<button class="world-headline" data-world-evidence="${esc(item.id)}"><span>${esc(calendarYear(world,item.year))} · ${esc(item.domain_label)}</span><strong>${esc(item.title)}</strong></button>`).join(''):'<p>世界档案从此刻开始，新的消息会随岁月来到。</p>'}</aside>`;
}

export function worldContext(event,world){
  const rows=event.world_context||[];
  if(!rows.length)return '';
  return `<aside class="causal-echo world-context"><span class="eyebrow">相关时代背景</span>${rows.map(row=>`<button class="causal-link" data-world-evidence="${esc(row.id)}"><span>${esc(calendarYear(world,row.year))} · ${esc(row.title)}</span><small>翻看当年的社会与环境变化</small><span aria-hidden="true">↗</span></button>`).join('')}</aside>`;
}

export function renderWorld(world,filters={}){
  if(!world)return '<section class="biography-intro"><h1>时代档案尚未接续。</h1><p>刷新页面后，可从保存的人生继续。</p></section>';
  const domain=filters.domain||'all',scope=filters.scope||'all',query=filters.query||'';
  const history=(world.history||[]).filter(row=>(domain==='all'||row.domain===domain)&&(scope==='all'||row.scope===scope)&&(!query||`${row.title} ${row.text}`.includes(query))).slice().reverse();
  const modes=world.modes||[];
  const metrics=world.metrics||[];
  const modify=world.modifiers||{income_percent:100,expense_percent:100};
  return `<section class="era-cover"><div><span class="eyebrow">An unwritten world</span><h1>时代纪事</h1><p class="era-location">${esc(world.name)} · ${esc(calendarYear(world,world.year))}</p></div><button class="button secondary" data-action="export-world">带走这部纪事 <span>↓</span></button><p class="era-intro">${esc(world.profile)} 世界随时间演化，这里只记下截至当年的消息。</p></section>
  <section class="era-modes" aria-label="当前世界的发展路线">${modes.map(mode=>`<div><span>${esc(mode.label)}</span><strong>${esc(mode.value_label||mode.value)}</strong></div>`).join('')}</section>
  <aside class="era-impact"><div><span class="eyebrow">时代落在生活里</span><p>当前环境对成年后常规收入的修正 <strong>${delta((modify.income_percent||100)-100)}%</strong>，对生活开支的修正 <strong>${delta((modify.expense_percent||100)-100)}%</strong>。</p></div><p>这些变化已计入生活预算。未来的事件仍可能改变它们。</p></aside>
  <details class="era-indicators"><summary>查看 ${metrics.length} 项社会与环境状态</summary><p>数值表示当前世界的模拟状态，指标各有含义。</p><div class="world-metrics">${metrics.map(metric=>`<div class="world-metric"><div><span>${esc(metric.label)}</span><strong>${metric.value}</strong></div><div class="stat-track"><div class="stat-fill ${metric.direction==='negative'?'world-pressure':''}" style="width:${Math.min(100,Math.max(0,metric.value))}%"></div></div></div>`).join('')}</div></details>
  <form class="era-filters" id="world-filter-form"><label>生活领域<select name="domain" aria-label="筛选时代领域"><option value="all">全部领域</option>${(world.domains||[]).map(item=>`<option value="${esc(item.id)}" ${domain===item.id?'selected':''}>${esc(item.label)}</option>`).join('')}</select></label><label>观察尺度<select name="scope" aria-label="筛选观察尺度"><option value="all">全部尺度</option>${Object.entries(scopeLabels).map(([id,label])=>`<option value="${id}" ${scope===id?'selected':''}>${label}</option>`).join('')}</select></label><label>查找记事<input name="query" aria-label="查找时代记事" placeholder="标题或内容" maxlength="60" value="${esc(query)}"></label><button class="button primary" type="submit">查看</button></form>
  <div class="era-count">${history.length} 条已发生的记事<span>档案起于 ${esc(calendarYear(world,world.start_year??world.year))}</span></div>
  <section class="era-history">${history.length?history.map(item=>`<article class="era-entry ${item.id===filters.highlight?'highlight':''}" id="era-${esc(item.id)}"><div class="era-stamp"><span>${esc(calendarYear(world,item.year))}</span><small>${esc(scopeLabels[item.scope]||item.scope)}</small></div><div class="era-story"><span class="category-tag">${esc(item.domain_label||item.domain)}</span><h2>${esc(item.title)}</h2><p>${esc(item.text)}</p><div class="change-tags">${(item.changes||[]).map(change=>`<span>${esc(change)}</span>`).join('')}</div>${item.causes?.length?`<div class="world-precedents"><span>此前的变化</span>${item.causes.map(id=>{const prior=world.history.find(row=>row.id===id);return prior?`<button data-world-evidence="${esc(id)}">${esc(prior.title)} ↗</button>`:'';}).join('')}</div>`:''}</div></article>`).join(''):'<div class="era-empty"><h2>这一页暂时空着。</h2><p>尚无符合筛选条件的消息。已保存的人生不会补写未曾记录的世界历史。</p></div>'}</section>`;
}

export function worldMarkdown(world){
  if(!world)return '';
  const lines=['# 时代纪事','',`${world.name} · ${calendarYear(world,world.year)}`,'',world.profile,''];
  for(const row of world.history||[]){lines.push(`## ${calendarYear(world,row.year)} · ${row.title}`,'',`${row.domain_label} / ${scopeLabels[row.scope]||row.scope}`,'',row.text,'',...(row.changes||[]).map(change=>`- ${change}`),'');}
  lines.push('本纪事来自游戏中的架空演化，只记录已经发生的模拟事件。');
  return lines.join('\n');
}
