"""Same-database, manual read-only SEO inspections; no clock or website executor."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta,date
import hashlib
import json
from pathlib import Path
import secrets
import uuid
from .tickets import Tickets,digest,encoded,identifier
from .onboarding import Onboarding,stamp
from .seo_data import request_plan,calls_from,normalize
from .seo_public import scoped,inspect_public

def load(db,kind,key):return Onboarding.load(db,kind,key)
def save(db,kind,key,value):return Onboarding.save(db,kind,key,value)

class SEO:
    def __init__(self,root,db_id):self.flow=Tickets(root,db_id);self.root=self.flow.root
    def prepare(self,project_id,start=None,end=None,gsc=None,ga4=None,ga_timezone=None,urls=(),inspection_id=None):
        r=Onboarding(self.root).get(identifier(project_id))
        if r['phase']=='cancelled':raise ValueError('接入已取消，不准备巡检')
        if inspection_id:
            stable_id=identifier(inspection_id)
            def previous(db):
                row=db.execute("SELECT payload FROM records WHERE kind='seo_plan' AND id=?",(stable_id,)).fetchone()
                if not row:return None
                old=self.flow.read_owned(self.root/'seo_plans'/(stable_id+'.json'),'seo_plans');entry=json.loads(row[0])
                if digest(old)!=entry['sha256'] or old['database_id']!=self.flow.database_id or old['data_dir']!=str(self.root) or old['project_id']!=project_id or old['revision']!=r['revision']:raise ValueError('既有巡检身份/修订不符')
                for k,value in [('start',start),('end',end)]:
                    if value is not None and value!=old['history_scope'][k]:raise ValueError('同一巡检日期范围冲突')
                for k,value in [('gsc_resource',gsc),('ga4_resource',ga4),('ga4_timezone',ga_timezone)]:
                    if value is not None and value!=old[k]:raise ValueError('同一巡检资源范围冲突')
                if urls and list(dict.fromkeys([r['site'],*[scoped(r['site'],x) for x in urls]]))!=old['urls']:raise ValueError('同一巡检URL范围冲突')
                return {'plan_file':str(self.root/'seo_plans'/(stable_id+'.json')),'plan':old,'scope':'恢复原固定只读计划；未重新采集或改日期'}
            prior=self.flow.tx(previous)
            if prior:return prior
        p=self.flow.tx(lambda db:load(db,'seo_project',project_id));gsc=gsc or r['google']['gsc'].get('resource');ga4=ga4 or r['google']['ga4'].get('resource')
        if not end:end=(datetime.now(timezone.utc).date()-timedelta(days=3)).isoformat()
        if not start:
            start=(date.fromisoformat(end)-timedelta(days=29)).isoformat()
            retained=p.get('history_scope',{}).get('start')
            if retained and 0<=(date.fromisoformat(end)-date.fromisoformat(retained)).days<480:start=min(start,retained)
        ga_timezone=ga_timezone or p.get('analytics',{}).get('timezone')
        if len(urls)>4:raise ValueError('最多选择4个额外公开URL')
        selected=list(dict.fromkeys([r['site'],*[scoped(r['site'],x) for x in urls]]))
        spec=request_plan(r['site'],start,end,gsc,ga4,ga_timezone,selected[:3]);run_id=identifier(inspection_id) if inspection_id else uuid.uuid4().hex
        plan={'inspection_id':run_id,'project_id':project_id,'database_id':self.flow.database_id,'data_dir':str(self.root),'site':r['site'],'revision':r['revision'],'synthetic':r['synthetic'],'created_at':datetime.now(timezone.utc).isoformat(),'challenge':secrets.token_hex(16),'urls':selected,**spec}
        def persist(db):
            old=db.execute("SELECT payload FROM records WHERE kind='seo_plan' AND id=?",(run_id,)).fetchone()
            file=self.root/'seo_plans'/(run_id+'.json')
            if old:
                entry=json.loads(old[0]);prior=self.flow.read_owned(file,'seo_plans')
                if digest(prior)!=entry['sha256'] or any(prior[k]!=plan[k] for k in ['project_id','database_id','data_dir','site','revision','synthetic','urls',*spec]):raise ValueError('同一巡检ID的范围/摘要冲突')
                return file,prior
            if file.exists():raise ValueError('未绑定巡检计划文件，先核对，不自动覆盖')
            self.flow.immutable(Path('seo_plans')/(run_id+'.json'),plan)
            save(db,'seo_plan',run_id,{'sha256':digest(plan),'status':'prepared','project_id':project_id});return file,plan
        file,plan=self.flow.tx(persist)
        return {'plan_file':str(file),'plan':plan,'scope':'只读请求计划；未读取Google/网站，未创建定时或领取工单'}
    def read_plan(self,file):
        plan=self.flow.read_owned(file,'seo_plans');key=identifier(plan['inspection_id']);stored=self.flow.tx(lambda db:load(db,'seo_plan',key))
        if stored['sha256']!=digest(plan) or plan['database_id']!=self.flow.database_id or Path(plan['data_dir'])!=self.root or Path(file).name!=key+'.json':raise ValueError('读取计划同库/摘要身份不符')
        return plan,stored
    def finish(self,plan_file,receipt,transport=None):
        plan,stored=self.read_plan(plan_file)
        if len(encoded(receipt))>8*1024*1024:raise ValueError('读取回执超过8MiB')
        fingerprint=digest(receipt)
        if stored['status']=='recorded':
            if stored['receipt_digest']!=fingerprint:raise ValueError('此巡检已落库，拒绝不同结果覆盖')
            return {'report':self.report(plan['inspection_id']),'idempotent':True,'network_replayed':False}
        calls,observed,stale=calls_from(plan,receipt)
        current=Onboarding(self.root).get(plan['project_id'])
        if current['phase']=='cancelled' or current['revision']!=plan['revision']:raise ValueError('接入已取消或范围变更；拒绝旧巡检计划')
        if plan['synthetic'] and transport is None:raise ValueError('合成巡检必须使用隔离fixture传输，禁止公开网络')
        if not plan['synthetic'] and transport is not None:raise ValueError('真实巡检不能使用合成传输')
        data=normalize(plan,calls,stale)
        def claim_read(db):
            entry=load(db,'seo_plan',plan['inspection_id'])
            if entry['status']!='prepared':return entry
            entry.update(status='collecting',receipt_digest=fingerprint);save(db,'seo_plan',plan['inspection_id'],entry);return {**entry,'new_collector':True}
        entry=self.flow.tx(claim_read)
        if entry.get('receipt_digest')!=fingerprint:raise ValueError('此巡检采集/回写中，拒绝不同回执')
        if entry['status']=='recorded':return {'report':self.report(plan['inspection_id']),'idempotent':True,'network_replayed':False}
        if not entry.get('new_collector'):
            path=self.root/'seo_reports'/(plan['inspection_id']+'.json')
            if not path.exists():raise ValueError('本巡检采集中或中断且尚无报告；不重复采集，可在核对后另建只读巡检计划')
            report=self.flow.read_owned(path,'seo_reports')
            if not entry.get('report_digest') or digest(report)!=entry['report_digest'] or report.get('receipt_digest')!=fingerprint:raise ValueError('已有巡检日志无完整摘要绑定或已被修改，拒绝恢复')
            return self.commit(plan,report)
        public=inspect_public(plan['site'],plan['urls'],transport,plan['synthetic'])
        findings=deepcopy(public['findings'])
        for row in data['index_records']:
            record=row['record']
            if row['status']=='ok' and record.get('pageFetchState') not in {None,'SUCCESSFUL','PAGE_FETCH_STATE_UNSPECIFIED'}:
                code='google-crawl-'+row['url'];findings.append({'key':hashlib.sha256(code.encode()).hexdigest()[:20],'code':'google_crawl','url':row['url'],'title':'核对Google保存的抓取异常','detail':str(record),'evidence_class':'observed'})
            if row['status']=='ok' and record.get('robotsTxtState')=='DISALLOWED':
                code='google-robots-'+row['url'];findings.append({'key':hashlib.sha256(code.encode()).hexdigest()[:20],'code':'google_robots','url':row['url'],'title':'核对Google保存的robots禁止记录','detail':str(record),'evidence_class':'observed'})
        key=plan['inspection_id'];at=datetime.now(timezone.utc).isoformat()
        gaps=stale or data['gsc_status']!='ok' or data['ga4_status']!='ok' or any(x['status']!='ok' for x in public['pages']) or any(g['status']!='ok' for r in data['analytics'].values() for side in r['data'].values() for name,g in side.items() if name not in {'source_events','page_events'}) or any(r['current']['status']!='ok' or not r['current']['complete'] for r in data['searches'].values())
        report={'id':key,'project_id':plan['project_id'],'site':plan['site'],'database_id':self.flow.database_id,'synthetic':plan['synthetic'],'checked_at':at,'observed_at':observed.isoformat(),'receipt_digest':fingerprint,'source':receipt['source'],'status':'completed_with_gaps' if gaps else 'completed','public':public,**data,'findings':findings,'history_scope':plan['history_scope'],'limitations':'只读抽查与客户端MCP回传；HTTP、地图发现、Google保存索引、搜索曝光、网站访问分别记录。无网站修改/发布；变化不证明优化因果。','google_requests':{'requested':len(plan['requests']),'returned':len(calls),'missing':len(plan['requests'])-len(calls)}}
        receipt_path=Path('seo_receipts')/(key+'.json');report_path=Path('seo_reports')/(key+'.json')
        self.flow.immutable(receipt_path,receipt);self.flow.immutable(report_path,report)
        def bind(db):
            entry=load(db,'seo_plan',key)
            if entry['receipt_digest']!=fingerprint:raise ValueError('回执绑定已变化')
            entry['report_digest']=digest(report);save(db,'seo_plan',key,entry)
        self.flow.tx(bind)
        return self.commit(plan,report)
    def commit(self,plan,report):
        key=plan['inspection_id'];fingerprint=report['receipt_digest'];observed=stamp(report['observed_at']);at=report['checked_at']
        def commit(db):
            latest=load(db,'onboarding',plan['project_id']);entry=load(db,'seo_plan',key)
            if entry.get('report_digest')!=digest(report):raise ValueError('完整报告摘要与同库绑定不符')
            if latest['phase']=='cancelled' or latest['revision']!=plan['revision']:raise ValueError('检查期间接入取消/变更；结果未投影')
            if entry['status']=='recorded':
                if entry['receipt_digest']!=fingerprint:raise ValueError('并发巡检回执冲突')
                return {'report':load(db,'seo_inspection',key),'idempotent':True,'network_replayed':False}
            project=load(db,'seo_project',plan['project_id'])
            prior=project.get('last_inspection_at')
            if prior and stamp(prior)>observed:raise ValueError('较旧观测不得覆盖新巡检投影')
            projection=deepcopy(report)
            if datetime.now(timezone.utc)-observed>timedelta(hours=24):
                projection['stale']=True
                for service in ['gsc','ga4']:
                    if plan[service+'_resource']:projection[service+'_status']='stale'
                for r in projection['searches'].values():
                    for side in r.values():side['status']='stale';side['complete']=False
                for r in projection['analytics'].values():r['complete']=False
            self.project(project,latest,plan,projection)
            project['runs'].append({'id':key,'kind':'diagnosis','status':'succeeded' if report['status']=='completed' else 'needs_review','title':'SEO只读巡检'+('（合成）' if plan['synthetic'] else ''),'summary':str(len(report['findings']))+'项需核对观察；GSC '+report['gsc_status']+'，GA4 '+report['ga4_status'],'limitations':report['limitations'],'updated_at':at,'verification':'read_only_evidence_checked','deployment':'not_performed','effect':'not_observed','inspection_id':key})
            save(db,'seo_inspection',key,report);save(db,'seo_project',plan['project_id'],project);save(db,'onboarding',plan['project_id'],latest)
            save(db,'seo_plan',key,{**entry,'status':'recorded','receipt_digest':fingerprint,'report_path':'seo_reports/'+key+'.json'})
            return {'report':report,'idempotent':False,'network_replayed':False}
        return self.flow.tx(commit)
    @staticmethod
    def project(p,onboard,plan,report):
        observed=report['observed_at'];p['last_inspection_at']=observed;p['last_inspection_id']=report['id'];p['inspection_findings']=report['findings'];p['history_scope']=plan['history_scope']
        p.setdefault('search_ranges',{});p.setdefault('ranges',{});p['search_attempts']={}
        for label,raw in report['searches'].items():
            r=deepcopy(raw);previous=p['search_ranges'].get(label,{})
            for period,side in r.items():
                side['fetched_at']=observed;side['pages']['fetched_at']=observed;old=previous.get(period,{})
                if (old.get('start'),old.get('end'))!=(side['start'],side['end']):continue
                if not side['daily'] and old.get('daily'):
                    side.update({k:deepcopy(old[k]) for k in ['daily','metrics','observed_days']});side.update(status='retained',last_attempt_status=raw[period]['status'],fetched_at=old.get('fetched_at',p.get('fetched_at')),complete=False)
                if side['pages']['status'] not in {'ok','partial'} and old.get('pages',{}).get('rows'):
                    side['pages']={**deepcopy(old['pages']),'status':'retained','last_attempt_status':side['pages']['status']};side['complete']=False
            cur=r['current'];p['search_attempts'][label]={'at':observed,'status':cur.get('last_attempt_status',cur['status']),'start':cur['start'],'end':cur['end']}
            if cur['daily'] and not report['stale']:
                p['search_ranges'][label]=r
                p['ranges'][label]={**{k:cur[k] for k in ['start','end','observed_days','days','complete']},**cur['metrics'],'ctr':cur['metrics']['ctr']*100 if cur['metrics']['ctr'] is not None else None,'fetched_at':cur['fetched_at']}
            elif label not in p['ranges']:
                p['search_ranges'][label]=r;p['ranges'][label]={**{k:cur[k] for k in ['start','end','observed_days','days','complete']},**cur['metrics'],'fetched_at':observed}
        active=p['search_ranges'].get('all',report['searches']['all']);cur=report['searches']['all']['current']
        p['quality']='stale' if report['stale'] else 'ok' if cur['complete'] else 'partial' if cur['daily'] else 'no_rows' if cur['status']=='no_rows' else 'error'
        if active['current']['daily'] and (not report['stale'] or not p.get('fetched_at')):p['fetched_at']=active['current'].get('fetched_at',observed)
        p['periods']={k:{f:r[f] for f in ['start','end','metrics']} for k,r in active.items()};p['daily']=active['current']['daily']
        now_pages={x['page']:x for x in active['current']['pages']['rows']};old_pages={x['page']:x for x in active['previous']['pages']['rows']}
        p['pages']=[{'url':url,'current':now_pages.get(url),'previous':old_pages.get(url)} for url in sorted(set(now_pages)|set(old_pages))]
        analytics=p.setdefault('analytics',{});analytics.setdefault('ranges',{});analytics.update(timezone=plan['ga4_timezone'] or '未提供',stale=report['stale'])
        all_ok=True
        for label,raw in report['analytics'].items():
            r=deepcopy(raw);old=analytics['ranges'].get(label)
            for period,groups in r['data'].items():
                same=old and old.get(period)==r[period]
                for name,group in list(groups.items()):
                    group['fetched_at']=observed;prior=old.get('data',{}).get(period,{}).get(name,{}) if same else {}
                    if group['status'] not in {'ok','partial','not_collected'} and prior.get('rows'):
                        groups[name]={**deepcopy(prior),'status':'retained','last_attempt_status':group['status']};r['complete']=False
            summary=r['data']['current']['summary'];usable=summary['status'] in {'ok','partial'} and summary['rows'] and not report['stale']
            if usable or label not in analytics['ranges'] or (old and old['current']==r['current']):analytics['ranges'][label]={**r,'fetched_at':summary.get('fetched_at',observed)}
            if not usable:all_ok=False
            analytics['ranges'][label]['last_attempt']={'at':observed,'status':summary['status'],'requested':r['current'],'retained':not bool(usable)}
        analytics.update(status='ok' if all_ok and report['ga4_status']=='ok' else 'partial',last_attempt={'at':observed,'status':report['ga4_status']})
        if all_ok or not analytics.get('fetched_at'):analytics['fetched_at']=observed
        labels={'ok':'已读取本站数据','not_connected':'尚未连接','missing_tool':'缺少所需工具','permission_denied':'权限不足','site_mismatch':'站点不匹配','binding_unknown':'站点绑定待核验','stale':'回执已陈旧','error':'读取失败','no_rows':'窗口暂无数据','partial':'部分记录可用'}
        for service,status in [('gsc',cur['status'] if report['gsc_status']=='ok' else report['gsc_status']),('ga4',report['ga4_status'])]:
            normalized='read_ok' if status=='ok' else status
            onboard['google'][service]={'status':normalized,'label':labels.get(status,'部分读取待核对'),'observed_at':observed,'resource':plan[service+'_resource'],'source':report['source'],'digest':report['receipt_digest']}
        p['connections']=deepcopy(onboard['google']);onboard['updated_at']=report['checked_at']
        current_rows=report['index_records'];old_health=p.get('crawl_health',{});retained={x['url']:x for x in old_health.get('records',[])}
        for x in current_rows:
            if x['status']=='ok' and not report['stale']:retained[x['url']]=x
            elif x['url'] not in retained:retained[x['url']]=x
        rows=list(retained.values());issues=[]
        for x in rows:
            record=x['record']
            if record.get('pageFetchState') not in {None,'SUCCESSFUL','PAGE_FETCH_STATE_UNSPECIFIED'}:issues.append({'kind':'page_fetch','value':record['pageFetchState'],'last_crawl':record.get('lastCrawlTime')})
        maps=report['google_sitemaps'];map_info=deepcopy(old_health.get('sitemap',{}))
        if maps['status']=='ok' and not report['stale']:
            selected=next((x for x in maps['items'] if x['path'].endswith('/sitemap.xml')),None)
            map_info={'google':selected} if selected else {}
        if map_info.get('google',{}).get('errors',0)>0:issues.append({'kind':'sitemap_errors','value':map_info['google']['errors'],'pending':map_info['google'].get('isPending')})
        p['crawl_health']={'status':'issues' if issues else 'unknown','issues':issues,'summary':str(sum(x['status']=='ok' for x in current_rows))+'个URL本次返回Google保存记录；公开HTTP抽查不代表收录。'+(' Google数据已陈旧。' if report['stale'] else ''),'fetched_at':observed,'sitemap':map_info,'records':rows}
    def report(self,key):return self.flow.tx(lambda db:load(db,'seo_inspection',identifier(key)))
    def propose(self,inspection_id,finding_key):
        report=self.report(inspection_id)
        if datetime.now(timezone.utc)-stamp(report['observed_at'])>timedelta(hours=24):raise ValueError('观察已陈旧，请先新巡检再形成工单')
        finding=next((x for x in report['findings'] if x['key']==finding_key),None)
        if not finding:raise ValueError('本报告无该观察项')
        definition={'kind':'seo','project_id':report['project_id'],'issue_key':'inspection-'+identifier(finding_key),'content':{'title':finding['title'],'rationale':finding['detail'][:3000]+'；证据巡检ID '+report['id'],'scope':'只调查 '+finding['url']+' 的所述问题，先核对原报告和当前情况。未授权网站修改、发布、DNS或账号变化。','validation':'保存实际只读证据及日期，明确是否有意设置、可复现问题或仍缺数据；不以HTTP/聊天完成代替收录或业务结果。','mutation_type':'investigation','external':{'kind':'none','target':None}}}
        key=hashlib.sha256(encoded([definition[k] for k in ['kind','project_id','issue_key']])).hexdigest()[:20]
        def existing(db):
            row=db.execute("SELECT payload FROM records WHERE kind='ticket' AND id=?",(key,)).fetchone();return json.loads(row[0]) if row else None
        old=self.flow.tx(existing)
        return {'ticket':self.flow.view(old) if old else self.flow.create(definition),'existing_issue_no_scope_change':bool(old),'claimed':False}
