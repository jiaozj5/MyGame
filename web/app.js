import {drawScene, drawPortrait} from './art.js';
import {renderWorld, worldPreview, worldContext, worldMarkdown, calendarYear} from './world.js';
import {renderPopulation} from './people.js';
import {storeSave,loadSave} from './storage.js';

const $=(selector)=>document.querySelector(selector);
const esc=(value)=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const money=value=>new Intl.NumberFormat('zh-CN',{maximumFractionDigits:0}).format(value||0);
const SAVE_KEY='fusheng-save-v05';
const LEGACY_SAVE_KEYS=['fusheng-save-v04','fusheng-save-v03','fusheng-save-v02'];
const UPGRADE_BACKUP_KEY='fusheng-before-upgrade-v05';
const ICONS={menu:'M4 5h16M4 12h16M4 19h16',cash:'M3 5h18v14H3zM3 9h18M7 14h3',energy:'m13 2-8 11h6l-1 9 9-12h-6z',health:'M12 20S3 14 3 8a4 4 0 0 1 9-2 4 4 0 0 1 9 2c0 6-9 12-9 12Z',stress:'M3 16h3l3-9 4 13 3-9h5',education:'m2 9 10-5 10 5-10 5zM6 11v6l6 3 6-3v-6',skill:'m14 4 6-1-1 6-4 1-9 11-3-3 11-10z'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[name]||ICONS.menu}"/></svg>`;
const origins={ordinary:{name:'普通人家',symbol:'▥',text:'日子算不上宽裕，也有家人为你留着一盏灯。'},struggling:{name:'清贫小院',symbol:'⌂',text:'家里常常精打细算。小小的决定，也有自己的分量。'},comfortable:{name:'安稳之家',symbol:'▤',text:'生活多一些余裕。宽阔的起点，仍有需要自己走的路。'}};
const sceneNames={home:'老屋与灯火',school:'小镇学堂',town:'青溪镇',work:'街角与工坊',river:'青溪河畔',hospital:'小城医院',evening:'暮色里的小城'};
let view=null,save=null,gameId=null,activeTab='life',busy=false,timelineFilter='all',showAllTimeline=false,highlightId=null,toastTimer,recoveryText=null;
let worldFilters={domain:'all',scope:'all',query:'',highlight:null};
let peopleFilters={query:'',group:'known',offset:0},peopleData=null,personDetail=null,peopleLoading=false,peopleRequest=0;

async function request(path,body){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'这一步暂时没有完成。');
  return result;
}
function notify(message){const toast=$('#toast');toast.textContent=message;toast.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.hidden=true,4500);}
async function applyResult(result){
  view=result.view;save=result.save;gameId=result.game_id;
  peopleData=view.population;personDetail=null;peopleFilters={query:'',group:'known',offset:0};peopleRequest++;peopleLoading=false;
  try{await storeSave(SAVE_KEY,save);$('#save-status').textContent='已自动保存 · 此刻';}
  catch{$('#save-status').textContent='自动保存不可用';notify('浏览器暂时无法自动保存，请在菜单中导出存档。');}
  if(view.finished)activeTab='biography';render();
}
function readStored(key){try{return localStorage.getItem(key);}catch{return null;}}
function legacySave(){return LEGACY_SAVE_KEYS.map(readStored).find(Boolean)||null;}
function keepUpgradeBackup(previous,result){
  if(['1.0.0','1.1.0','1.2.0'].includes(previous?.schema_version) && result.save?.schema_version==='1.3.0'){
    try{localStorage.setItem(UPGRADE_BACKUP_KEY,JSON.stringify(previous));}
    catch{notify('这次升级前的备份未能写入浏览器。原有旧版自动存档仍保留，请导出存档妥善保存。');}
  }
}
function refreshBackupButton(){
  $('#export-backup').hidden=!(readStored(UPGRADE_BACKUP_KEY)||legacySave());
}
function renderOutlook(){
  const plan=view.outlook;
  if(view.age<18)return '<aside class="outlook childhood-outlook"><span class="eyebrow">有人为你撑起日常</span><p>家人照料生活，零用钱可以慢慢留下来。成年后，你会开始承担自己的年度开支。</p></aside>';
  if(view.age>=82)return '<aside class="outlook childhood-outlook"><span class="eyebrow">最后这一页</span><p>眼前还有一段经历等待落笔。这一章过后，走过的路将收进人物志。</p></aside>';
  if(!plan)return '';
  const signed=value=>`${value>0?'+':''}${money(value)}`;
  const balance=Number(plan.balance)||0;
  const interval=plan.years_to_next>0?`下一人生片段相隔约 ${plan.years_to_next} 年，途中会逐年结算。`:'眼前还有同一年的事情需要决定。';
  return `<aside class="outlook" aria-label="下一年生活预估"><div class="outlook-heading"><span class="eyebrow">日子的打算 · 下一年预估</span><span class="pace-tag">${esc(plan.pace_label||'平稳节奏')}</span></div><div class="outlook-budget"><div><span>收入</span><strong>¥ ${money(plan.income)}</strong></div><div><span>开支</span><strong>¥ ${money(plan.expenses)}</strong></div><div class="${balance<0?'budget-gap':'budget-surplus'}"><span>${balance<0?'缺口':'结余'}</span><strong>¥ ${money(Math.abs(balance))}</strong></div></div><div class="outlook-effects"><span>精力 ${signed(plan.energy_change||0)}</span><span>压力 ${signed(plan.stress_change||0)}</span></div><p class="outlook-interval">${interval}</p>${plan.warnings?.length?`<ul class="outlook-warnings">${plan.warnings.map(warning=>`<li>${esc(warning)}</li>`).join('')}</ul>`:''}<details class="outlook-help"><summary>这些数字意味着什么</summary><p>这是按当前时代环境和个人安排计算的预估，未来宏观变化与额外事件的影响另计。工作安排和休整时，可以重新选择生活节奏；透支精力、积累压力都会影响往后的日子。</p></details></aside>`;
}
function renderCauses(event){
  if(!event.causes?.length)return '';
  return `<aside class="causal-echo"><span class="eyebrow">这件事有来处</span>${event.causes.map(cause=>`<button class="causal-link" data-evidence="${esc(cause.id)}"><span>${cause.age} 岁 · ${esc(cause.title)}</span><small>那时，你选择了「${esc(cause.choice)}」</small><span aria-hidden="true">↗</span></button>`).join('')}</aside>`;
}
function formMarkup(prefix='start'){
  return `<form class="new-form" id="${prefix}-form"><label for="${prefix}-name">这一生，你的名字</label><input id="${prefix}-name" name="name" maxlength="16" autocomplete="off" value="林禾" required><label>你出生在怎样的人家</label><div class="origin-options" role="group" aria-label="出生家庭">${Object.entries(origins).map(([id,item])=>`<button type="button" class="origin-option ${id==='ordinary'?'selected':''}" data-origin="${id}" aria-pressed="${id==='ordinary'}"><span class="origin-icon" aria-hidden="true">${item.symbol}</span>${item.name}</button>`).join('')}</div><input name="origin" type="hidden" value="ordinary"><p class="origin-description">${origins.ordinary.text}</p><button type="submit" class="button primary">开始这一生 <span aria-hidden="true">→</span></button><details class="seed-row"><summary>给这段人生一个编号（可选）</summary><input name="seed" type="number" min="0" max="2147483647" placeholder="留空，遇见未知的人生" aria-label="人生编号"></details></form>`;
}
function renderLanding(){
  $('#navigation').hidden=true;$('#menu-button').hidden=true;
  $('#app').innerHTML=`<section class="hero"><div class="hero-art"><span class="eyebrow">A life in a small town</span><h1 class="hero-heading">小城的风吹过，<br>留下<em>你的一生。</em></h1><div class="hero-scene"><canvas class="scene-canvas" id="landing-scene" aria-label="像素画：青溪镇的房屋、树木与河流"></canvas></div><div class="photo-caption"><span>青溪镇，一切还没有开始。</span><span>新历元年 · 春</span></div></div><div class="hero-intro"><span class="eyebrow">每一个选择，都有回声</span><h2>有些路，是走过之后<br>才知道通向哪里。</h2><p class="hero-copy">从一声啼哭，到一页人物志。<br>在一个历史尚未写定的世界里，长大、谋生、与人相遇。<br>时代会改变生活，你也有自己的选择。</p>${formMarkup()}<p class="welcome-note">约 30 次关键选择 · 自动保存进度<br>没有标准的人生答案。你的经历，会成为最后的故事。</p></div></section>`;
  drawScene($('#landing-scene'),{scene:'town',age:6});
}
function stageTitle(){if(view.finished)return '一生已成书';return {童年:'小城初醒',少年:'青涩时光',青年:'路向远方',成年:'日子深处',中年:'日子深处',老年:'晚风徐来',晚年:'晚风徐来'}[view.stage]||'岁月缓缓向前';}
function progressMarkup(){const stages=[['出生',0],['童年',6],['少年',12],['青年',18],['中年',40],['晚年',65],['终章',82]];return `<div class="life-progress"><span>这一生的刻度</span><div class="life-stages" style="--progress:${Math.min(100,view.age/82*100)}%">${stages.map(([name,age])=>`<span class="life-stage ${view.age>=age||view.finished?'reached':''}">${name}</span>`).join('')}</div></div>`;}
function statMarkup(key,name){const value=view.stats[key]||0;const cash=key==='cash';const danger=key==='health'&&value<35||key==='energy'&&value<20||key==='stress'&&value>70;return `<div class="stat"><div class="stat-top"><span class="stat-name">${icon(key)}${name}</span><span class="stat-value">${cash?money(value):value}${cash?'<span class="stat-unit"> 元</span>':''}</span></div>${cash?`<div class="stat-finance-note">${view.age<18?'日常生活由家人照料':value<Math.max(1,view.status.expenses||12000)?'留意接下来的生活开支':'手里留有一些余裕'}</div>`:`<div class="stat-track"><div class="stat-fill ${danger?'danger':''}" style="width:${Math.min(100,Math.max(0,value))}%"></div></div>`}</div>`;}
function renderLife(){
  if(!view.event){return `<section class="biography-intro"><div class="book-mark">终</div><h1>岁月落笔，这一生已成书。</h1><p>那些相遇、选择和牵挂，都留在了你的人物志里。</p><button data-tab="biography" class="button primary">翻开人物志 <span>→</span></button></section>`;}
  const event={...view.event,choices:view.event.choices.map(choice=>({...choice,description:compactChoiceText(choice.description)===compactChoiceText((choice.costs||[]).join(''))?'':choice.description}))};
  return `<div class="play-heading"><div class="season-title"><h1>${stageTitle()}</h1><span class="eyebrow">${esc(view.stage)} · ${esc(calendarYear(view.world,view.year))}</span></div><span class="chapter-counter">${String(Math.round((view.progress||0)*30)+1).padStart(2,'0')} / 人生片段</span></div><div class="game-grid"><section class="world-panel" aria-label="人物与生活状态"><div class="scene-frame"><canvas id="game-scene" class="scene-canvas" aria-label="青溪镇的像素场景"></canvas><span class="scene-time">${esc(calendarYear(view.world,view.year))} · QINGXI</span><span class="scene-label">${sceneNames[event.scene]||'青溪镇'}</span></div><div class="character-strip"><canvas class="portrait" id="player-portrait" aria-label="角色像素头像"></canvas><div><h2 class="character-name">${esc(view.name)}</h2><div class="character-desc">${esc(origins[view.origin]?.name||'青溪镇人')} · ${esc(view.status.job_label||'尚在成长')}</div></div><div class="age-tag">${view.age}<small>岁</small></div></div><div class="stats-grid">${[['cash','积蓄'],['health','健康'],['energy','精力'],['stress','压力'],['education','学识'],['skill','技能']].map(([key,name])=>statMarkup(key,name)).join('')}</div>${renderOutlook()}${worldPreview(view.world)}${view.last_outcome?`<aside class="echo"><span class="eyebrow">上一段回声 · ${esc(view.last_outcome.title)}</span><p>${esc(view.last_outcome.text)}</p>${view.last_outcome.changes?.length?`<div class="change-tags">${view.last_outcome.changes.map(change=>`<span>${esc(change)}</span>`).join('')}</div>`:''}</aside>`:`<aside class="echo"><span class="eyebrow">故事的起点</span><p>你出生在青溪镇。长长的一生，从眼前这件小事开始。</p></aside>`}</section><section class="story-card" aria-labelledby="story-title"><div class="story-meta"><span class="category-tag">${esc(event.category)}</span><span>${view.age} 岁 · ${esc(view.stage)}</span></div><h2 class="story-title" id="story-title" tabindex="-1">${esc(event.title)}</h2><p class="story-text">${esc(event.text)}</p>${event.id.startsWith("system.recovery.")?'<p class="recovery-notice">先把眼前的日子安顿好，再继续往前。</p>':''}${renderCauses(event)}${worldContext(event,view.world)}<div class="choice-divider">这一次，你会怎样选择</div><div class="choices">${event.choices.map((choice,index)=>`<button class="choice" data-choice="${esc(choice.id)}" ${!choice.available?'disabled':''}><span class="choice-letter">${choice.available?String.fromCharCode(65+index):'·'}</span><span class="choice-content"><span class="choice-label">${esc(choice.label)}</span>${choice.description?`<span class="choice-description">${esc(choice.description)}</span>`:''}${choice.costs?.length?`<span class="choice-costs">${choice.costs.map(esc).join('　·　')}</span>`:''}${!choice.available?`<span class="locked-reason">暂不可选 · ${esc(choice.locked_reason||'尚未满足条件')}</span>`:''}</span><span class="choice-arrow" aria-hidden="true">${choice.available?'↗':'—'}</span></button>`).join('')}</div><p class="story-footnote">选择之后，时间会继续向前。无法选择的路，不会被当作你的偏好。</p></section></div>${progressMarkup()}`;
}
function renderPeople(){
  return renderPopulation(peopleData,peopleFilters,view,personDetail,peopleLoading);
}
const compactChoiceText = text => String(text??'').replace(/[，。·\s]/g, '');
function isChoice(entry){return !!entry.choice||entry.kind==='choice';}
function renderTimeline(){
  const filtered=view.timeline.filter(entry=>timelineFilter==='all'||timelineFilter==='choice'&&isChoice(entry)||timelineFilter==='turn'&&!isChoice(entry)&&!['annual','budget','income'].includes(entry.kind));
  let entries=[...filtered].reverse();if(!showAllTimeline)entries=entries.slice(0,30);
  return `<div class="section-heading"><div><span class="eyebrow">An archive of living</span><h1>人生年表</h1></div><p class="muted">${view.name?esc(view.name)+'的':''}每一步，都有来处。<br>在这里回看选择、生活的改变，以及他人的消息。</p></div><div class="filter-buttons"><button class="filter-button ${timelineFilter==='all'?'active':''}" data-filter="all">全部记事</button><button class="filter-button ${timelineFilter==='choice'?'active':''}" data-filter="choice">我的选择</button><button class="filter-button ${timelineFilter==='turn'?'active':''}" data-filter="turn">生活转折</button></div><section class="timeline-list">${entries.map(entry=>`<article class="timeline-item ${entry.id===highlightId?'highlight':''}" id="memory-${esc(entry.id)}"><div class="timeline-date"><span class="timeline-age">${entry.age}<small class="small"> 岁</small></span><span class="timeline-year">${esc(calendarYear(view.world,entry.year??view.year-view.age+entry.age))}</span></div><div class="timeline-body"><h3>${esc(entry.title)}</h3><p>${esc(entry.text)}</p>${entry.choice?`<div class="choice-memory">当时的选择 · ${esc(typeof entry.choice==='string'?entry.choice:entry.choice.label||entry.choice.id)}</div>`:''}</div></article>`).join('')}${!entries.length?'<p class="muted">这一类记事还没有发生。</p>':''}${filtered.length>30&&!showAllTimeline?`<button class="button secondary more-button" data-action="all-timeline">展开全部 ${filtered.length} 条记事 <span>↓</span></button>`:''}</section>`;
}
function evidenceLinks(ids=[]){return `<div class="evidence-links">${ids.filter(id=>view.timeline.some(entry=>entry.id===id)).map(id=>{const entry=view.timeline.find(item=>item.id===id);return `<button class="evidence-link" data-evidence="${esc(id)}" title="回看这条经历">${entry.age} 岁 · ${esc(entry.title)} ↗</button>`;}).join('')}</div>`;}
const portraitLabels={
  novelty_approach:'接近新事物',information_seeking:'先获取信息',familiarity_preference:'保留熟悉做法',
  goal_commitment:'目标投入',method_adaptation:'方法调整',exit_reassessment:'暂停与退出复评',
  contact_initiation:'发起接触',social_selectivity:'社交选择',solitude_choice:'主动独处',
  need_attention:'注意需求',support_mode:'支持方式',care_scope_boundary:'关怀边界',
  allocation_principle:'分配原则',commitment_management:'承诺管理',conflict_disclosure:'利益冲突披露',
  assertion_boundary:'主张边界',negotiation_compromise:'协商妥协',withdrawal_mediation:'退出与调解',
  risk_acceptance:'接受风险',risk_information:'风险信息',risk_mitigation:'降低风险',
  support_initiation:'发起求助',autonomy_first:'先自主处理',trust_and_reciprocity:'信任与互惠',
  low:'低压力',moderate:'中等压力',high:'高压力',essential_need_threat:'基本需求受威胁',
  self:'自我',dependent:'受抚养者',family:'家庭',friend:'朋友',neighbor:'邻里',institution:'机构',group:'群体',unknown:'未标注',
  known:'信息较充分',partial:'信息部分已知',uncertain:'信息不确定',general:'未细分'
};
function portraitLabel(value){return portraitLabels[value]||value;}
function patternDetails(pattern){
  const count=(obj)=>Object.entries(obj||{}).map(([key,value])=>`${esc(portraitLabel(key))} ${esc(value)}`).join(' · ');
  const facets=count(pattern.facet_counts);
  const pressure=count(pattern.pressure_counts);
  const relationships=count(pattern.relationship_counts);
  const information=count(pattern.information_counts);
  return `<div class="pattern-details"><div class="pattern-metrics"><span>有效机会 ${pattern.eligible_opportunities||0}</span><span>独立剧情 ${pattern.independent_episodes||0}</span><span>${esc(pattern.evidence_level||'材料不足')}</span></div>${pattern.subdimensions?.length?`<p class="pattern-subdimensions">观察子维度：${pattern.subdimensions.map(item=>esc(portraitLabel(item))).join(' · ')}</p>`:''}${facets?`<p class="pattern-context">行为子类：${facets}</p>`:''}${pressure?`<p class="pattern-context">压力情境：${pressure}</p>`:''}${relationships?`<p class="pattern-context">关系范围：${relationships}</p>`:''}${information?`<p class="pattern-context">信息条件：${information}</p>`:''}${pattern.limitations?.length?`<ul class="pattern-limitations">${pattern.limitations.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>`:''}</div>`;
}
function renderBiography(){
  if(!view.finished||!view.biography)return `<section class="biography-intro"><div class="book-mark">志</div><span class="eyebrow">A story still unfolding</span><h1>你的故事，还在发生。</h1><p>等这一生走完，发生过的事会被收进人物志。它会记下你的选择、代价与变化，也会留下无法判断的部分。</p><button class="button primary" data-tab="life">回到此刻 <span>→</span></button></section>`;
  const bio=view.biography;
  return `<article class="biography-paper"><header class="biography-cover"><span class="eyebrow">青溪镇人物志 · ${esc(view.world?.calendar||"纪年")} ${view.year-view.age} — ${view.year}</span><h1>${esc(bio.title||view.name+'小传')}</h1><p class="biography-subtitle">${esc(bio.subtitle)}</p><p class="biography-summary">${esc(bio.summary)}</p></header><div class="biography-chapters">${(bio.chapters||[]).map(chapter=>`<section class="biography-chapter"><h2>${esc(chapter.title)}</h2><p>${esc(chapter.text)}</p>${evidenceLinks(chapter.event_ids)}</section>`).join('')}</div><section class="biography-section"><h2>那些选择，勾勒出的你</h2><div class="pattern-grid">${(bio.patterns||[]).map(pattern=>`<article class="pattern"><h3>${esc(pattern.label)}<span class="coverage">证据${esc(pattern.coverage)}</span></h3><p>${esc(pattern.text)}</p>${patternDetails(pattern)}${evidenceLinks(pattern.evidence_ids)}${pattern.counter_evidence_ids?.length?`<p class="small" style="margin-top:9px">也曾作出不同选择</p>${evidenceLinks(pattern.counter_evidence_ids)}`:''}</article>`).join('')}</div></section>${bio.relationships?.length?`<section class="biography-section"><h2>那些与你同行的人</h2>${bio.relationships.map(person=>`<article class="relationship-memo"><h3>${esc(person.name)}</h3><p>${esc(person.text)}</p>${evidenceLinks(person.event_ids)}</article>`).join('')}</section>`:''}<p class="closing">${esc(bio.closing)}</p><div class="biography-notes">${(bio.notes||[]).map(note=>`<p>${esc(note)}</p>`).join('')}</div><div class="ending-actions"><button class="button secondary" data-action="export-biography">带走这本人物志 <span>↓</span></button><button class="button primary" data-action="new-life">再过一种人生 <span>→</span></button></div></article>`;
}
function render(){
  if(!view){renderLanding();return;}
  $('#navigation').hidden=false;$('#menu-button').hidden=false;
  document.querySelectorAll('.nav-button').forEach(button=>{button.classList.toggle('active',button.dataset.tab===activeTab);button.setAttribute('aria-current',button.dataset.tab===activeTab?'page':'false');});
  const renderers={life:renderLife,people:renderPeople,world:()=>renderWorld(view.world,worldFilters),timeline:renderTimeline,biography:renderBiography};
  $('#app').innerHTML=(view.migration_note?`<aside class="migration-note" role="status"><span>旧日记已接续</span><p>${esc(view.migration_note)}</p><button data-action="export-backup">带走升级前的备份 ↓</button></aside>`:'')+renderers[activeTab]();$('#footer-right').textContent=view.finished?'这一路，已成为故事':`${calendarYear(view.world,view.year)} · ${view.stage} · 选择会留下回声`;
  if(activeTab==='life'){drawScene($('#game-scene'),{scene:view.event?.scene,age:view.age,year:view.year,finished:view.finished});drawPortrait($('#player-portrait'),{id:'player',age:view.age,alive:!view.finished});}
  if(activeTab==='people')document.querySelectorAll('.population-portrait').forEach(canvas=>{const person=personDetail?.id===canvas.dataset.personId?personDetail:peopleData?.people.find(item=>item.id===canvas.dataset.personId);drawPortrait(canvas,{...person,alive:!['dead','deceased'].includes(person?.status)});});
}
function setTab(tab){if(!view)return;activeTab=tab;render();window.scrollTo({top:0,behavior:'instant'});}
async function loadPeople(npcId=null){
  const token=++peopleRequest;peopleLoading=true;if(activeTab==='people')render();
  try{
    const result=await request(npcId?'/api/person':'/api/people',{game_id:gameId,...(npcId?{npc_id:npcId}:peopleFilters)});
    if(token!==peopleRequest)return;
    if(npcId)personDetail=result;else{peopleData=result;personDetail=null;}
  }catch(error){if(token===peopleRequest)notify(error.message);}
  finally{if(token===peopleRequest){peopleLoading=false;if(activeTab==='people')render();}}
}
async function socialAction(action,npcId,plan=null){
  if(busy)return;busy=true;$('#app').classList.add('busy');
  try{
    const result=await request(plan?'/api/social-plan':'/api/social',{game_id:gameId,revision:view.revision,...(plan?{plan}:{npc_id:npcId,action})});
    await applyResult(result);if(npcId)await loadPeople(npcId);notify(plan?'接下来的日常来往已重新安排。':view.last_outcome?.text||'这次来往已记下。');
  }catch(error){notify(error.message);}
  finally{busy=false;$('#app').classList.remove('busy');}
}
function download(filename,text,type='application/json'){
  const url=URL.createObjectURL(new Blob([text],{type:`${type};charset=utf-8`}));const link=document.createElement('a');link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function exportSave(){if(!save)return;download(`浮生-${view.name}-${view.age}岁.json`,JSON.stringify(save));notify('存档已导出。');}
function exportBackup(){
  const original=readStored(UPGRADE_BACKUP_KEY)||legacySave();
  if(!original){notify('当前浏览器没有升级前的备份。');return;}
  download('浮生-升级前备份.json',original);notify('升级前的原始存档已导出。');
}
function exportBiography(){
  const bio=view.biography;if(!bio)return;
  const lines=[`# ${bio.title}`,'',bio.subtitle,'',bio.summary,''];
  for(const chapter of bio.chapters||[])lines.push(`## ${chapter.title}`,'',chapter.text,'');
  lines.push('## 选择与情境','');for(const pattern of bio.patterns||[]){lines.push(`### ${pattern.label}（证据${pattern.coverage}）`,'',pattern.text,'',`- 有效机会：${pattern.eligible_opportunities||0}` ,`- 独立剧情：${pattern.independent_episodes||0}`,`- 证据等级：${pattern.evidence_level||'材料不足'}`);if(pattern.subdimensions?.length)lines.push(`- 观察子维度：${pattern.subdimensions.join('、')}`);if(pattern.limitations?.length)lines.push(`- 限制：${pattern.limitations.join('；')}`);lines.push('');for(const id of pattern.evidence_ids||[]){const entry=view.timeline.find(item=>item.id===id);if(entry)lines.push(`- ${entry.age}岁 · ${entry.title}：${entry.text}`);}lines.push('');}
  lines.push('## 同行的人','');for(const person of bio.relationships||[])lines.push(`### ${person.name}`,'',person.text,'');lines.push(bio.closing,'',...(bio.notes||[]));
  download(`浮生-${view.name}-人物志.md`,lines.join('\n'),'text/markdown');
}
function openNew(){
  $('#settings-dialog').close();$('#new-form-container').innerHTML=formMarkup('again');$('#new-dialog').showModal();
}
async function choose(id){
  if(busy)return;busy=true;$('#app').classList.add('busy');
  try{const result=await request('/api/choose',{game_id:gameId,choice_id:id,revision:view.revision});await applyResult(result);$('#story-title')?.focus({preventScroll:true});}
  catch(error){notify(error.message);}
  finally{busy=false;$('#app').classList.remove('busy');}
}
async function start(form){
  if(busy)return;busy=true;const button=form.querySelector('[type=submit]');button.disabled=true;button.textContent='小城正在醒来…';
  const data=new FormData(form);const raw=data.get('seed');
  try{const result=await request('/api/new',{name:data.get('name'),origin:data.get('origin'),seed:raw!==''?Number(raw):null});activeTab='life';showAllTimeline=false;timelineFilter='all';highlightId=null;worldFilters={domain:'all',scope:'all',query:'',highlight:null};await applyResult(result);$('#new-dialog').close();window.scrollTo({top:0,behavior:'instant'});}
  catch(error){notify(error.message);button.disabled=false;button.innerHTML='开始这一生 <span>→</span>';}
  finally{busy=false;}
}
document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.tab){setTab(button.dataset.tab);return;}
  if(button.dataset.choice){choose(button.dataset.choice);return;}
  if(button.hasAttribute('data-people-back')){peopleRequest++;peopleLoading=false;personDetail=null;render();return;}
  if(button.dataset.person){loadPeople(button.dataset.person);return;}
  if(button.dataset.social){socialAction(button.dataset.social,button.dataset.socialPerson);return;}
  if(button.dataset.socialPlan){socialAction(null,null,button.dataset.socialPlan);return;}
  if(button.hasAttribute('data-people-page')){peopleFilters.offset=Number(button.dataset.peoplePage);loadPeople();return;}
  if(button.dataset.origin){const form=button.closest('form');form.querySelector('[name=origin]').value=button.dataset.origin;form.querySelectorAll('[data-origin]').forEach(item=>{item.classList.toggle('selected',item===button);item.setAttribute('aria-pressed',item===button?'true':'false');});form.querySelector('.origin-description').textContent=origins[button.dataset.origin].text;return;}
  if(button.dataset.filter){timelineFilter=button.dataset.filter;showAllTimeline=false;render();return;}
  if(button.dataset.evidence){highlightId=button.dataset.evidence;showAllTimeline=true;timelineFilter='all';setTab('timeline');document.getElementById(`memory-${highlightId}`)?.scrollIntoView({block:'center',behavior:'smooth'});return;}
  if(button.dataset.worldEvidence){worldFilters={domain:'all',scope:'all',query:'',highlight:button.dataset.worldEvidence};setTab('world');document.getElementById(`era-${worldFilters.highlight}`)?.scrollIntoView({block:'center',behavior:'smooth'});return;}
  if(button.dataset.action==='all-timeline'){showAllTimeline=true;render();return;}
  if(button.dataset.action==='all-people-news'){peopleFilters.allNews=true;render();return;}
  if(button.dataset.action==='export-biography'){exportBiography();return;}
  if(button.dataset.action==='export-world'){download('浮生-时代纪事.md',worldMarkdown(view.world),'text/markdown');return;}
  if(button.dataset.action==='export-backup'){exportBackup();return;}
  if(button.dataset.action==='export-recovery'&&recoveryText){download('浮生-保留的原始存档.json',recoveryText);return;}
  if(button.dataset.action==='new-life'){openNew();return;}
  if(button.dataset.action==='fresh-start'){view=null;renderLanding();return;}
  if(button.dataset.action==='retry'){location.reload();return;}
  if(button.classList.contains('close-dialog'))button.closest('dialog').close();
});
document.addEventListener('submit',event=>{
  if(event.target.id==='people-filter-form'){event.preventDefault();const form=new FormData(event.target);peopleFilters={query:String(form.get('query')||'').trim(),group:form.get('group'),offset:0};loadPeople();return;}
  if(event.target.id==='world-filter-form'){event.preventDefault();const form=new FormData(event.target);worldFilters={domain:form.get('domain'),scope:form.get('scope'),query:String(form.get('query')||'').trim(),highlight:null};render();return;}
  if(event.target.classList.contains('new-form')){event.preventDefault();start(event.target);}
});
$('#menu-button').innerHTML=icon('menu');$('#menu-button').addEventListener('click',()=>{refreshBackupButton();$('#settings-dialog').showModal();});
$('#export-save').addEventListener('click',exportSave);$('#restart').addEventListener('click',openNew);$('#import-save').addEventListener('click',()=>$('#save-file').click());
$('#export-backup').addEventListener('click',exportBackup);
$('#save-file').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  try{if(file.size>20_000_000)throw new Error('这份存档过大。');const imported=JSON.parse(await file.text());const result=await request('/api/resume',{save:imported});keepUpgradeBackup(imported,result);activeTab='life';await applyResult(result);$('#settings-dialog').close();notify('已经回到存档中的那一天。');}
  catch(error){notify(`存档没有替换：${error.message}`);}
  finally{event.target.value='';}
});
async function init(){
  const current=await loadSave(SAVE_KEY);
  const stored=current?JSON.stringify(current):legacySave();
  if(!stored){renderLanding();return;}
  recoveryText=stored;
  try{const previous=JSON.parse(stored);const result=await request('/api/resume',{save:previous});keepUpgradeBackup(previous,result);await applyResult(result);$('#save-status').textContent='已接续上次的人生';}
  catch(error){$('#app').innerHTML=`<section class="error-panel"><span class="eyebrow">稍作停留</span><h2>上次的人生，还留在这里。</h2><p>暂时未能读取自动存档：${esc(error.message)}<br>原始存档没有被删除。可以导出留存、重试，或开始另一段人生。</p><div class="dialog-actions"><button class="button primary" data-action="retry">重试连接 <span>↻</span></button><button class="button secondary" data-action="export-recovery">导出保留的原始存档 <span>↓</span></button><button class="button secondary" data-action="fresh-start">前往新人生 <span>→</span></button></div></section>`;}
}
init();
