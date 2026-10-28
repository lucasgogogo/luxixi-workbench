"""Receipts for ONE client-native clock; this module does not implement a timer."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import secrets
from zoneinfo import ZoneInfo
from .tickets import Tickets, identifier, text, shape, digest, encoded
from .onboarding import stamp, forbid_secrets
from .seo import SEO, load, save

def optional(db, kind, key, default=None):
    row = db.execute('SELECT payload FROM records WHERE kind=? AND id=?', (kind,key)).fetchone()
    return json.loads(row[0]) if row else deepcopy(default)

def projection(grouped):
    """Pure GET projection, never contacts or starts the native scheduler."""
    from .methods import baseline
    binding=next(iter(grouped.get('seo_schedule',[])),None)
    research=deepcopy(next(iter(grouped.get('seo_method',[])),baseline()))
    runs=sorted(grouped.get('seo_cycle',[]),key=lambda x:x['started_at']);latest=runs[-1] if runs else None
    schedule={'name':'统一SEO任务','unified':bool(binding and binding.get('native_id')),'status':'UNCONFIGURED','display':'尚未配置','natural_runs':0}
    auto=[]
    if binding:
        try:fresh=datetime.now(timezone.utc)-stamp(binding.get('observed_at'))<=timedelta(hours=24)
        except (ValueError,TypeError):fresh=False
        status=binding['status'] if fresh else 'UNKNOWN' if binding.get('native_id') else 'UNCONFIGURED'
        reported=sum(x['provenance']=='client_reported_scheduled' and x['status']!='running' for x in runs)
        simulated=sum(x['provenance']=='synthetic_scheduled' and x['status']!='running' for x in runs)
        unknown=sum(x['provenance'] in {'client_native_trigger_unknown','synthetic_trigger_unknown'} and x['status']!='running' for x in runs)
        schedule.update(status=status,display=binding['cadence']+' · '+binding['timezone']+' · '+('合成调度回执' if binding.get('source')=='synthetic_native' else '原生配置读回；不保证下次成功'),
                        observed_at=binding.get('observed_at'),next_run_at=binding.get('next_run_at'),native_id=binding.get('native_id'),natural_runs=reported,
                        simulated_runs=simulated,unknown_trigger_runs=unknown,latest_cycle=latest,scope=binding['scope'])
        for p in grouped.get('seo_project',[]):
            onboard=next((x for x in grouped.get('onboarding',[]) if x['id']==p['id']),{})
            enabled=p.get('cycle_state')!='paused' and onboard.get('phase')!='cancelled'
            p['seo_enabled']=enabled and schedule['unified'];p['seo_review_enabled']=p['seo_enabled']
        active=status=='ACTIVE';running=bool(latest and latest['status']=='running' and datetime.now(timezone.utc)-stamp(latest['started_at'])<timedelta(hours=2))
        if binding.get('native_id'):
            auto=[{'id':binding['scope'],'name':'统一SEO巡检','kind':'schedule','enabled':active,'schedule':binding['cadence'],
                   'schedule_note':binding['timezone']+'；同一任务动态读取全部启用网站','health':'running' if active and running else 'waiting' if active else 'paused' if status in {'PAUSED','CANCELLED'} else 'unknown',
                   'last_trigger':latest['started_at'] if latest else None,'next_run':binding.get('next_run_at') if active else None,
                   'execution':('正在处理原周期' if running else '已完成本轮记录' if latest else '尚无执行记录'),
                   'business':('本轮 '+latest['status']+'；'+str(len(latest['projects']))+'站；'+latest['provenance'] if latest else '尚无实际巡检回写')+'；原生报告定时 '+str(reported)+' 次，合成 '+str(simulated)+' 次，触发方式未知 '+str(unknown)+' 次',
                   'business_at':latest.get('finished_at') if latest else None,'faults':[],'uncertainties':[],'collection_stale':not fresh,'run_evidence_available':False}]
    research['schedule_enabled']=schedule['unified'] and schedule['status']=='ACTIVE'
    return schedule,research,auto

class Cycle:
    def __init__(self, root, db_id, clock=None):
        self.flow = Tickets(root, db_id, clock); self.root = self.flow.root

    def plan(self, client, cadence, timezone_name):
        if client not in {'codex_desktop','claude_desktop'}: raise ValueError('需要可访问本库的本机原生持久任务；CLI/session loop/cloud新克隆不适用')
        text(cadence,200); ZoneInfo(timezone_name)
        def run(db):
            old = optional(db,'seo_schedule','unified')
            if old:
                if old['client'] != client or old['cadence'] != cadence or old['timezone'] != timezone_name:
                    raise ValueError('已有统一任务绑定，先核对并更新原生同一任务；不能另建时钟')
                return old
            scope = 'luxixi-seo-' + self.flow.database_id
            value = {'id':'unified','scope':scope,'database_id':self.flow.database_id,'data_dir':str(self.root),
                     'client':client,'cadence':cadence,'timezone':timezone_name,'challenge':secrets.token_hex(16),
                     'status':'UNCONFIGURED','native_id':None,'created_at':self.flow.now().isoformat()}
            save(db,'seo_schedule','unified',value); return value
        result = self.flow.tx(run)
        return {'schedule':result,'instruction':'用当前客户端原生工具先查同scope任务。只创建/复用一项本机持久任务并读回；调度内容动态读取本库全部启用站点，执行cycle begin→逐站巡检/效果复查→到期方法研究→complete。网页服务、手动命令和session loop不证明自然运行。','created_native_task':False}

    def bind(self, receipt):
        shape(receipt,{'scope','database_id','data_dir','challenge','client','native_id','status','cadence','timezone',
                       'persistent','local_files','observed_at','next_run_at','source','tool','evidence'})
        forbid_secrets(receipt); text(receipt['tool'],200)
        if receipt['source'] not in {'client_native','synthetic_native'}: raise ValueError('需要原生工具实际读回；合成回执明确标记')
        if receipt['persistent'] is not True or receipt['local_files'] is not True: raise ValueError('缺独立持久任务/本地文件能力，保持未配置')
        if receipt['status'] not in {'ACTIVE','PAUSED','CANCELLED'}: raise ValueError('原生状态无效')
        identifier(receipt['native_id']); self.flow.evidence(receipt['evidence'],required=True)
        observed=stamp(receipt['observed_at'])
        if abs((self.flow.now()-observed).total_seconds())>300: raise ValueError('原生读回不新鲜')
        if receipt['next_run_at'] is not None and stamp(receipt['next_run_at'])<=observed: raise ValueError('下一执行时间须在读回之后；未知请留null')
        def run(db):
            value=load(db,'seo_schedule','unified')
            for k in ['scope','database_id','data_dir','challenge','client','cadence','timezone']:
                if receipt[k]!=value[k]: raise ValueError('原生任务与本库/计划范围不符')
            if value['native_id'] and value['native_id']!=receipt['native_id']: raise ValueError('同库拒绝第二项原生任务；先核对原绑定')
            if value['status']=='CANCELLED' and receipt['status']!='CANCELLED': raise ValueError('已取消任务不自动恢复')
            value.update({k:deepcopy(receipt[k]) for k in ['native_id','status','next_run_at','observed_at','source','tool','evidence']})
            save(db,'seo_schedule','unified',value); return value
        return self.flow.tx(run)

    def site_state(self, project_id, state):
        if state not in {'enabled','paused'}: raise ValueError('只能明确逐站启用或暂停')
        def run(db):
            onboard=load(db,'onboarding',identifier(project_id))
            if onboard['phase']=='cancelled' and state=='enabled': raise ValueError('接入已取消，先由安装者明确resume')
            p=load(db,'seo_project',project_id);p.update(cycle_state=state,seo_enabled=state=='enabled',seo_review_enabled=state=='enabled')
            save(db,'seo_project',project_id,p);return {'id':project_id,'state':state,'native_tasks_added':0}
        return self.flow.tx(run)

    def begin(self, operation_id, trigger='manual', invocation=None):
        identifier(operation_id)
        if trigger not in {'manual','native'}: raise ValueError('触发类型仅manual/native')
        inv=deepcopy(invocation)
        if trigger=='manual' and inv is not None: raise ValueError('手动运行不能附自然触发证明')
        if trigger=='native':
            shape(inv,{'native_id','run_id','dispatch','scheduled_at','started_at','source','tool','evidence'},{'identity_kind','platform_run_id'})
            if inv['dispatch'] not in {'scheduled','unknown'} or inv['source'] not in {'client_native','synthetic_native'}: raise ValueError('Run now或手动补采不能计自然触发')
            identifier(inv['run_id']);text(inv['tool'],200);self.flow.evidence(inv['evidence'],required=True);forbid_secrets(inv)
            if inv['dispatch']=='scheduled' and inv['scheduled_at'] is None:raise ValueError('确认排期触发需要实际计划时间；缺失只能记录unknown')
            if inv['dispatch']=='unknown':
                if inv['scheduled_at'] is not None:raise ValueError('unknown不能猜填计划时间')
                if inv.get('identity_kind') not in {'conversation_id','observed_invocation_id'}:raise ValueError('unknown需要实际会话/观测身份语义，不能生成平台运行ID')
                if inv.get('platform_run_id') is not None:raise ValueError('平台运行ID未知须保留null')
            if inv['scheduled_at'] is not None and stamp(inv['scheduled_at'])>stamp(inv['started_at']) or stamp(inv['started_at'])>self.flow.now()+timedelta(minutes=5): raise ValueError('触发时间不成立')
        key=hashlib.sha256(encoded([self.flow.database_id,operation_id])).hexdigest()[:32]
        fingerprint=digest([trigger,inv])
        def run(db):
            old=optional(db,'seo_cycle',key)
            if old:
                if old['input_digest']!=fingerprint: raise ValueError('重复operation的来源/回执冲突')
                return old
            binding=optional(db,'seo_schedule','unified')
            if trigger=='native':
                if not binding or binding['status']!='ACTIVE' or binding['native_id']!=inv['native_id'] or binding['source']!=inv['source']: raise ValueError('原生触发与当前唯一任务绑定不符')
                if self.flow.now()-stamp(binding['observed_at'])>timedelta(hours=24): raise ValueError('原生状态已陈旧，先读回')
                if stamp(inv['started_at'])<stamp(binding['created_at']) or self.flow.now()-stamp(inv['started_at'])>timedelta(hours=24): raise ValueError('拒绝旧触发')
                for row in db.execute("SELECT payload FROM records WHERE kind='seo_cycle'"):
                    other=json.loads(row[0])
                    if other.get('invocation',{}).get('run_id')==inv['run_id']: raise ValueError('同一原生运行不能换operation重放')
            open_runs=[json.loads(r[0])['id'] for r in db.execute("SELECT payload FROM records WHERE kind='seo_cycle'") if json.loads(r[0])['status']=='running']
            if open_runs: raise ValueError('已有未收尾巡检，请按原operation核对/继续：'+open_runs[0])
            projects={r['id']:r for (raw,) in db.execute("SELECT payload FROM records WHERE kind='seo_project'") for r in [json.loads(raw)]}
            items={}
            for (raw,) in db.execute("SELECT payload FROM records WHERE kind='onboarding'"):
                r=json.loads(raw);p=projects[r['id']]
                if r['phase']=='cancelled' or p.get('cycle_state')=='paused': continue
                items[r['id']]={'revision':r['revision'],'site':r['site'],'synthetic':r['synthetic'],'status':'pending',
                                'inspection_id':hashlib.sha256(encoded([key,r['id']])).hexdigest()[:32]}
            value={'id':key,'operation_id':operation_id,'input_digest':fingerprint,'database_id':self.flow.database_id,'trigger':trigger,
                   'invocation':inv or {},'provenance':'manual' if trigger=='manual' else ('synthetic_trigger_unknown' if inv['source']=='synthetic_native' else 'client_native_trigger_unknown') if inv['dispatch']=='unknown' else 'synthetic_scheduled' if inv['source']=='synthetic_native' else 'client_reported_scheduled',
                   'started_at':self.flow.now().isoformat(),'status':'running','projects':items,'research_id':None}
            save(db,'seo_cycle',key,value);return value
        return self.flow.tx(run)

    def get(self, key): return self.flow.tx(lambda db:load(db,'seo_cycle',identifier(key)))

    def prepare_project(self, key, project_id, **kwargs):
        cycle=self.get(key);item=cycle['projects'].get(identifier(project_id))
        if cycle['status']!='running' or not item: raise ValueError('本轮未包含该站点或已收尾')
        onboard=self.flow.tx(lambda db:load(db,'onboarding',project_id));p=self.flow.tx(lambda db:load(db,'seo_project',project_id))
        if onboard['phase']=='cancelled' or onboard['revision']!=item['revision'] or p.get('cycle_state')=='paused': raise ValueError('站点已暂停/取消/修订变化，停止该站')
        return SEO(self.root,self.flow.database_id).prepare(project_id,inspection_id=item['inspection_id'],**kwargs)

    def record_project(self, key, project_id, error=None):
        if error is not None: text(error,1000);forbid_secrets(error)
        def run(db):
            cycle=load(db,'seo_cycle',identifier(key));item=cycle['projects'].get(identifier(project_id))
            if not item: raise ValueError('本轮未包含该站点')
            if item['status']!='pending': return cycle
            if cycle['status']!='running': raise ValueError('本轮已收尾')
            onboard=load(db,'onboarding',project_id);p=load(db,'seo_project',project_id)
            if onboard['phase']=='cancelled' or p.get('cycle_state')=='paused' or onboard['revision']!=item['revision']:
                item.update(status='skipped',reason='站点已暂停/取消/修订变化')
            elif error is not None:
                item.update(status='failed',reason=error)
                definition={'kind':'seo','project_id':project_id,'issue_key':'cycle-collection-interrupted','content':{
                    'title':'核对本站巡检流程中断','rationale':error+'；周期 '+key,'scope':'只读核对此站巡检中断，未授权网站修改、发布或恢复暂停任务。',
                    'validation':'下一轮本站同库完整绑定报告并有实际响应才确认流程恢复；Google数据和HTTP异常另行判断。','mutation_type':'investigation','external':{'kind':'none','target':None}}}
                ticket_id=hashlib.sha256(encoded([definition[k] for k in ['kind','project_id','issue_key']])).hexdigest()[:20]
                ticket=optional(db,'ticket',ticket_id);condition='collector-'+project_id
                if not ticket:
                    self.flow.create(definition,connection=db);ticket=Tickets.load(db,ticket_id)
                    ticket['monitor_origin']={'project_id':project_id,'condition':condition,'first_cycle':key,'content_hash':ticket['content_hash']};self.flow.save(db,ticket)
                health=optional(db,'seo_health',ticket_id,{'id':ticket_id,'project_id':project_id,'condition':condition,'history':[]})
                health['history'].append({'cycle_id':key,'inspection_id':None,'bad':True,'observed_at':self.flow.now().isoformat(),'evidence_at':self.flow.now().isoformat(),'detail':error})
                health['status']='open';save(db,'seo_health',ticket_id,health)
                if ticket.get('observation_resolution') and not ticket.get('claim') and not ticket['attempts']:
                    ticket.update(state='pending',reason='同一巡检流程再次中断；复用原监测单');ticket.pop('observation_resolution',None);self.flow.event(ticket,'observed_recurrence',ticket['reason']);self.flow.save(db,ticket)
            else:
                report=load(db,'seo_inspection',item['inspection_id'])
                if report['database_id']!=self.flow.database_id or report['project_id']!=project_id or stamp(report['checked_at'])<stamp(cycle['started_at']): raise ValueError('报告不属于本轮本站同库')
                item.update(status='recorded',report_digest=digest(report),observed_at=report['observed_at'],data_status=report['status'],post_status='pending')
            save(db,'seo_cycle',key,cycle);return cycle
        result=self.flow.tx(run)
        if result['projects'][project_id]['status']=='recorded':
            from .effects import Effects
            try:
                Effects(self.root,self.flow.database_id).review_project(project_id,result['projects'][project_id]['inspection_id'])
                self.health(project_id,result['projects'][project_id]['inspection_id']);post_status='done';reason=None
            except (ValueError,OSError) as error:post_status='failed';reason=str(error)[:300]
            def post(db):
                latest=load(db,'seo_cycle',key);latest['projects'][project_id].update(post_status=post_status,post_error=reason);save(db,'seo_cycle',key,latest);return latest
            result=self.flow.tx(post)
        return result

    def health(self,project_id,inspection_id):
        """Observation recovery only; never closes an execution that someone claimed."""
        identifier(project_id)
        report=SEO(self.root,self.flow.database_id).report(inspection_id)
        if report['project_id']!=project_id or report['database_id']!=self.flow.database_id:raise ValueError('健康证据错站/错库')
        if report['stale'] or self.flow.now()-stamp(report['observed_at'])>timedelta(hours=24): return {'observed':False}
        observations=[]
        if any(isinstance(p.get('http_status'),int) for p in report['public']['pages']) or report['gsc_status'] in {'ok','partial','no_rows'} or report['ga4_status'] in {'ok','partial','no_rows'} or any(x['status']=='ok' for x in report['index_records']):
            observations.append(('collector-'+project_id,False,report['site'],'有限巡检流程已返回同库绑定结果；各来源缺口另列',report['checked_at']))
        for page in report['public']['pages']:
            status=page.get('http_status',page.get('status_code'))
            # The public checker explicitly separates successful HTTP observations from errors.
            if page.get('status') in {'ok','http_error'} and isinstance(status,int): observations.append(('public-'+page['url'],status>=400,page['url'],str(status),report['checked_at']))
        for row in report['index_records']:
            record=row['record'];last=record.get('lastCrawlTime')
            # A newly read old Google record is NOT fresh recovery evidence.
            if row['status']=='ok' and last and timedelta(0)<=self.flow.now()-stamp(last)<=timedelta(days=7):
                state=record.get('pageFetchState')
                if state and state!='PAGE_FETCH_STATE_UNSPECIFIED': observations.append(('google-'+row['url'],state!='SUCCESSFUL',row['url'],state,last))
        output=[]
        for condition,bad,url,note,evidence_at in observations:
            finding_key=hashlib.sha256((('http_error|'+url) if condition.startswith('public-') else ('google-crawl-'+url)).encode()).hexdigest()[:20]
            issue='cycle-collection-interrupted' if condition.startswith('collector-') else 'inspection-'+finding_key
            definition={'kind':'seo','project_id':project_id,'issue_key':issue,'content':{
                'title':'核对本站抓取/响应异常','rationale':url+' 本轮 '+note+'；巡检 '+inspection_id,
                'scope':'只读核对本站该异常，未授权网站修改、发布或恢复暂停任务。','validation':'保存本站新鲜响应/Google抓取日期与证据；旧记录不能作恢复。',
                'mutation_type':'investigation','external':{'kind':'none','target':None}}}
            ticket_id=hashlib.sha256(encoded([definition[k] for k in ['kind','project_id','issue_key']])).hexdigest()[:20]
            def update(db):
                current=load(db,'seo_inspection',inspection_id);bound=load(db,'seo_plan',inspection_id)
                if current['project_id']!=project_id or digest(current)!=digest(report) or bound.get('report_digest')!=digest(current):raise ValueError('健康报告完整身份不符')
                onboard=load(db,'onboarding',project_id);p=load(db,'seo_project',project_id)
                if onboard['phase']=='cancelled' or p.get('cycle_state')=='paused':return
                if p.get('last_inspection_id')!=inspection_id:raise ValueError('只接受本站最新完整绑定的健康观察')
                t=optional(db,'ticket',ticket_id)
                if bad and not t:
                    self.flow.create(definition,connection=db);t=Tickets.load(db,ticket_id)
                    t['monitor_origin']={'project_id':project_id,'condition':condition,'first_inspection':inspection_id,'content_hash':t['content_hash']};self.flow.save(db,t)
                if not t:return
                old=optional(db,'seo_health',ticket_id,{'id':ticket_id,'project_id':project_id,'condition':condition,'history':[]})
                if any(x['inspection_id']==inspection_id for x in old['history']):return
                if old['history'] and stamp(evidence_at)<=stamp(old['history'][-1]['evidence_at']):return
                old['history'].append({'inspection_id':inspection_id,'bad':bad,'observed_at':report['observed_at'],'evidence_at':evidence_at,'detail':note})
                old['status']='open' if bad else 'recovered';save(db,'seo_health',ticket_id,old)
                monitor=t.get('monitor_origin',{})
                can_resolve=monitor.get('project_id')==project_id and monitor.get('condition')==condition and monitor.get('content_hash')==t['content_hash'] and not t.get('claim') and not t['attempts']
                if not bad and can_resolve and t['state']=='pending':
                    t.update(state='completed',reason='本监测项已由本站新鲜证据恢复；没有执行网站修复',observation_resolution={'inspection_id':inspection_id,'observed_at':report['observed_at']})
                    self.flow.event(t,'observed_recovery',t['reason']);self.flow.save(db,t)
                elif bad and can_resolve and t.get('observation_resolution'):
                    t.update(state='pending',reason='同一监测项再次出现；复用原单');t.pop('observation_resolution',None);self.flow.event(t,'observed_recurrence',t['reason']);self.flow.save(db,t)
                output.append(old)
            self.flow.tx(update)
        return {'observed':True,'items':output}

    def complete(self,key):
        from .methods import Methods
        research_due=Methods(self.root,self.flow.database_id).due()
        def run(db):
            cycle=load(db,'seo_cycle',identifier(key))
            if cycle['status']!='running':return cycle
            if any(x['status']=='pending' for x in cycle['projects'].values()): raise ValueError('还有未记录站点，不能伪称巡检完成')
            if any(x['status']=='recorded' and x.get('post_status')=='pending' for x in cycle['projects'].values()):raise ValueError('效果/健康回写尚未完成，继续原周期')
            if research_due and not cycle.get('research_id'):raise ValueError('方法研究已到期，请记录本轮实际成功/失败及缺口')
            gaps=any(x['status']!='recorded' or x.get('data_status')!='completed' or x.get('post_status')=='failed' for x in cycle['projects'].values()) or cycle.get('research_status') in {'partial','failed'}
            cycle.update(status='completed_with_gaps' if gaps else 'completed',finished_at=self.flow.now().isoformat())
            save(db,'seo_cycle',key,cycle);return cycle
        return self.flow.tx(run)
