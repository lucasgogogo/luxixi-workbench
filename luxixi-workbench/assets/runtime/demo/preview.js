const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=v=>v?new Date(typeof v==='number'?v*1000:v).toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}):'暂无记录';
const cardDate=v=>v?new Date(typeof v==='number'?v*1000:v).toLocaleString('zh-CN',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'}):'暂无记录';
function remaining(at,clock=Date.now()){
  const delta=at-clock;
  if(delta<=0)return '计划时间已到，等待确认是否启动';
  const total=Math.ceil(delta/1000),days=Math.floor(total/86400),hours=Math.floor(total%86400/3600),minutes=Math.floor(total%3600/60),seconds=total%60;
  return '还有 '+(days?days+'天 ':'')+(days||hours?hours+'小时 ':'')+(days||hours||minutes?minutes+'分 ':'')+seconds+'秒';
}
function nextRun(x){
  if(!x.enabled)return '已暂停';
  if(x.continuous_instance)return '持续运行中';
  if(x.required===false)return '需要时打开';
  if(x.collection_stale)return '上次排期 '+cardDate(x.next_run)+'；本轮未读到';
  const at=typeof x.next_run==='number'?x.next_run*1000:Date.parse(x.next_run);
  if(x.next_run&&Number.isFinite(at))return `<span>${cardDate(x.next_run)}</span><span class="countdown" data-next="${at}">${remaining(at)}</span>`;
  if(x.schedule?.includes('MSFT_TaskLogonTrigger'))return '下次登录电脑时启动';
  if(x.schedule?.includes('MSFT_TaskBootTrigger'))return '下次开机时启动';
  return '暂时没有读到下次执行时间';
}
function isFresh(){return connected&&state?.fresh&&Date.now()-state.at*1000<100000;}
function tickCountdown(){document.querySelectorAll('[data-next]').forEach(n=>n.textContent=isFresh()?remaining(Number(n.dataset.next)):'记录已过期，等待重新读取');if(state&&!isFresh()){$('fresh').className='badge fault';$('fresh').textContent='记录已过期，等待重新读取';}}
function executionText(x){
  if(x.execution==='AI 对话已结束'&&x.run_reply_present)return '本轮对话已结束，有处理说明';
  const labels={'AI 对话已结束':'本轮执行已结束，实际产出尚未核验','执行证据未接入':'暂时没有读到本轮执行结果','系统确认任务实例在运行；服务响应未核验':'任务正在运行，服务响应尚未检查','调度器返回 0；业务结果未确认':'本轮程序已结束，返回码 0','尚无执行记录':'尚未首次执行'};
  return labels[x.execution]||x.execution;
}
const health={healthy:'运行中',running:'运行中',waiting:'等待下次执行',fault:'发现异常',unknown:'无法确认',paused:'已暂停'};
const kinds={schedule:'AI 定时任务',heartbeat:'AI 心跳',listener:'持续监听 / 服务',local:'本地计划任务',adapter:'状态读取'};
let state=null,detailId=null,connected=false;
function schedule(s){if(!s)return '未提供';if(!s.includes('FREQ='))return s.replace('MSFT_TaskLogonTrigger','登录时启动').replace('MSFT_TaskTimeTrigger','指定时间触发').replace('MSFT_TaskBootTrigger','开机时启动');const f=Object.fromEntries(s.split('RRULE:').pop().trim().split(';').map(x=>x.split('=')));const days={MO:'周一',TU:'周二',WE:'周三',TH:'周四',FR:'周五',SA:'周六',SU:'周日'};let label={DAILY:'每天',WEEKLY:'每周',HOURLY:'每小时',MINUTELY:'每分钟',YEARLY:'每年',MONTHLY:'每月'}[f.FREQ]||f.FREQ;if(f.INTERVAL&&f.INTERVAL!=='1')label+='（间隔 '+f.INTERVAL+'）';if(f.BYDAY)label+=' '+f.BYDAY.split(',').map(d=>days[d]||d).join('、');if(f.BYHOUR)label+=' '+f.BYHOUR.split(',').map(h=>h.padStart(2,'0')+':'+(f.BYMINUTE||'0').padStart(2,'0')).join('、');return label;}
function route(){return ['overview','tickets','history','seo','skills'].includes(location.hash.slice(1))?location.hash.slice(1):'seo';}
function workspace(){const seo=route()==='seo',skills=route()==='skills',special=seo||skills;$('automationSide').hidden=special;document.querySelector('main').hidden=special;$('seoWorkspace').hidden=!seo;$('skillsWorkspace').hidden=!skills;$('automationTab').className=special?'':'active';$('seoTab').className=seo?'active':'';$('skillsTab').className=skills?'active':'';if(seo&&!$('seoFrame').getAttribute('src'))$('seoFrame').setAttribute('src','seo.html?scenario='+Demo.scenario+'#overview');if(skills)window.skillPage?.show();}
function badge(h,label){return `<span class="badge ${esc(h)}">${esc(label)}</span>`;}
function taskBadge(x){return badge(['healthy','running'].includes(x.health)?'running':x.health,x.health==='waiting'&&x.status_label==='等待启动'?'等待启动':health[x.health]);}
function taskTicket(x){const tickets=state.tickets.filter(t=>t.target===x.id&&!['resolved','archived'].includes(t.state));if(tickets.length)return tickets.map(t=>`<button data-ticket="${t.id}">查看工单 ${esc(t.code)}</button>`).join(' ');return x.uncertainties?.length?'<p class="small">正在生成诊断工单…</p>':'';}
function taskCard(x){
  const actions=taskTicket(x);
  const problem=x.health==='fault'&&x.status_reason&&!x.faults.includes(x.status_reason)?'<p class="faultline">'+esc(x.status_reason)+'</p>':'';
  return `<article class="card task-card"><div class="cardhead"><span class="kind">${esc(kinds[x.kind]||x.kind)}</span>${taskBadge(x)}</div>
    <h3>${esc(x.name)}</h3><dl>
    <dt>运行方式</dt><dd>${esc(schedule(x.schedule))}${x.schedule_note?'<span class="schedule-note">'+esc(x.schedule_note)+'</span>':''}</dd>
    <dt>最近触发</dt><dd>${cardDate(x.last_trigger)}</dd>
    <dt>最近执行结果</dt><dd>${esc(executionText(x))}</dd>
    ${x.kind==='listener'&&x.required!==false?'<dt>最近心跳</dt><dd>'+cardDate(x.heartbeat)+'</dd>':'<dt>下次执行</dt><dd>'+nextRun(x)+'</dd>'}
    <dt>实际结果</dt><dd class="business">${x.collection_stale?'上次记录：':''}${esc(x.business)}${x.business_at?'<span class="small result-time">'+cardDate(x.business_at)+'</span>':''}${x.run_evidence_available?'<button class="result-link" data-evidence="'+esc(x.id)+'">查看执行记录</button>':''}</dd></dl>
    ${problem}${x.faults.map(f=>'<p class="faultline">'+esc(f)+'</p>').join('')}
    ${actions?'<div class="card-actions">'+actions+'</div>':''}</article>`;
}
function render(){
  if(['seo','skills'].includes(route()))return;
  if(!state)return;
  const r=route();
  document.querySelectorAll('#automationSide nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+r));
  $('host').textContent=state.host+' · 本机';
  $('title').textContent={overview:'全部任务',tickets:'待处理工单',history:'历史记录'}[r];
  $('subtitle').textContent='最近检查 '+date(state.at)+' · 时间按当前电脑显示';
  $('fresh').className='badge '+(isFresh()&&state.observation_complete?'healthy':'fault');
  $('fresh').textContent=!isFresh()?'记录已过期，请检查检测器':state.observation_complete?'检测器正在工作':'部分状态读取失败';
  const items=state.items.filter(x=>x.kind!=='adapter'),tickets=state.tickets.filter(t=>!['resolved','archived'].includes(t.state));
  $('totalNav').textContent=items.length;$('ticketNav').textContent=tickets.length;
  const values=[['监测对象',items.length],['发现异常',state.items.filter(x=>x.health==='fault').length],['待处理工单',tickets.length],['已暂停',items.filter(x=>!x.enabled).length]];
  $('stats').innerHTML=values.map(([name,n])=>`<div class="stat"><span>${name}</span><strong>${n}</strong></div>`).join('');
  $('filters').hidden=r!=='overview';
  let html='';
  if(r==='overview'){
    const query=$('search').value.toLowerCase(),kind=$('kind').value;
    const filtered=items.filter(x=>x.name.toLowerCase().includes(query)&&(kind==='all'||(kind==='paused'?!x.enabled:x.kind===kind)));
    html=filtered.length?'<div class="grid">'+filtered.map(taskCard).join('')+'</div>':'<div class="empty">没有匹配的任务</div>';
    const readers=state.items.filter(x=>x.kind==='adapter'&&x.health==='fault');
    if(readers.length)html='<div class="reader-warning">'+readers.map(x=>'<p>'+esc(x.name)+'失败：相关任务保留上次记录，本轮情况无法确认。</p>'+taskTicket(x)).join('')+'</div>'+html;
  }else if(r==='tickets'){
    html=tickets.length?'<div class="list">'+tickets.map(t=>{
      const name=items.find(x=>x.id===t.target)?.name||t.target;
      return `<article class="card ticket"><div><span class="small">${esc(t.code)} · ${esc(name)}</span><h3>${esc(t.fault)}</h3>${badge(t.state,t.state_label)}<p>${esc(t.diagnosis?.summary||'已记录问题，正在等待自动诊断；诊断失败时会明确显示。')}</p><small class="small">首次发现 ${date(t.opened)}</small></div><button data-ticket="${t.id}">查看工单</button></article>`;
    }).join('')+'</div>':'<div class="empty">目前没有待处理工单</div>';
  }else{
    html=state.events.length?'<div class="card">'+state.events.map(e=>`<div class="history"><time>${date(e.at)}</time><button data-ticket="${e.ticket}">AW-${String(e.ticket).padStart(4,'0')}</button><strong>${esc(e.kind)}</strong><span>${esc(e.detail)}</span></div>`).join('')+'</div>':'<div class="empty">暂无工单历史；正常轮询不会反复产生记录</div>';
  }
  $('content').innerHTML=html;
  const c=state.coverage||{};
  $('coverage').textContent=c.scope?`监测范围：${c.scope}。已读到 AI 原生任务 ${c.codex||0} 项、本机计划 ${c.windows||0} 项、服务 ${c.services||0} 项。`+(c.codex_verified?`目录已登记 ${c.registered} 项，缺失 ${c.missing?.length||0} 项，新增 ${c.additional?.length||0} 项。`:'本轮目录对账未完成。')+' 未登记的独立程序与云端任务不在此范围内。':'监测范围正在核对。';
  document.querySelectorAll('[data-ticket]').forEach(b=>b.onclick=()=>openTicket(Number(b.dataset.ticket)));document.querySelectorAll('[data-evidence]').forEach(b=>b.onclick=()=>{const x=state.items.find(x=>x.id===b.dataset.evidence);detailId=null;$('detailBody').innerHTML='<h2>'+esc(x.name)+' · 合成执行记录</h2><div class="detailblock"><h4>执行证据</h4><p>'+esc(executionText(x))+'</p><h4>实际结果</h4><p>'+esc(x.business)+'</p><p>'+cardDate(x.business_at)+'</p></div><p class="small">合成记录，不关联原生聊天或私人文件。</p>';$('detail').showModal();});
  if(detailId&&$('detail').open)renderDetail();
}
function renderDetail(){const t=state.tickets.find(t=>t.id===detailId);if(!t)return;const blocks=[...(t.archive_note?[['归档说明',t.archive_note]]:[]),['原始告警',t.fault],['AI 诊断',t.diagnosis?.summary||'尚未完成'],['判断依据',t.diagnosis?.evidence||'只有连续两轮检查证据，原因尚未确认'],['可能原因',t.diagnosis?.possible_cause||'等待 AI 诊断'],['建议修复范围',t.diagnosis?.repair_scope||'先在 AI 核验，不能依据未知原因直接改生产']];$('detailBody').innerHTML=`<p class="eyebrow">${esc(t.code)} · ${date(t.opened)}</p><h2>${esc(t.fault)}</h2>${badge(t.state,t.state_label)}${blocks.map(([h,v])=>'<div class="detailblock"><h4>'+esc(h)+'</h4><p>'+esc(v)+'</p></div>').join('')}<textarea class="prompt-text" id="automationPrompt" aria-label="执行提示词预览" readonly>${esc(t.prompt)}</textarea><button id="copy" class="primary" ${['resolved','archived','executing'].includes(t.state)?'disabled':''}>复制执行提示词</button><span id="copyresult" class="copyresult" role="status"></span><p class="small">${t.state==='archived'?'此工单已归档，原始证据和处理记录保留；归档不表示业务恢复。':t.type==='uncertainty'?'AI 回写排查结果；取得运行证据后，工单自动更新为“已确认”。':'AI 处理后回写记录；原异常经连续两轮检测确认恢复后，会显示“已恢复”。'}</p><h3>处理记录</h3>${t.events.map(e=>'<p class="small">'+date(e.at)+' · '+esc(e.kind)+' · '+esc(e.detail)+'</p>').join('')}`;$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(t.prompt);$('copyresult').textContent='已复制，粘贴到 AI 即可';}catch{$('copyresult').textContent='复制失败，可手动复制上方文本；工单状态未变';}};}
function openTicket(id){detailId=id;renderDetail();$('detail').showModal();}
$('closeDialog').onclick=()=>{$('detail').close();detailId=null;};$('detail').addEventListener('close',()=>detailId=null);$('search').oninput=render;$('kind').onchange=render;window.onhashchange=()=>{workspace();render();};
async function refresh(){if(Demo.scenario==='error'){connected=false;$('message').textContent=state?'工作台读取失败，当前保留上次合成记录；本轮状态无法确认。':'工作台读取失败，尚无可展示的任务记录。';workspace();render();$('fresh').textContent='读取失败 · 保留上次记录';$('fresh').className='badge fault';tickCountdown();return;}state=Demo.automation();connected=true;$('message').textContent=Demo.scenario==='empty'?'空库演示 · 尚未接入任务；在接入设置中选择允许范围。':'';workspace();render();tickCountdown();}
workspace();refresh();setInterval(refresh,30000);setInterval(tickCountdown,1000);

window.addEventListener('demochange',()=>{if($('detail').open)$('detail').close();detailId=null;window.skillPage?.reset();const frame=$('seoFrame');if(frame.getAttribute('src'))frame.contentWindow?.postMessage({kind:'demo-scenario',scenario:Demo.scenario},'*');refresh();});
$('methodLink').onclick=()=>{$('seoFrame').setAttribute('src','seo.html?scenario='+Demo.scenario+'#skill');};
$('setup').onclick=()=>{$('scenario').value=Demo.scenario;$('setupDialog').showModal();};$('closeSetup').onclick=()=>$('setupDialog').close();$('scenario').onchange=()=>{Demo.setScenario($('scenario').value);window.dispatchEvent(new Event('demochange'));};
window.__demo={inspect:()=>({scenario:Demo.scenario,automation:structuredClone(state)}),refresh,route};
