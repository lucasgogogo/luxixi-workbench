"""Descriptive GSC follow-up attached to the original confirmed deployment."""
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
import hashlib
import json
from .tickets import Tickets, digest, encoded, identifier
from .onboarding import stamp
from .seo import load, save, SEO

class Effects:
    def __init__(self,root,db_id): self.flow=Tickets(root,db_id);self.root=self.flow.root

    def deployments(self,project_id):
        def read(db):
            output=[]
            for (raw,) in db.execute("SELECT payload FROM records WHERE kind='ticket'"):
                t=json.loads(raw)
                if t['kind']!='seo' or t['project_id']!=project_id or t['state']!='completed' or t['content']['mutation_type'] not in {'technical_fix','content_update'}:continue
                for a in t['attempts']:
                    r=a.get('result')
                    if not r or r['revision']!=t['revision'] or r['content_hash']!=t['content_hash'] or r['outcome'] not in {'succeeded','no_change'} or r['external']['status']!='confirmed_success' or r['verification']['status']!='passed':continue
                    if t['receipts'].get(r['receipt_id'])!=digest(r):raise ValueError('原上线回执摘要已变化')
                    original=self.flow.read_owned(self.root/'receipts'/(t['id']+'-'+r['receipt_id']+'.json'),'receipts')
                    if original!=r:raise ValueError('原上线不可变回执不符')
                    self.flow.evidence(r['external']['evidence'],required=True)
                    for c in r['verification']['checks']:self.flow.evidence(c['evidence'],required=True)
                    output.append({'ticket_id':t['id'],'revision':t['revision'],'content_hash':t['content_hash'],'attempt_id':a['attempt_id'],
                                   'deployed_at':r.get('deployed_at'),'publication_observed_at':r['observed_at'],'deployment_receipt_id':r['receipt_id'],'synthetic':t['synthetic']})
            return output
        return self.flow.tx(read)

    def review_project(self,project_id,inspection_id):
        project_id=identifier(project_id);report=SEO(self.root,self.flow.database_id).report(inspection_id)
        if report['project_id']!=project_id:raise ValueError('效果证据错站')
        deployments=self.deployments(project_id);output=[]
        from zoneinfo import ZoneInfo
        tz=ZoneInfo('America/Los_Angeles')
        window=report['searches']['all']['current'];rows={x['date']:x for x in window['daily']}
        for d in deployments:
            day=stamp(d['deployed_at']).astimezone(tz).date() if d['deployed_at'] else None
            latest=date.fromisoformat(window['end']);elapsed=(latest-day).days if day else 0
            periods=[n for n in [7,15,30] if elapsed>=n] or [7]
            for days in periods:
                key=hashlib.sha256(encoded([d,inspection_id,days])).hexdigest()[:32]
                def record(db):
                    old=db.execute("SELECT payload FROM records WHERE kind='seo_effect' AND id=?",(key,)).fetchone()
                    if old:return json.loads(old[0])
                    journal=db.execute("SELECT payload FROM records WHERE kind='seo_effect_plan' AND id=?",(key,)).fetchone()
                    if journal:
                        bound=json.loads(journal[0])
                        if bound['source_digest']!=digest([d,report]) or bound['value_digest']!=digest(bound['value']):raise ValueError('效果恢复完整摘要/来源不符')
                        return bound['value']
                    onboard=load(db,'onboarding',project_id);p=load(db,'seo_project',project_id)
                    if onboard['phase']=='cancelled' or p.get('cycle_state')=='paused':raise ValueError('站点已暂停/取消，不更新效果')
                    def period(start,end):
                        dates=[(start+timedelta(days=i)).isoformat() for i in range(days)];data=[rows[x] for x in dates if x in rows]
                        return {'start':start.isoformat(),'end':end.isoformat(),'days':days,'observed_days':len(data),
                                'clicks':sum(x['clicks'] for x in data) if data else None,'impressions':sum(x['impressions'] for x in data) if data else None}
                    before=period(day-timedelta(days=days),day-timedelta(days=1)) if day else None;after=period(day+timedelta(days=1),day+timedelta(days=days)) if day else None
                    checked=self.flow.now()
                    stale=report['stale'] or checked-stamp(report['observed_at'])>timedelta(hours=24)
                    full=day is not None and window['status']=='ok' and not stale and before['observed_days']==days and after['observed_days']==days and elapsed>=days
                    enough=full and all(x['impressions']>=100 and x['clicks']>=5 for x in [before,after])
                    overlaps=bool(day and sum(bool(x['deployed_at']) and abs((stamp(x['deployed_at']).astimezone(tz).date()-day).days)<=days for x in deployments)>1)
                    status='descriptive' if enough else 'observing'
                    if not day:conclusion='继续观察：原记录缺真实上线时间，未用确认回执时间代替发布时刻；无法划分前后窗口。'
                    elif not full:conclusion='继续观察：数据窗口不足、缺日、读取失败或陈旧；未补零。'
                    elif not enough:conclusion='继续观察：样本不足（本地提示阈值为每窗100展示及5点击，不是显著性检验）。'
                    else:conclusion='同长度窗口的本站搜索点击由'+str(before['clicks'])+'变为'+str(after['clicks'])+'；仅描述变化，不能归因于本次优化。'
                    if overlaps:conclusion+=' 同期有其他上线记录，影响无法分离。'
                    observed=stamp(report['observed_at']);prior=[x for x in p.get('effect_reviews',[]) if x['suggestion_id']==d['ticket_id'] and x['revision']==d['revision']]
                    if any(stamp(x['observed_at'])>observed for x in prior):raise ValueError('较旧巡检不能覆盖较新效果记录')
                    value={'id':key,'suggestion_id':d['ticket_id'],'revision':d['revision'],'content_hash':d['content_hash'],'deployment_run_id':d['attempt_id'],
                           'deployment_receipt_id':d['deployment_receipt_id'],'deployed_at':d['deployed_at'],'synthetic':d['synthetic'],'inspection_id':inspection_id,
                           'checked_at':checked.isoformat(),'observed_at':report['observed_at'],'status':status,'period_days':days,'before':before,'after':after,
                           'conclusion':conclusion,'metric_scope':'本站范围最终web搜索，America/Los_Angeles；非所改页面因果，不包含GA4用户/收入',
                           'data_end':window['end'],'next_check_at':(checked+timedelta(days=7)).isoformat(),'confounded':overlaps,
                           'click_change_percent':round((after['clicks']-before['clicks'])/before['clicks']*100,2) if enough and before['clicks'] else None}
                    save(db,'seo_effect_plan',key,{'source_digest':digest([d,report]),'value_digest':digest(value),'value':value})
                    return value
                value=self.flow.tx(record)
                self.flow.immutable(Path('seo_effects')/(key+'.json'),value)
                def commit(db):
                    old=db.execute("SELECT payload FROM records WHERE kind='seo_effect' AND id=?",(key,)).fetchone()
                    if old:
                        if json.loads(old[0])!=value:raise ValueError('已有效果内容冲突')
                        return value
                    bound=load(db,'seo_effect_plan',key)
                    if bound['source_digest']!=digest([d,report]) or bound['value_digest']!=digest(value):raise ValueError('效果投影绑定不符')
                    current=load(db,'seo_inspection',inspection_id);ticket=Tickets.load(db,d['ticket_id'])
                    if digest(current)!=digest(report) or ticket['revision']!=d['revision'] or ticket['content_hash']!=d['content_hash']:raise ValueError('效果来源修订/报告已变化')
                    onboard=load(db,'onboarding',project_id);p=load(db,'seo_project',project_id)
                    if onboard['phase']=='cancelled' or p.get('cycle_state')=='paused':raise ValueError('站点暂停，不投影效果')
                    prior=[x for x in p.get('effect_reviews',[]) if x['suggestion_id']==d['ticket_id'] and x['revision']==d['revision']]
                    if any(stamp(x['observed_at'])>stamp(report['observed_at']) for x in prior):raise ValueError('旧恢复不能覆盖新效果')
                    p.setdefault('effect_reviews',[]).append(value);save(db,'seo_project',project_id,p);save(db,'seo_effect',key,value);return value
                output.append(self.flow.tx(commit))
        return {'items':output,'website_changed':False,'new_tickets':0}
