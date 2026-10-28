(() => {
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const packageName = name => name;
  let data = null, category = 'all', loading = false, lastRequest = 0;
  function render() {
    if (!data) return;
    const items = data.items || [], categories = data.categories || [];
    el('skillTotal').textContent = data.at ? `${items.length} 个（含禁用项）` : '';
    el('skillsChecked').textContent = data.at ? '清单更新 '+new Date(data.at*1000).toLocaleString('zh-CN',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'})+'（本机时间）' : '尚未读到清单';
    el('skillsNotice').textContent = data.status==='unavailable' ? (data.at ? '本轮读取失败，下面保留的是上次清单。' : '暂时无法读取本机Skill，请稍后重新读取。') : data.status==='partial' ? '部分技能资料读取失败，当前仅显示已确认的技能。' : '';
    el('skillsCategories').innerHTML = [{id:'all',name:'全部'},...categories].map(c=>`<button data-skill-category="${escape(c.id)}" aria-pressed="${category===c.id}" class="${category===c.id?'selected':''}">${escape(c.name)} <span>${c.id==='all'?items.length:items.filter(x=>x.category===c.id).length}</span></button>`).join('');
    el('skillsCategories').querySelectorAll('[data-skill-category]').forEach(button=>button.onclick=()=>{category=button.dataset.skillCategory;render();});
    const query = el('skillsSearch').value.trim().toLocaleLowerCase();
    const filtered = items.filter(x=>(category==='all'||x.category===category)&&[x.title,x.name,x.summary,x.description,x.package].some(v=>String(v||'').toLocaleLowerCase().includes(query)));
    el('skillsMatches').textContent = `显示 ${filtered.length} 个`;
    el('skillsContent').innerHTML = filtered.length ? categories.filter(c=>filtered.some(x=>x.category===c.id)).map(c=>`<section class="skill-group"><h2>${escape(c.name)} <span>${filtered.filter(x=>x.category===c.id).length}</span></h2><div class="skills-grid">${filtered.filter(x=>x.category===c.id).map(x=>`<article class="skill-card ${x.enabled===false?'skill-disabled':''}"><h3>${escape(x.title)}</h3><p class="skill-name">${escape(x.name)}</p><p class="skill-state">${x.enabled===false?'已禁用 · 不自动恢复':x.enabled===true?'已启用':'启用状态未知'}</p><p class="skill-summary">${escape(x.summary)}</p><p class="skill-capability">${escape(x.capability)} · ${escape(x.version||'版本未知')}</p><div class="skill-source">${escape(x.source)}${x.package?' · '+escape(packageName(x.package)):''}</div></article>`).join('')}</div></section>`).join('') : `<p class="empty">${data.status==='unavailable'&&!data.at?'尚未读到Skill清单':'没有符合条件的Skill'}</p>`;
  }
  async function load(force=false) {
    if (loading || (!force && Date.now()-lastRequest<60000)) return;
    loading=true;lastRequest=Date.now();el('skillsReload').disabled=true;el('skillsReload').textContent='读取中…';
    try {
      const response=await fetch('/api/skills',{cache:'no-store'});if(!response.ok)throw Error('read_failed');
      const next=await response.json();if(!Array.isArray(next.items)||!Array.isArray(next.categories))throw Error('invalid_data');
      data=next;render();
    } catch {
      if(data){data={...data,status:'unavailable',fresh:false};render();}
      else el('skillsNotice').textContent = '暂时无法读取本机Skill，请稍后重新读取。';
      if(!data)el('skillsContent').innerHTML='<p class="empty">尚未读到Skill清单</p>';
    } finally {loading=false;el('skillsReload').disabled=false;el('skillsReload').textContent='重新读取';}
  }
  el('skillsSearch').oninput=render;
  el('skillsReload').onclick=()=>load(true);
  window.skillPage={reset:()=>{lastRequest=0;category='all';el('skillsSearch').value='';load(true);},show:()=>{render();load();}};
  setInterval(()=>{if(location.hash==='#skills')load();},60000);
})();
