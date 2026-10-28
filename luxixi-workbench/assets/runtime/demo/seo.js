'use strict';
let state=Demo.scenario==='error'?null:Demo.seo();let openTicket=null;const selected={};
function hasAttempt(s){return s.project.runs.some(r=>r.suggestion_id===s.id&&r.revision===s.revision&&['attempt','run'].includes(r.kind)&&['started','running','succeeded','no_change','needs_review','needs_reconciliation'].includes(r.status));}
window.addEventListener('message',ev=>{if(ev.source!==parent||ev.data?.kind!=='demo-scenario')return;Demo.setScenario(ev.data.scenario);if(document.querySelector('#detail').open)document.querySelector('#detail').close();refresh();});
const e=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=x=>x===null||x===undefined?'—':Number(x).toLocaleString('zh-CN',{maximumFractionDigits:2});
function localTime(value){if(!value)return '未知';const date=new Date(value);if(Number.isNaN(date.getTime()))return '未知';return date.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});}
function collected(p,end=p.periods?.current?.end){return `搜索更新 ${localTime(p.fetched_at)}（本机时间）${end?` · 数据截至 ${end}`:''}`;}
const cardNumber=(value,suffix='')=>value==null?'暂无':n(value)+suffix;
const names={};
const analyticsLabels={page_view:'浏览页面',session_start:'开始访问',user_engagement:'页面互动',scroll:'滚动页面',ui_click:'点击按钮或链接','Organic Search':'自然搜索',Direct:'直接访问',Referral:'其他网站引荐','(no next action)':'没有后续操作'};
const analyticsLabel=x=>String(x).replace(/^(\d+\. )?(.*)$/,(_,prefix,key)=>(prefix||'')+(analyticsLabels[key]||key));
function crawlNotice(p,compact=false){const h=p.crawl_health;if(!h)return '';const issues=(h.issues||[]).map(i=>i.kind==='sitemap_errors'?`地图报告 ${i.value} 个错误${i.pending?'，正在重新处理':''}`:i.kind==='robots'?'Google记录禁止抓取':`Google保存的抓取结果：${i.value==='ACCESS_FORBIDDEN'?'访问被拒绝（403）':i.value}${i.last_crawl?'（最后抓取 '+localTime(i.last_crawl)+'）':''}`).join('；');const sm=h.sitemap,g=sm?.google;const map=g?`站点地图：${g.isPending?'正在处理':g.lastDownloaded?'已读取':'尚无读取时间'}，${g.errors==null?'错误数未知':g.errors+' 个错误'}`:sm?.registered===false?'站点地图：当前Google属性未登记该地址':'站点地图：读取情况未知';return `<div class="notice"><strong>Google抓取检查 · ${h.status==='issues'?'有异常':h.status==='unknown'?'仍有未知项':'本次未报告错误'}</strong><p>${e(issues?issues+'；'+h.summary:h.summary)}</p><p>${e(map)}</p><p class="small">检查时间 ${e(localTime(h.fetched_at))} · Google保存的记录${compact?'':`；地图最近读取 ${e(localTime(g?.lastDownloaded))}。实时测试通过不代表旧错误已清除或已收录。`}</p></div>`;}
const label=p=>p.name||p.slug;
const badge=(text,tone='blue')=>`<span class="tag ${tone}">${e(text)}</span>`;
const statusBadge=status=>badge(statuses[status]||status, ['proposed','needs_review','blocked','failed','needs_reconciliation'].includes(status)?'amber':['succeeded','approved'].includes(status)?'green':'blue');
const avatar=p=>`<span class="avatar" aria-hidden="true">${e(label(p).slice(0,1))}</span>`;
const statuses={proposed:'待处理',approved:'已批准',deferred:'暂缓',rejected:'已拒绝',succeeded:'执行完成',failed:'失败',blocked:'阻塞',started:'执行中',no_change:'未改动',needs_reconciliation:'待核对',needs_review:'需核对'};
const heading=(title,desc)=>`<header class="heading"><div><h1>${e(title)}</h1><p>${e(desc)}</p></div></header>`;
const suggestAll=()=>state.projects.flatMap(p=>p.suggestions.map(s=>({...s,project:p})));
function sameTicket(a,b){return Boolean(a&&b&&a.id===b.id&&a.revision===b.revision&&a.content_hash===b.content_hash&&a.status===b.status);}
function handoffPrompt(s){return '【合成演示 · 非真实工单，请勿执行】\n项目：'+s.project.name+'；站点：'+s.project.site+'\n工单：'+s.number+'；修订：'+s.revision+'；摘要：'+s.content_hash+'\n目标：'+s.content.title+'\n范围：'+JSON.stringify(s.content.scope)+'\n验证：'+s.content.validation+'\n实际产品需通过安装者自己的本地记录工具核对当前修订、领取、验证和回写同一库；已有执行或发布结果应先核对，不重复执行。复制不改变状态。';}
function chart(p){const range=p.ranges[selected[p.id]||'month'];if(!range)return '';const data=(p.daily||[]).filter(d=>d.date>=range.start&&d.date<=range.end),valid=data.filter(d=>d.clicks!=null);if(!valid.length)return '<p class="card-explain">该时段暂无每日记录，不补零</p>';const day=x=>Date.parse(x+'T00:00:00Z')/86400000,start=day(range.start),end=day(range.end),max=Math.max(1,...valid.map(d=>d.clicks)),segments=[];let segment=[];for(const row of data){if(row.clicks==null){if(segment.length)segments.push(segment);segment=[];continue;}const previous=segment.at(-1);if(previous&&day(row.date)-previous.day>1){segments.push(segment);segment=[];}segment.push({day:day(row.date),point:`${(day(row.date)-start)*440/Math.max(1,end-start)},${64-row.clicks/max*64}`});}if(segment.length)segments.push(segment);return `<div class="mini-trend"><div class="trend-caption">每日搜索点击 · 当前选择范围（合成）</div><svg viewBox="0 -3 440 70" role="img" aria-label="${e(label(p))}每日搜索点击趋势">${segments.map(s=>`<polyline points="${s.map(x=>x.point).join(' ')}" fill="none" stroke="#5275d9" stroke-width="2"/>`).join('')}</svg><div class="trend-caption"><span>${e(range.start)}</span><span>${e(range.end)} · ${valid.length}个有记录日期 · 缺日留空</span></div></div>`;}
function stats(p){
 const d=p.ranges[selected[p.id]||'month'];
 const retained=['no_rows','error'].includes(p.quality)&&d&&(d.clicks!=null||d.impressions!=null),quality=retained?(p.quality==='error'?'已有记录 · 最新采集失败':'已有记录'):d?.complete?'完整数据':'部分数据';
 const head=`<div class="card-data-head"><strong>Google搜索表现</strong><a href="#${e(p.slug)}/performance">详情 →</a>${d?badge(quality+(p.quality==='stale'?' · 已陈旧':''),d.complete&&p.quality!=='stale'&&!retained?'green':'amber'):''}</div><p class="card-explain">网页在Google搜索里被展示、被点击</p>`;
 if(!d||(d.clicks==null&&d.impressions==null))return `<section class="card-data-block">${head}<p class="card-explain">${p.quality==='no_rows'?'暂无搜索记录，不计为零':'该时段没有可用搜索记录'}</p></section>`;
 return `<section class="card-data-block">${head}<div class="project-dates">${e(d.start)} — ${e(d.end)}</div><div class="card-metrics">${[['搜索点击',d.clicks],['搜索展示',d.impressions],['点击率',d.ctr]].map(([k,v])=>`<div><span>${k}</span><strong>${cardNumber(v,k==='点击率'?'%':'')}</strong></div>`).join('')}</div>${retained?`<p class="card-explain">${p.quality==='error'?'最新搜索采集失败':'最新查询未返回新记录'}，显示此前已采集的数据</p>`:''}${!d.complete?`<p class="card-explain">已返回 ${n(d.observed_days)} / ${n(d.days)} 天，数字仅含已有记录</p>`:''}${chart(p)}<p class="card-updated">${e(retained&&p.quality==='error'?`最近采集尝试 ${localTime(p.fetched_at)}（本机时间） · 已有数据截至 ${d.available_end||d.end}`:collected(p,d.available_end||d.end))}</p></section>`;
}
function cardVisits(p){
 const a=p.analytics,r=a?.ranges?.[selected[p.id]||'month'],summary=r?.data?.current?.summary,row=summary?.rows?.[0];
 const limited=summary?.metadata?.subjectToThresholding||summary?.metadata?.samplingMetadatas?.length||summary?.metadata?.dataLossFromOtherRow;
 const available=a&&a.status!=='error'&&a.status!=='not_connected'&&summary?.status==='ok'&&row;
 const head=`<div class="card-data-head"><strong>网站访问</strong><a href="#${e(p.slug)}/behavior">详情 →</a>${available?badge(limited?'数据受限':r.complete?'完整数据':'部分数据',r.complete&&!limited?'green':'amber'):''}</div><p class="card-explain">进入网站后的访问，包含所有来源</p>`;
 if(!available)return `<section class="card-data-block card-visits">${head}<p class="card-explain">${a?.status==='error'||summary?.status==='error'?'访客记录读取失败':r?.status==='waiting_for_processed_data'?'等待统计数据':'暂无可用访客记录，不计为零'}</p></section>`;
 return `<section class="card-data-block card-visits">${head}<div class="project-dates">${e(r.current.start)} — ${e(r.current.end)}</div><div class="card-metrics visits-metrics"><div><span>访客人数</span><strong>${cardNumber(row.totalUsers)}</strong></div><div><span>页面浏览量</span><strong>${cardNumber(row.screenPageViews)}</strong></div></div>${!r.complete?'<p class="card-explain">接入不足所选周期，显示已有日期的统计</p>':''}<p class="card-updated">访问更新 ${e(localTime(a.fetched_at))}（本机时间）${a.stale?' · 记录已陈旧':''}${a.last_attempt&&a.last_attempt.status!=='ok'?' · 最新采集未完成':''}</p></section>`;
}
function card(p){return `<section class="panel project-card" aria-label="${e(label(p))} 项目卡片"><div class="project-card-head"><a class="site" href="#${p.slug}/performance">${avatar(p)}<span><strong>${e(label(p))} ↗</strong><br><span class="small muted">${e(p.site)}</span></span></a><div class="range-switch">${[['week','近一周'],['month','近一个月'],['all','所有时间']].map(([k,v])=>`<button data-range="${k}" data-project="${p.id}" aria-pressed="${(selected[p.id]||'month')===k}">${v}</button>`).join('')}</div></div>${stats(p)}${cardVisits(p)}${crawlNotice(p,true)}<div class="compact-status">${badge(p.suggestions.filter(s=>needsUserAction({...s,project:p})).length+' 项待处理工单',p.suggestions.some(s=>needsUserAction({...s,project:p}))?'amber':'blue')} ${p.seo_enabled===false&&!p.seo_review_enabled?'本项目未纳入定时运行':p.collection_mode==='public-only'&&state.schedule?.unified&&state.schedule.status==='ACTIVE'?'已纳入统一周检查 · 搜索数据尚未接入':state.schedule?.unified&&state.schedule.status==='ACTIVE'?'已纳入统一总任务':'统一任务未启用或状态未知'}</div><div class="project-foot"><a class="link" href="#${p.slug}/plan">任务 →</a></div></section>`;}
function tasks(p){return p.suggestions.length?`<section class="panel"><div class="table-wrap"><table class="rows"><thead><tr><th>编号</th><th>任务</th><th>状态</th><th></th></tr></thead><tbody>${p.suggestions.map(s=>{const a=p.runs.filter(r=>['attempt','run'].includes(r.kind)&&r.suggestion_id===s.id&&r.revision===s.revision).sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||''))[0];const done=['succeeded','no_change'].includes(a?.status);const taskStatus=ticketDisplayState({...s,project:p});return `<tr class="${done?'task-completed':''}"><td class="task-label">${e(s.number)}</td><td class="task-label">${e(s.display_title||s.content.title)}</td><td>${badge(taskStatus,done?'green':a&&a.status!=='started'&&a.status!=='running'?'amber':'blue')}</td><td><button data-suggestion="${s.id}">查看工单</button></td></tr>`;}).join('')}</tbody></table></div></section>`:'<section class="panel empty">暂无本工作流工单；不代表旧项目没有任务。</section>';}
function diagnosis(p){return p.runs.filter(r=>r.kind==='diagnosis').sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||'')).slice(0,1).map(r=>`<section class="panel body"><h2>本轮诊断 · ${e(r.updated_at)}</h2><p>${e(r.summary)}</p><p class="small muted">${e(r.limitations)}</p></section>`).join('');}
function performance(p){return crawlNotice(p)+performanceData(p);}
function performanceData(p){if(p.quality==='no_rows')return '<div class="notice">Search Console已接通；查询窗口暂无数据，不能计为零或比较增长。</div>'+diagnosis(p);if(!p.periods)return '<div class="notice">搜索数据尚未接入，不能判断为零。查看任务清单处理接入事项。</div>'+diagnosis(p);const a=p.periods.current,b=p.periods.previous;return `<section class="date-context"><div>本期 ${a.start} — ${a.end}</div><div>前期 ${b.start} — ${b.end}</div><p>${e(collected(p))} · ${e(({ok:'数据完整',missing:'尚未接入',error:'数据校验失败',partial:'数据不完整',no_rows:'已接通，暂无数据'})[p.quality]||p.quality)} · Search Console</p></section><div class="metrics">${[['点击','clicks'],['展示','impressions'],['点击率','ctr'],['平均排名','position']].map(([k,v])=>`<div class="metric"><span>${k}</span><div class="value">${n(a.metrics[v]===null?null:a.metrics[v]*(v==='ctr'?100:1))}${v==='ctr'?'%':''}</div><span class="small muted">前期 ${n(b.metrics[v]===null?null:b.metrics[v]*(v==='ctr'?100:1))}${v==='ctr'?'%':''}</span></div>`).join('')}</div><section class="panel"><div class="panel-head"><h2>页面表现</h2><span>点击 / 展示</span></div><div class="table-wrap"><table class="rows"><thead><tr><th>页面</th><th>本期</th><th>前期</th><th>点击变化</th><th>本轮处理</th></tr></thead><tbody>${p.pages.map(x=>{const d=x.current&&x.previous?x.current.clicks-x.previous.clicks:null;return `<tr><td>${e(x.url)}</td><td>${n(x.current?.clicks)} / ${n(x.current?.impressions)}</td><td>${n(x.previous?.clicks)} / ${n(x.previous?.impressions)}</td><td>${n(d)}</td><td>${d===null?'缺行，待核对':'待分析，变化不代表处理决定'}</td></tr>`}).join('')}</tbody></table></div><div class="project-foot">缺少页面行显示 —，不补零。页面聚合不加总为全站。</div></section>${p.runs.filter(r=>r.kind==='diagnosis').sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||'')).slice(0,1).map(r=>`<section class="panel body"><h2>本轮诊断 · ${e(r.updated_at)}</h2><p>${e(r.summary)}</p><p class="small muted">${e(r.limitations)}</p></section>`).join('')}`;}
const historyTitles={};
const historyStamp=r=>{const time=Date.parse(r.updated_at||r.created_at||'');return Number.isFinite(time)?time:-Infinity;};
const historyNewest=(a,b)=>historyStamp(b)-historyStamp(a);
function historyRows(p){
 const suggestions=new Map((p.suggestions||[]).map(s=>[s.id,s])),groups=new Map(),checks=[];
 for(const r of p.runs||[]){
  const s=suggestions.get(r.suggestion_id);
  // Group only the same ticket revision; preserve every source record in details.
  if(r.suggestion_id&&['run','attempt'].includes(r.kind)){
   const key=r.suggestion_id+':'+(r.revision??'unknown');
   if(!groups.has(key))groups.set(key,{suggestion:s,records:[]});groups.get(key).records.push(r);
  }else checks.push({record:r,records:[r]});
 }
 const optimizations=[],others=[];
 for(const group of groups.values()){
  group.records.sort(historyNewest);group.record=group.records[0];
  const version=(p.suggestion_bindings||[]).findLast(x=>x.id===group.record.suggestion_id&&x.revision===group.record.revision)||(group.suggestion?.revision===group.record.revision?group.suggestion:null);
  group.reviews=(p.effect_reviews||[]).filter(x=>x.suggestion_id===group.record.suggestion_id&&x.revision===group.record.revision&&group.records.some(r=>r.id===x.deployment_run_id&&(r.content_hash||version?.content_hash)&&(r.content_hash||version?.content_hash)===x.content_hash)).sort((a,b)=>Date.parse(b.checked_at)-Date.parse(a.checked_at));group.review=group.reviews[0];
  const r=group.record,s=group.suggestion,type=r.mutation_type||(s&&r.revision===s.revision?s.content?.mutation_type:null);
  if(!type){group.categoryUnknown=true;others.push(group);}
  else if(!['investigation','analytics','analytics_setup','domain_verification'].includes(type))optimizations.push(group);
  else checks.push(group);
 }
 const sort=(a,b)=>historyNewest(a.record,b.record);
 return {optimizations:optimizations.sort(sort),checks:checks.sort(sort),others:others.sort(sort)};
}
function historyTitle(item){
 const r=item.record,s=item.suggestion;
 if(s&&r.revision===s.revision){const known=historyTitles[s.number];return known&&known.revision===r.revision&&known.source===s.content?.title?known.label:s.display_title||s.content?.title||r.title||'工单执行记录';}
 if(s)return r.title&&!['run','attempt'].includes(r.title)?r.title:`${s.number} · 早期修改记录`;
 const title=String(r.title||''),week=title.match(/\d{4}-W\d{2}/)?.[0];
 if(/GA4.*恢复/.test(title))return '恢复访客统计并补齐数据';
 if(week)return `${r.kind==='diagnosis'?'每周检查结论':'每周数据检查'} · ${week}`;
 if(/analytics-acceptance/.test(title))return '访客统计接入检查';
 if(/acceptance-/.test(title))return '自动检查流程验收';
 if(/首次统一自然触发/.test(title))return '首次自动检查结论';
 if(/试运行/.test(title))return '首次检查试运行';
 if(/第一步诊断进度/.test(title))return '搜索统计接入进度';
 if(!title||['run','attempt','diagnosis'].includes(title))return r.kind==='diagnosis'||r.status==='analysis_complete_pending_decisions'?'搜索表现诊断':'工作记录';
 return title;
}
function historyState(r,isCheck=false){
 const labels=isCheck?{succeeded:'检查完成',no_change:'保持网站现状',failed:'检查失败',blocked:'检查受阻',started:'检查中',running:'检查中',analysis_complete_pending_decisions:'诊断完成，有建议待处理'}:{succeeded:'执行完毕',no_change:'无需修改',failed:'执行失败',blocked:'执行受阻',started:'执行中',running:'执行中'};
 return labels[r.status]||({needs_review:'待核对',needs_reconciliation:'待核对'}[r.status])||'状态未确认';
}
function historyDeployment(r){
 const value=String(r.deployment||'').trim();
 if(!value)return '未记录上线结果';
 if(/^(not_performed|未上线|尚未上线|未发布|没有|未执行|等待)/.test(value))return '未上线';
 if(/^(Vercel(?: production)? READY\b|已上线[：:·\s]|已发布[：:·\s])/.test(value))return '已上线';
 return '上线情况待核对';
}
function historyEffect(r){
 const value=String(r.effect||'').trim();
 if(!value)return '未记录效果';
 if(/^(pending|not_observed|未观察|待观察|尚无)/.test(value))return '效果待观察';
 if(/未证明|不保证|不承诺|不作因果|不归因|未作|不推断/.test(value))return '尚未确认效果';
 return value;
}
function historyNote(value){return ({not_performed:'未执行网站发布',not_observed:'尚未观察效果',read_only_evidence_checked:'已核对只读证据'})[value]||value||'未记录';}
function historyItem(item,isCheck=false){
 const r=item.record,s=item.suggestion,title=historyTitle(item),deployment=historyDeployment(r),effect=item.review?.conclusion||historyEffect(r);
 const effectDetails=item.review?`<p class="history-review-time">最近效果检查：${e(localTime(item.review.checked_at))}（本机时间） · 下次检查：${e(localTime(item.review.next_check_at))}</p><details><summary>查看效果复查历史（${item.reviews.length}次）</summary>${item.reviews.map(x=>`<div class="history-detail"><p>${e(localTime(x.checked_at))}（本机时间）</p><p>${e(x.conclusion)}</p><p>搜索数据截至：${e(x.data_end||'尚无数据')} · ${e(x.metric_scope)}</p>${x.before&&x.after?`<p>上线前：${e(x.before.start)} — ${e(x.before.end)}（已有${n(x.before.observed_days)}/${n(x.before.days)}天）<br>上线后：${e(x.after.start)} — ${e(x.after.end)}（已有${n(x.after.observed_days)}/${n(x.after.days)}天）</p>`:''}</div>`).join('')}</details>`:'';
 const recordDetail=x=>`<div class="history-detail"><p>${e(localTime(x.updated_at||x.created_at))} · ${e(historyState(x,isCheck))}</p>${x.summary||x.reason?`<p>${e(x.summary||x.reason)}</p>`:''}<p>验证：${e(historyNote(x.verification))}</p><p>上线记录：${e(historyNote(x.deployment))}</p><p>效果记录：${e(historyNote(x.effect))}</p></div>`;
 return `<article class="history-item"><div class="history-item-head"><h3>${e(title)}</h3>${badge(historyState(r,isCheck),['failed','blocked','needs_review','needs_reconciliation'].includes(r.status)?'amber':'blue')}</div><p class="history-time">${isCheck?'检查时间':'最近执行记录'} ${e(localTime(r.updated_at||r.created_at))}（本机时间）${s?` · ${e(s.number)} · 第${e(r.revision??'未知')}版`:''}</p>${item.categoryUnknown?'<p>旧版本未记录工作类型，暂不计入网站优化。</p>':''}${isCheck?`<p>${e(r.summary||r.reason||'具体检查说明见下方记录。')}</p>`:`<div class="history-outcome"><div><span>本次上线结果</span><strong class="${deployment==='已上线'?'history-live':''}">${e(deployment)}</strong></div><div><span>效果</span><strong>${e(effect)}</strong></div></div>${effectDetails}`}<details><summary>${item.records.length>1?`查看详细说明与过程（${item.records.length}条记录）`:'查看详细说明'}</summary>${item.records.map(recordDetail).join('')}</details></article>`;
}
function history(p){
 const data=historyRows(p),events=(p.events||[]).slice().sort((a,b)=>Date.parse(b.at)-Date.parse(a.at));
 return `<section class="panel history-section"><div class="panel-head"><h2>网站优化 · ${data.optimizations.length}项</h2><span>最近的在最上面</span></div><p class="history-intro">具体网站修改与执行结果；上线和效果分别记录。</p>${data.optimizations.map(x=>historyItem(x)).join('')||'<p class="empty">尚无网站优化执行记录。</p>'}</section><section class="panel history-section"><div class="panel-head"><h2>检查报告 · ${data.checks.length}项</h2><span>最近的在最上面</span></div><p class="history-intro">每周数据检查、诊断及统计接入，单独保留，不算网站优化。</p>${data.checks.map(x=>historyItem(x,true)).join('')||'<p class="empty">暂无检查报告。</p>'}</section>${data.others.length?`<details class="panel body"><summary>其他历史记录 · ${data.others.length}项（类型待核对）</summary>${data.others.map(x=>historyItem(x)).join('')}</details>`:''}<details class="panel body"><summary>追溯事件（${events.length}）</summary>${events.map(x=>`<p class="small">#${e(x.seq)} · ${e(localTime(x.at))} · ${e(({attempt:'执行过程',run:'执行记录',diagnosis:'诊断记录',suggestion:'优化工单',evidence:'依据'})[x.kind]||'工作记录')}</p>`).join('')}</details>`;
}
function skill(){const r=state.research;const names={integrated:'已融合',no_change:'本轮无适用更新',candidate_ready:'候选待审核',failed:'研究失败',partial:'研究不完整',deferred:'延期'};return heading('SEO 方法 · '+r.method_version,'方法与研究记录')+`<section class="panel body"><p>内容指纹 ${e(state.skill_hash)} · 方法最近融合 ${e(r.last_integrated_date||'未记录')}</p><p>最近完整研究 ${e(r.research_date)} · 最近尝试 ${e(r.last_attempt_date||r.research_date)} · ${e(names[r.status]||r.status)}</p><p>下一研究目标 ${e(r.next_review_target)} · ${r.schedule_enabled?'已纳入唯一SEO总任务':'总任务研究未启用或状态未知'}</p><p>${e(r.last_summary||'')}</p><h2>来源与能力</h2><p>${r.sources.map(e).join(' · ')}</p><p>先核对数据与收录，再选择调查、修改、新增或观察；新建议先查重，保留证据与批准绑定。</p><h2>持续更新流程</h2><p>到期检索开源方法和Google官方变化 → 来源、许可证、权限与适用性评估 → 案例回放和复审 → 候选交你审核 → 融合、记录版本及回退来源。</p><p>没有适用更新也记录；失败保留原因和下次目标。新方法通过审核才影响共用规则，网站修改继续按具体工单批准。</p><h2>待审核候选</h2>${(r.pending_candidates||[]).length?(r.pending_candidates||[]).map(x=>`<p>${e(x.id)} · ${e(x.summary)}<br><span class="small">报告：${e(x.report)}</span></p>`).join(''):'<p>暂无候选需要决定。</p>'}<h2>研究与融合历史</h2>${[...(r.history||[])].reverse().map(x=>`<p><strong>${e(x.date)} · ${e(x.id)} · ${e(names[x.status]||x.status)}</strong><br>${e(x.summary)}<br><span class="small">报告：${e(x.report)}</span></p>`).join('')}<p>历史案例回放不证明流量提升；首次定时研究仍待实际执行验收。</p></section>`;}
function behavior(p){
 const a=p.analytics,key=selected[p.id]||'month';
 const attemptNotice=a?.last_attempt&&a.last_attempt.status!=='ok'?`<p class="notice">最近采集 ${e(localTime(a.last_attempt.at))}：${a.last_attempt.status==='running'?'正在读取':'未完整成功'}。现有数据的时间见下方。</p>`:'';
 const switches=`<div class="range-switch">${[['week','近一周'],['month','近一个月'],['all','所有时间']].map(([k,v])=>`<button data-range="${k}" data-project="${p.id}" aria-pressed="${key===k}">${v}</button>`).join('')}</div>`+attemptNotice;
 if(!a||a.status==='not_connected')return switches+'<section class="panel body">访客统计尚未接入，不能判断为零。</section>';
 if(a.status==='error')return switches+'<div class="notice">访客记录校验失败，暂不展示。</div>';
 const r=a.ranges[key];
 if(!r||r.status==='waiting_for_processed_data')return switches+`<section class="panel body">统计属性已接通，从 ${e(a.first_date||'接入日')} 开始累计，等待 Google 处理数据。本看板预留两天处理时间；新安装的按钮统计没有历史记录。</section>`;
 const cur=r.data.current,prev=r.data.previous;
 const overviewWarnings=[cur.summary,cur.daily,prev?.summary,prev?.daily].filter(Boolean).flatMap(g=>[g.status==='error'?'总指标或趋势读取失败':'',g.metadata?.subjectToThresholding?'总指标或趋势受 Google 隐私阈值限制':'',g.metadata?.samplingMetadatas?.length?'总指标或趋势使用采样':'',g.metadata?.dataLossFromOtherRow?'部分汇总明细被合并':'']).filter(Boolean);
 const rows=(side,g)=>(side?.[g]?.rows||[]).map(x=>({...x,averageEngagement:x.activeUsers?x.userEngagementDuration/x.activeUsers:null}));
 const first=(side)=>rows(side,'summary')[0]||{};
 const c=first(cur),b=first(prev);
 const delta=(x,y)=>x==null||y==null?'—':`${n(x-y)}${y?` (${n((x-y)/y*100)}%)`: '（前期为零）'}`;
 const compareTable=(title,group,keys,metrics)=>{
  const current=rows(cur,group),old=rows(prev,group),id=x=>keys.map(k=>x[k]).join(' · '),prior=new Map(old.map(x=>[id(x),x])),now=new Map(current.map(x=>[id(x),x]));
  const sortMetric=group==='pages'?'averageEngagement':metrics[0][1];
  const ids=[...new Set([...now.keys(),...prior.keys()])].sort((x,y)=>(now.get(y)?.[sortMetric]||0)-(now.get(x)?.[sortMetric]||0));
  const warnings=[cur?.[group],prev?.[group]].filter(Boolean).flatMap(g=>[g.status==='error'?'读取失败，不能判断为零':'',g.excluded_private_rows?`已排除 ${g.excluded_private_rows} 行私有页面`:'',g.metadata?.subjectToThresholding?'Google 隐私阈值可能隐藏部分数据':'',g.metadata?.dataLossFromOtherRow?'部分明细被 Google 合并为其他':'',g.metadata?.samplingMetadatas?.length?'Google 报告使用了采样':'']).filter(Boolean);
  return `<section class="panel"><div class="panel-head"><h2>${title}</h2></div>${warnings.length?`<p class="notice">${[...new Set(warnings)].map(e).join('；')}</p>`:''}<div class="table-wrap"><table class="rows"><thead><tr><th>项目</th>${metrics.map(([label])=>`<th>${label} · 本期</th><th>前期</th><th>变化</th>`).join('')}</tr></thead><tbody>${ids.map(k=>`<tr><td>${k.split(" · ").map(analyticsLabel).map(e).join(" · ")}</td>${metrics.map(([,metric])=>`<td>${n(now.get(k)?.[metric])}</td><td>${n(prior.get(k)?.[metric])}</td><td>${delta(now.get(k)?.[metric],prior.get(k)?.[metric])}</td>`).join('')}</tr>`).join('')||'<tr><td>暂无可展示的数据；缺行不补零。</td></tr>'}</tbody></table></div></section>`;
 };
 const daily=rows(cur,'daily').sort((x,y)=>x.date.localeCompare(y.date));const max=Math.max(1,...daily.map(x=>x.totalUsers));
 const day=x=>Date.parse(x.length===8?`${x.slice(0,4)}-${x.slice(4,6)}-${x.slice(6,8)}T00:00:00Z`:x+'T00:00:00Z')/86400000;
 const start=day(r.current.start),end=day(r.current.end),segments=[];let segment=[];
 daily.forEach((x,i)=>{if(i&&day(x.date)-day(daily[i-1].date)>1){segments.push(segment);segment=[];}segment.push(`${(day(x.date)-start)*800/Math.max(1,end-start)},${100-x.totalUsers/max*100}`);});if(segment.length)segments.push(segment);
 const funnelHTML=(cur.funnels||[]).map(f=>{const old=(prev?.funnels||[]).find(x=>x.title===f.title);const prior=new Map((old?.rows||[]).map(x=>[x.funnelStepName,x]));const next=f.next_actions;return `<section class="panel body"><h2>使用流程 · ${e(f.title)}</h2><p class="small muted">按先后步骤统计同一批用户。新安装事件尚无完整周期，不能据此判断产品流失。${f.status==='error'?'漏斗读取失败。':''}${f.metadata?.samplingMetadatas?.length?'Google 使用了采样。':''}</p><table class="rows"><thead><tr><th>步骤</th><th>本期人数</th><th>前期</th><th>未进入下一步</th></tr></thead><tbody>${(f.rows||[]).map(x=>`<tr><td>${e(analyticsLabel(x.funnelStepName))}</td><td>${n(x.activeUsers)}</td><td>${n(prior.get(x.funnelStepName)?.activeUsers)}</td><td>${n(x.funnelStepAbandonments)}</td></tr>`).join('')||'<tr><td>等待流程数据</td></tr>'}</tbody></table><details><summary>接下来做了什么</summary>${(next?.rows||[]).filter(x=>!x.dimensionValues.some(v=>v.value==='RESERVED_TOTAL')).map(x=>`<p>${x.dimensionValues.map(v=>e(analyticsLabel(v.value))).join(' → ')} · ${n(x.metricValues[0]?.value)} 人</p>`).join('')||'暂无后续操作记录'}</details></section>`;}).join('');
 return switches+`<section class="date-context"><div>本期 ${e(r.current.start)} — ${e(r.current.end)}</div><div>前期 ${r.previous?`${e(r.previous.start)} — ${e(r.previous.end)}`:'暂无同长度历史可比较'}</div><p>${e(a.timezone)} · GA4 · 更新 ${e(localTime(a.fetched_at))}${r.complete?'':' · 接入不足完整周期'}${a.stale?' · 数据已陈旧':''}${a.status==='partial'?' · 部分报告读取失败':''}</p></section>`+
 `${overviewWarnings.length?`<p class="notice">${[...new Set(overviewWarnings)].map(e).join('；')}</p>`:''}`+`<div class="metrics">${[['访客','totalUsers'],['浏览量','screenPageViews'],['访问次数','sessions'],['新访客','newUsers']].map(([title,k])=>`<div class="metric"><span>${title}</span><div class="value">${n(c[k])}</div><span class="small muted">前期 ${n(b[k])} · 变化 ${delta(c[k],b[k])}</span></div>`).join('')}</div>`+
 `<section class="panel body"><h2>每日访客</h2>${daily.length?`<svg viewBox="0 -5 800 115" role="img" aria-label="每日访客趋势">${segments.map(points=>`<polyline points="${points}" fill="none" stroke="#5275d9" stroke-width="2"/>`).join('')}</svg><p>${e(r.current.start)} — ${e(r.current.end)} · 缺日留空</p>`:'暂无趋势'}<p class="small muted">人数按所选时间去重；每日人数不能相加当作总人数。统计受浏览器拦截和用户同意影响。</p></section>`+
 compareTable('流量从哪里来','sources',['sessionDefaultChannelGroup','sessionSourceMedium'],[['访客','totalUsers'],['访问次数','sessions'],['互动访问','engagedSessions']])+
 compareTable('每个页面的表现 · 按人均参与时长排序','pages',['pagePath'],[['访客','totalUsers'],['浏览量','screenPageViews'],['人均参与秒数','averageEngagement']])+
 compareTable('按钮与操作','events',['eventName'],[['人数','totalUsers'],['次数','eventCount']])+
 (cur.buttons?compareTable('每个按钮与问答','buttons',['pagePath','eventName','customEvent:element_id'],[['人数','totalUsers'],['次数','eventCount']]):'')+
 compareTable('不同来源的后续操作','source_events',['sessionDefaultChannelGroup','eventName'],[['人数','totalUsers'],['次数','eventCount']])+
 compareTable('页面操作与滚动','page_events',['pagePath','eventName'],[['人数','totalUsers'],['次数','eventCount']])+funnelHTML+
 '<section class="panel body small muted">参与时长是页面处于前台的互动时间。按钮事件从安装后开始累计；未采集的历史无法补回。私有页面已脱敏或排除。</section>';
}
function render(){if(!state)return;const hash=location.hash.slice(1)||'overview';let content='';document.querySelector('#project-nav').innerHTML=state.projects.map(p=>`<a class="site-link" style="display:block" href="#${p.slug}/performance">${avatar(p)}${e(label(p))}</a>`).join('');document.querySelector('#version').textContent=state.research.method_version;document.querySelector('#crumb').textContent='工作区 / '+hash;
 if(hash==='overview')content=heading('全部项目','每个项目独立查看时间、表现和任务。')+`<section class="date-context"><div><strong>${e(state.schedule?.name||'SEO总任务')}</strong>${state.schedule?.unified&&state.schedule.status==='ACTIVE'?'已启用 · 一个入口管理全部项目':'未启用或配置待核对'}</div><div>${e(state.schedule?.display||'频率未配置')}</div><p>配置状态实时读取；自然触发及结果请看执行历史。页面刷新不会触发任务。</p></section>`+`<div class="project-card-grid">${state.projects.map(card).join('')}</div>`;
 else if(hash==='inbox'){content=heading('待处理工单','查看建议后复制执行提示词，交给 自己的 AI 处理并回写。')+state.projects.map(p=>{const q={...p,suggestions:p.suggestions.filter(s=>needsUserAction({...s,project:p}))};return q.suggestions.length?`<h2>${e(label(p))}</h2>${tasks(q)}`:''}).join('');}
 else if(hash==='skill')content=skill();else{const [slug,view='performance']=hash.split('/');const p=state.projects.find(p=>p.slug===slug);content=p?heading(label(p),p.goal)+`<nav class="tabs">${[['performance','搜索表现'],['behavior','访客与行为'],['plan','任务清单'],['history','执行历史']].map(([k,v])=>`<a class="${view===k?'active':''}" href="#${p.slug}/${k}">${v}</a>`).join('')}</nav>${p.error?`<div class="notice">${e(p.error)}</div>`:''}`+(view==='plan'?tasks(p):view==='history'?history(p):view==='behavior'?behavior(p):performance(p)):'项目不存在';}
 document.querySelectorAll('aside .nav a, aside .site-link, aside .side-foot a').forEach(a=>{const dest=a.getAttribute('href').slice(1);const active=dest===hash||(dest.endsWith('/performance')&&dest.split('/')[0]===hash.split('/')[0]);a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 document.querySelector('#screen').innerHTML=content;document.querySelector('#read-time').textContent='记录读取 '+localTime(state.read_at)+'（本机时间）';
}
async function refresh(){const badge=document.querySelector('#connection');if(Demo.scenario==='error'){badge.textContent='读取失败 · 保留上次记录';badge.className='tag amber';document.querySelector('#alert').innerHTML=state?'<div class="notice">合成读取失败：当前保留上次画面，本轮状态无法确认。</div>':'<div class="notice">合成读取失败：尚无可展示的项目记录。</div>';return;}state=Demo.seo();badge.textContent='合成记录 · 未连接资源';badge.className='tag blue';document.querySelector('#alert').textContent=Demo.scenario==='empty'?'首次安装空库 · 请从顶栏接入设置开始。':'';render();}
document.addEventListener('click',async ev=>{const range=ev.target.closest('[data-range]');if(range){selected[range.dataset.project]=range.dataset.range;render();}const button=ev.target.closest('[data-suggestion]');if(button){const s=suggestAll().find(s=>s.id===button.dataset.suggestion);if(!s)return;openTicket=structuredClone(s);const c=s.content;const prompt=handoffPrompt(openTicket,true);
document.querySelector('#detail-body').innerHTML=`<h3>${e(s.number)} · ${e(s.display_title||c.title)}</h3><p>状态 ${e(ticketDisplayState(s))} · revision ${s.revision}</p>${[['依据',c.rationale],['具体范围',c.scope],['预期',c.expected_effect],['验收',c.validation||c.verification||c.acceptance],['观察',c.observe_after]].map(([k,v])=>`<h3>${k}</h3><p style="white-space:pre-wrap">${e(typeof v==='object'?JSON.stringify(v,null,2):v||'未记录')}</p>`).join('')}<textarea id="prompt" readonly>${e(prompt)}</textarea><button id="copy" data-ticket="${s.id}" ${hasAttempt(s)?'disabled':''}>复制执行提示词</button><p id="copy-result"></p>`;document.querySelector('#detail').showModal();}
if(ev.target.id==='copy'){const latest=suggestAll().find(x=>x.id===ev.target.dataset.ticket);if(!sameTicket(openTicket,latest)){document.querySelector('#copy-result').textContent='工单已更新，请关闭并重新查看后复制；没有复制新范围。';return;}const s=openTicket;if(hasAttempt(latest)){document.querySelector('#copy-result').textContent='已有执行记录，请核对原结果，不重复开工。';return;}const prompt=handoffPrompt(s,true);document.querySelector('#prompt').value=prompt;try{await navigator.clipboard.writeText(prompt);document.querySelector('#copy-result').textContent='已复制';}catch{document.querySelector('#copy-result').textContent='复制失败，请手动复制上方提示词。';}}});
document.querySelector('#detail').addEventListener('close',()=>openTicket=null);
window.__demoSeo={inspect:()=>({scenario:Demo.scenario,state:structuredClone(state),selected:{...selected}}),render,refresh};
render();
document.querySelector('#close').onclick=()=>document.querySelector('#detail').close();document.querySelector('#refresh').onclick=refresh;window.addEventListener('hashchange',render);refresh();setInterval(refresh,30000);

function ticketDisplayState(s){const a=s.project.runs.filter(r=>r.suggestion_id===s.id&&r.revision===s.revision&&['run','attempt'].includes(r.kind)).sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||''))[0];return a?({succeeded:'执行完毕',started:'执行中',running:'执行中',failed:'未完成 / 需核对',blocked:'未完成 / 需核对',needs_reconciliation:'需核对',needs_review:'需核对',no_change:'执行完毕 · 无需改动'}[a.status]||'需核对'):({deferred:'已暂缓',rejected:'已拒绝'}[s.status]||'待处理');}
function needsUserAction(s){return ['待处理','需核对','未完成 / 需核对'].includes(ticketDisplayState(s));}
