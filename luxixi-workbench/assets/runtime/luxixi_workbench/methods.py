"""Versioned research receipts; no downloaded code installation or automatic fusion."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
from .tickets import Tickets,shape,text,identifier,digest,encoded
from .onboarding import stamp,forbid_secrets
from .seo import load,save
from .cycle import optional

BASELINE={'version':'0.6.0','capabilities':['有限公开抽查','GSC最终web搜索与GA4分离','缺失不补零','同库唯一原生任务绑定','原优化记录效果复查','有来源的方法候选审查'],
          'sources':['https://developers.google.com/webmaster-tools/v1/searchanalytics/query','https://developers.google.com/search/docs/monitor-debug/debugging-search-traffic-drops','https://developers.google.com/search/docs/appearance/ai-features'],
          'license':'本包自行实现，不包含第三方爬虫或候选源码；依赖许可另见安装包清单。'}

def baseline():
    return {'method_version':BASELINE['version'],'fingerprint':digest(BASELINE),'capabilities':BASELINE['capabilities'],'sources':BASELINE['sources'],'license':BASELINE['license'],'source_details':[],
            'last_integrated_date':'随本包版本；无第三方候选已自动融合','research_date':'尚未研究','last_attempt_date':'未记录','status':'not_configured',
            'next_review_target':'首次统一巡检','last_summary':'方法基线已随包提供；实际研究及原生任务尚未验收。','pending_candidates':[],'history':[]}

class Methods:
    def __init__(self,root,db_id):self.flow=Tickets(root,db_id);self.root=self.flow.root
    def due(self):
        value=self.flow.tx(lambda db:optional(db,'seo_method','current'))
        return not value or not value.get('next_review_at') or stamp(value['next_review_at'])<=self.flow.now()
    def record(self,receipt):
        shape(receipt,{'id','cycle_id','database_id','observed_at','status','summary','sources','candidates'})
        forbid_secrets(receipt);identifier(receipt['id']);text(receipt['summary'],3000)
        if len(encoded(receipt))>65536 or receipt['database_id']!=self.flow.database_id:raise ValueError('研究回执过大/错库')
        observed=stamp(receipt['observed_at'])
        if abs((self.flow.now()-observed).total_seconds())>86400:raise ValueError('研究时间陈旧或在未来')
        if observed>self.flow.now()+timedelta(minutes=5):raise ValueError('研究时间在未来')
        if receipt['status'] not in {'no_change','candidate_ready','partial','failed'}:raise ValueError('候选不能直接声明已融合')
        if not isinstance(receipt['sources'],list) or len(receipt['sources'])>12 or not isinstance(receipt['candidates'],list) or len(receipt['candidates'])>8:raise ValueError('研究条目超限')
        types=set()
        for source in receipt['sources']:
            shape(source,{'url','kind','revision','license','fetched_at','summary','evidence'})
            u=urlsplit(source['url'])
            if u.scheme!='https' or u.username or u.password or u.query or u.fragment:raise ValueError('来源只接受无敏感参数的HTTPS链接')
            if source['kind']=='official' and u.hostname not in {'developers.google.com','support.google.com','learn.chatgpt.com','developers.openai.com','code.claude.com'}:raise ValueError('官方来源域不符')
            if source['kind']=='opensource' and u.hostname!='github.com':raise ValueError('开源候选需要实际上游仓库来源')
            if source['kind'] not in {'official','opensource'}:raise ValueError('来源类型无效')
            for k in ['revision','license','summary']:text(source[k],2000)
            fetched=stamp(source['fetched_at'])
            if fetched>observed+timedelta(minutes=5) or observed-fetched>timedelta(days=7):raise ValueError('来源未在本周期实际复核')
            self.flow.evidence(source['evidence'],required=True);types.add(source['kind'])
        for c in receipt['candidates']:
            shape(c,{'id','source_url','revision','license','permission_diff','validation','summary'})
            identifier(c['id'])
            if not any(s['kind']=='opensource' and s['url']==c['source_url'] and s['revision']==c['revision'] and s['license']==c['license'] for s in receipt['sources']):raise ValueError('候选版本/许可与来源不一致')
            for k in ['permission_diff','summary']:text(c[k],2000)
            shape(c['validation'],{'status','environment','evidence'})
            if c['validation']['status'] not in {'not_run','passed','failed'}:raise ValueError('隔离验证状态无效')
            text(c['validation']['environment'],200)
            self.flow.evidence(c['validation']['evidence'],required=c['validation']['status']!='not_run')
        complete=receipt['status'] in {'no_change','candidate_ready'}
        if complete and types!={'official','opensource'}:raise ValueError('完整研究需要官方与开源来源的实际证据')
        if receipt['status']=='candidate_ready' and not receipt['candidates']:raise ValueError('候选待审需要候选记录')
        key=receipt['id'];fingerprint=digest(receipt)
        def run(db):
            old=optional(db,'seo_research',key)
            if old:
                if old['digest']!=fingerprint:raise ValueError('研究ID内容冲突')
                return old
            cycle=load(db,'seo_cycle',identifier(receipt['cycle_id']))
            if cycle['status']!='running':raise ValueError('研究必须随本轮巡检写回')
            if cycle.get('research_id'):raise ValueError('同一周期不能用另一研究覆盖')
            value=optional(db,'seo_method','current',baseline())
            if value.get('last_attempt_at') and observed<stamp(value['last_attempt_at']):raise ValueError('旧研究不覆盖新研究')
            history={'id':key,'date':receipt['observed_at'],'status':receipt['status'],'summary':receipt['summary'],'report':'seo_research/'+key+'.json'}
            value['history'].append(history);value.update(status=receipt['status'],last_attempt_date=receipt['observed_at'],last_attempt_at=receipt['observed_at'],
                last_summary=receipt['summary'],next_review_at=(observed+timedelta(days=7 if complete else 1)).isoformat())
            value['next_review_target']=value['next_review_at']
            if complete:
                pending={x['id']:x for x in value.get('pending_candidates',[])}
                for c in receipt['candidates']:
                    old_candidate=pending.get(c['id'])
                    if old_candidate and any(old_candidate[k]!=c[k] for k in ['source_url','revision','license']):raise ValueError('候选ID身份冲突，不能悄悄替换原版本')
                    pending[c['id']]=c
                value.update(research_date=receipt['observed_at'],sources=[s['url'] for s in receipt['sources']],source_details=[{k:s[k] for k in ['url','kind','revision','license','fetched_at','summary']} for s in receipt['sources']],pending_candidates=list(pending.values()))
            self.flow.immutable(Path('seo_research')/(key+'.json'),receipt)
            record={'id':key,'digest':fingerprint,'receipt':receipt};save(db,'seo_research',key,record);save(db,'seo_method','current',value)
            cycle['research_id']=key;cycle['research_status']=receipt['status'];save(db,'seo_cycle',cycle['id'],cycle);return record
        return self.flow.tx(run)
