"""Chat-led registration and bounded native-MCP receipts. No Google credentials."""
from contextlib import closing
from datetime import datetime, timezone, timedelta, date
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlsplit
from .store import Store, utc_now, current_connections
from .public_check import site_url, initial_check

STATUS={'not_connected':'尚未连接','missing_tool':'缺少所需工具','permission_denied':'权限不足','site_mismatch':'站点不匹配','binding_unknown':'接口可读，站点绑定待核验','no_rows':'已读取，窗口暂无数据','read_ok':'已读取本站数据','error':'读取失败','stale':'回执已陈旧'}
FORBIDDEN={'access_token','refresh_token','client_secret','private_key','password','authorization','cookie','api_key','credentials'}

def clean_text(value,limit=300):
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError('文本字段无效')
    return value

def forbid_secrets(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key.lower() in FORBIDDEN:raise ValueError('回执不得包含凭据')
            forbid_secrets(item)
    elif isinstance(value,list):
        for item in value:forbid_secrets(item)
    elif isinstance(value,str) and ('Bearer ' in value or '-----BEGIN PRIVATE KEY' in value):
        raise ValueError('回执不得包含令牌')

def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('指标必须为有限非负数')
    return value

def stamp(value):
    if not isinstance(value,str):raise ValueError('回执时间无效')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('回执时间需要时区')
    return parsed.astimezone(timezone.utc)

def gsc_covers(resource,site):
    host=urlsplit(site).hostname
    if resource.startswith('sc-domain:'):
        domain=resource[10:].lower().encode('idna').decode()
        return host==domain or host.endswith('.'+domain)
    target=urlsplit(resource);selected=urlsplit(site)
    return target.scheme==selected.scheme and target.netloc.lower()==selected.netloc.lower() and selected.path.startswith(target.path or '/')

def ga4_result(value):
    """Official MCP 0.8 emits proto snake_case; REST connectors emit camelCase."""
    aliases={'dimension_headers':'dimensionHeaders','metric_headers':'metricHeaders','dimension_values':'dimensionValues','metric_values':'metricValues','time_zone':'timeZone','data_streams':'dataStreams','web_stream_data':'webStreamData','default_uri':'defaultUri','subject_to_thresholding':'subjectToThresholding','data_loss_from_other_row':'dataLossFromOtherRow','sampling_metadatas':'samplingMetadatas'}
    if isinstance(value,list):return [ga4_result(x) for x in value]
    if not isinstance(value,dict):return value
    result={}
    for k,v in value.items():
        key=aliases.get(k,k)
        if key in result:raise ValueError('GA4字段别名冲突')
        result[key]=ga4_result(v)
    return result

def property_number(value):
    value=str(value)
    return value.removeprefix('properties/')

class Onboarding:
    def __init__(self,root):self.store=Store(root);self.root=root
    def transaction(self,fn):
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                result=fn(db);db.commit()
                if isinstance(result,dict) and isinstance(result.get('google'),dict):result['google']=current_connections(result['google'])
                return result
            except BaseException:db.rollback();raise
    @staticmethod
    def load(db,kind,key):
        row=db.execute('SELECT payload FROM records WHERE kind=? AND id=?',(kind,key)).fetchone()
        if not row:raise ValueError('接入记录不存在')
        return json.loads(row[0])
    @staticmethod
    def save(db,kind,key,value):
        db.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload',(kind,key,json.dumps(value,ensure_ascii=False,allow_nan=False)))
    def begin(self,site,name='',goal='',client='codex',synthetic=False):
        site=site_url(site);key=hashlib.sha256(site.encode()).hexdigest()[:20]
        if client not in {'codex','claude'}:raise ValueError('选择Codex或Claude Code本机客户端')
        for value in [name,goal]:clean_text(value)
        def run(db):
            found=db.execute("SELECT payload FROM records WHERE kind='onboarding' AND id=?",(key,)).fetchone()
            if found:
                record=json.loads(found[0])
                if record['synthetic']!=bool(synthetic):raise ValueError('禁止混用合成与真实接入记录')
                return record
            record={'id':key,'site':site,'name':name or urlsplit(site).hostname,'goal':goal,'client':client,'synthetic':bool(synthetic),'phase':'awaiting_google','challenge':secrets.token_hex(16),'created_at':utc_now(),'updated_at':utc_now(),'allowed_dirs':[],'timezone':'未选择','google':{k:{'status':'not_connected','label':STATUS['not_connected']} for k in ['gsc','ga4']},'initial_check':None,'revision':1}
            project={'id':key,'slug':key,'site':site,'name':record['name']+('（合成验收）' if synthetic else ''),'goal':goal,'quality':'missing','ranges':{},'daily':[],'pages':[],'suggestions':[],'runs':[],'events':[],'analytics':{'status':'not_connected'},'source':'synthetic' if synthetic else 'user_registration','connections':record['google'],'seo_enabled':False,'seo_review_enabled':False}
            self.save(db,'onboarding',key,record);self.save(db,'seo_project',key,project)
            return record
        return self.transaction(run)
    def get(self,key):
        record=self.transaction(lambda db:self.load(db,'onboarding',key));record['google']=current_connections(record['google']);return record
    def configure(self,key,goal=None,name=None,timezone_name=None,allowed_dirs=None):
        def run(db):
            record=self.load(db,'onboarding',key)
            if record['phase']=='cancelled':raise ValueError('接入已取消，先resume')
            for field,value in [('goal',goal),('name',name)]:
                if value is not None:record[field]=clean_text(value)
            if timezone_name is not None:
                from zoneinfo import ZoneInfo
                ZoneInfo(timezone_name);record['timezone']=timezone_name
            if allowed_dirs is not None:
                if len(allowed_dirs)>10:raise ValueError('允许目录最多10个')
                from .skill_scan import linked
                if any(any(linked(p) for p in [Path(x).expanduser().absolute(),*Path(x).expanduser().absolute().parents]) or not Path(x).expanduser().is_dir() for x in allowed_dirs):raise ValueError('允许目录必须已存在且不经链接/junction')
                record['allowed_dirs']=[str(Path(x).expanduser().resolve()) for x in allowed_dirs]
            record['revision']+=1;record['updated_at']=utc_now()
            p=self.load(db,'seo_project',key);p['goal']=record['goal'];p['name']=record['name']+('（合成验收）' if record['synthetic'] else '')
            self.save(db,'onboarding',key,record);self.save(db,'seo_project',key,p);return record
        return self.transaction(run)
    def phase(self,key,cancel=False):
        def run(db):
            r=self.load(db,'onboarding',key);r['phase']='cancelled' if cancel else 'awaiting_google';r['updated_at']=utc_now();self.save(db,'onboarding',key,r);return r
        return self.transaction(run)
    def google(self,key,receipt):
        if not isinstance(receipt,dict):raise ValueError('MCP回执必须是对象')
        forbid_secrets(receipt)
        if len(json.dumps(receipt).encode())>262144:raise ValueError('MCP回执超过256KiB')
        service=receipt.get('service')
        if service not in {'gsc','ga4'}:raise ValueError('回执服务无效')
        clean_text(receipt.get('server',''),120)
        if not receipt.get('server'):raise ValueError('需要实际MCP服务器标识')
        observed=stamp(receipt['observed_at']);now=datetime.now(timezone.utc)
        if observed>now+timedelta(minutes=5):raise ValueError('回执时间在未来')
        digest=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        def run(db):
            r=self.load(db,'onboarding',key)
            if r['phase']=='cancelled':raise ValueError('接入已取消')
            if receipt.get('challenge')!=r['challenge']:raise ValueError('回执不属于本次接入')
            if receipt.get('source')!=('synthetic_mcp' if r['synthetic'] else 'client_mcp'):raise ValueError('合成/真实回执来源不匹配')
            old=r['google'][service]
            if old.get('digest')==digest:return r
            if old.get('observed_at') and observed<stamp(old['observed_at']):raise ValueError('拒绝旧回执覆盖新结果')
            status='stale' if now-observed>timedelta(hours=24) else receipt.get('error')
            if receipt.get('error') and receipt['error'] not in {'not_connected','missing_tool','permission_denied','site_mismatch','binding_unknown','error'}:raise ValueError('错误状态不能代替读取证明')
            p=self.load(db,'seo_project',key)
            calls=receipt.get('calls',[])
            if not isinstance(calls,list) or len(calls)>8:raise ValueError('回执调用数无效')
            allowed={'gsc.list_sites','gsc.query','ga4.property','ga4.report','ga4.streams'}
            for c in calls:
                if not isinstance(c,dict) or c.get('operation') not in allowed or not c['operation'].startswith(service+'.'):raise ValueError('只接受本站所需只读调用')
                clean_text(c.get('tool',''),160)
                if not c.get('tool'):raise ValueError('需要实际MCP工具标识')
            by_op={c['operation']:c for c in calls}
            if len(by_op)!=len(calls):raise ValueError('拒绝重复调用覆盖范围证明')
            result={}
            resource=clean_text(receipt.get('resource',''),2048)
            if not status:
                if service=='gsc':status,result=self._gsc(r,p,resource,by_op)
                else:status,result=self._ga4(r,p,resource,by_op)
            status=status or 'error'
            if service=='gsc':
                if status in {'read_ok','no_rows'}:p['fetched_at']=observed.isoformat()
                elif p.get('ranges'):p['quality']='stale' if status=='stale' else 'error'
            elif p.get('analytics',{}).get('ranges'):
                if status in {'read_ok','no_rows'}:p['analytics']['fetched_at']=observed.isoformat()
                else:p['analytics']['last_attempt']={'at':observed.isoformat(),'status':status};p['analytics']['stale']=status=='stale'
            r['google'][service]={'status':status,'label':STATUS[status],'resource':resource,'server':receipt['server'],'source':receipt['source'],'observed_at':observed.isoformat(),'digest':digest,**result}
            r['updated_at']=utc_now();p['connections']=r['google']
            self.save(db,'onboarding',key,r);self.save(db,'seo_project',key,p);return r
        result=self.transaction(run);result['google']=current_connections(result['google']);return result
    @staticmethod
    def _gsc(r,p,resource,calls):
        if not {'gsc.list_sites','gsc.query'}<=calls.keys():return 'missing_tool',{}
        if not gsc_covers(resource,r['site']):return 'site_mismatch',{}
        sites=calls['gsc.list_sites']['result'].get('siteEntry',[])
        if not any(x.get('siteUrl')==resource and x.get('permissionLevel') in {'siteOwner','siteFullUser','siteRestrictedUser'} for x in sites):return 'permission_denied',{}
        call=calls['gsc.query'];args=call['arguments']
        if args.get('siteUrl')!=resource or args.get('dimensions')!=['date']:raise ValueError('搜索查询资源/日期维度不匹配')
        if set(args)-{'siteUrl','startDate','endDate','dimensions','dimensionFilterGroups','rowLimit','type','dataState','startRow'}:raise ValueError('搜索查询含不支持的范围参数')
        if args.get('type','web')!='web' or args.get('dataState','final')!='final' or args.get('startRow',0)!=0:raise ValueError('初检只接受第一页最终web搜索数据')
        if args.get('rowLimit',1000)>1000:raise ValueError('搜索行上限过大')
        expected=[{'groupType':'and','filters':[{'dimension':'page','operator':'includingRegex','expression':'^'+re.escape(r['site'])}]}]
        filters=args.get('dimensionFilterGroups')
        if resource!=r['site'] and filters!=expected:raise ValueError('较宽GSC属性必须以锚定page正则限定所选网站/路径')
        if resource==r['site'] and filters not in (None,[],expected):raise ValueError('拒绝额外GSC数据子集过滤')
        start=date.fromisoformat(args['startDate']);end=date.fromisoformat(args['endDate'])
        if not 0<=(end-start).days<=90 or end>=datetime.now(timezone.utc).date():raise ValueError('搜索查询窗口无效')
        rows=call['result'].get('rows',[])
        if not isinstance(rows,list) or len(rows)>1000:raise ValueError('搜索结果行数无效')
        daily=[];seen=set()
        for x in rows:
            if not isinstance(x.get('keys'),list) or len(x['keys'])!=1:raise ValueError('搜索结果日期维度无效')
            day=date.fromisoformat(x['keys'][0])
            if not start<=day<=end or day in seen:raise ValueError('搜索日期越界或重复')
            seen.add(day);daily.append({'date':day.isoformat(),'clicks':finite(x['clicks']),'impressions':finite(x['impressions']),'position':finite(x['position'])})
        clicks=sum(x['clicks'] for x in daily);impressions=sum(x['impressions'] for x in daily)
        metrics={'clicks':clicks,'impressions':impressions,'ctr':clicks/impressions if impressions else None,'position':sum(x['position']*x['impressions'] for x in daily)/impressions if impressions else None}
        p.update(quality='partial' if daily else 'no_rows',fetched_at=r['google']['gsc'].get('observed_at') or utc_now(),daily=sorted(daily,key=lambda x:x['date']),pages=[],ranges={'all':{'start':start.isoformat(),'end':end.isoformat(),'clicks':clicks if daily else None,'impressions':impressions if daily else None,'ctr':metrics['ctr']*100 if metrics['ctr'] is not None else None,'observed_days':len(daily),'days':(end-start).days+1,'complete':False}},periods={'current':{'start':start.isoformat(),'end':end.isoformat(),'metrics':metrics if daily else {k:None for k in metrics}},'previous':{'start':None,'end':None,'metrics':{k:None for k in metrics}}})
        for label,days in [('week',7),('month',30)]:
            first=max(start,end-timedelta(days=days-1));selected=[x for x in daily if x['date']>=first.isoformat()]
            c=sum(x['clicks'] for x in selected);im=sum(x['impressions'] for x in selected)
            p['ranges'][label]={'start':first.isoformat(),'end':end.isoformat(),'clicks':c if selected else None,'impressions':im if selected else None,'ctr':c/im*100 if im else None,'observed_days':len(selected),'days':(end-first).days+1,'complete':False}
        return ('read_ok' if daily else 'no_rows'),{'rows':len(daily),'start':start.isoformat(),'end':end.isoformat()}
    @staticmethod
    def _ga4(r,p,resource,calls):
        calls={op:{**c,'result':ga4_result(c['result'])} for op,c in calls.items()}
        if not re.fullmatch(r'properties/\d+',resource):raise ValueError('GA4资源格式无效')
        if not {'ga4.property','ga4.report'}<=calls.keys():return 'missing_tool',{}
        prop=calls['ga4.property']['result']
        if prop.get('name')!=resource or property_number(calls['ga4.property']['arguments'].get('property_id'))!=resource.split('/')[1]:return 'site_mismatch',{}
        call=calls['ga4.report'];args=call['arguments']
        if property_number(args.get('property_id'))!=resource.split('/')[1]:raise ValueError('GA4查询资源不匹配')
        planned=['totalUsers','screenPageViews','sessions','newUsers']
        if set(args)!={'property_id','date_ranges','dimensions','metrics','dimension_filter'} or args['dimensions']!=['hostName'] or args['metrics']!=planned or not isinstance(args['date_ranges'],list) or len(args['date_ranges'])!=1:raise ValueError('GA4只接受单窗口、hostname及四个标准指标')
        parsed=urlsplit(r['site']);host=parsed.hostname
        host_filter={'filter':{'field_name':'hostName','string_filter':{'match_type':'EXACT','value':host,'case_sensitive':False}}}
        expected=host_filter if parsed.path=='/' else {'and_group':{'expressions':[host_filter,{'filter':{'field_name':'pagePath','string_filter':{'match_type':'BEGINS_WITH','value':parsed.path,'case_sensitive':True}}}]}}
        if args['dimension_filter']!=expected:raise ValueError('GA4过滤必须精确限定本站，不能包含其他来源/页面子集')
        response=call['result'];headers=[x['name'] for x in response.get('dimensionHeaders',[])]
        metrics=[x['name'] for x in response.get('metricHeaders',[])]
        if headers!=['hostName'] or metrics!=planned:raise ValueError('GA4需要hostname绑定及四个标准汇总指标')
        rows=response.get('rows',[])
        host=urlsplit(r['site']).hostname
        if len(rows)>1000:raise ValueError('GA4行数过大')
        matched=[x for x in rows if x.get('dimensionValues',[{}])[0].get('value')==host]
        if matched and len(matched)!=len(rows):raise ValueError('GA4响应包含其他站点')
        if rows and not matched:return 'site_mismatch',{}
        streams=calls.get('ga4.streams')
        if streams and property_number(streams['arguments'].get('property_id'))!=resource.split('/')[1]:raise ValueError('GA4流配置来自其他属性')
        binding=any(x.get('name','').startswith(resource+'/dataStreams/') and gsc_covers(x.get('webStreamData',{}).get('defaultUri',''),r['site']) for x in (streams or {}).get('result',{}).get('dataStreams',[]))
        if not matched and not binding:return 'binding_unknown',{}
        if len(matched)>1:raise ValueError('GA4每站汇总必须唯一，不加总去重用户')
        period=args['date_ranges'][0];start=date.fromisoformat(period['start_date']);end=date.fromisoformat(period['end_date'])
        if not 0<=(end-start).days<=90 or end>=datetime.now(timezone.utc).date():raise ValueError('GA4窗口无效')
        summary=[]
        if matched:
            row={k:finite(float(matched[0]['metricValues'][i]['value'])) for i,k in enumerate(metrics)};summary=[row]
        raw_meta=response.get('metadata',{});metadata={}
        for field in ['subjectToThresholding','dataLossFromOtherRow']:
            if field in raw_meta:
                if not isinstance(raw_meta[field],bool):raise ValueError('GA4元数据标记应为布尔值')
                metadata[field]=raw_meta[field]
        if raw_meta.get('samplingMetadatas'):
            metadata['samplingMetadatas']=[{'sampled':True}]
        if prop.get('timeZone'):
            from zoneinfo import ZoneInfo
            ZoneInfo(prop['timeZone'])
        p['analytics']={'status':'ok','fetched_at':utc_now(),'timezone':prop.get('timeZone','未提供'),'stale':False,'ranges':{'all':{'current':{'start':start.isoformat(),'end':end.isoformat()},'previous':None,'complete':False,'data':{'current':{k:{'status':'ok' if k=='summary' else 'not_collected','rows':summary if k=='summary' else [],'metadata':metadata if k=='summary' else {}} for k in ['summary','daily','sources','pages','events','source_events','page_events']},'previous':None}}}}
        if (end-start).days<30:p['analytics']['ranges']['month']=p['analytics']['ranges']['all']
        if (end-start).days<7:p['analytics']['ranges']['week']=p['analytics']['ranges']['all']
        return ('read_ok' if matched else 'no_rows'),{'rows':len(matched),'start':start.isoformat(),'end':end.isoformat()}
    def scan(self,key):
        from .skill_scan import scan_metadata
        r=self.get(key)
        if r['phase']=='cancelled':raise ValueError('接入已取消')
        items=scan_metadata(r['allowed_dirs'])
        def run(db):
            latest=self.load(db,'onboarding',key)
            if latest['phase']=='cancelled' or latest['allowed_dirs']!=r['allowed_dirs']:raise ValueError('扫描范围已变更或取消')
            for item in items:self.save(db,'skill',item['id'],item)
            return {'scanned':len(items),'scope':'仅所选目录直接Skill子目录的frontmatter；启用/执行能力未推断'}
        return self.transaction(run)
    def check(self,key,transport=None):
        r=self.get(key)
        if r['phase']=='cancelled':raise ValueError('接入已取消')
        if r['synthetic'] and transport is None:raise ValueError('合成记录只允许隔离测试传输，不发公开网络请求')
        report=initial_check(r['site'],transport=transport)
        if (report['source']=='synthetic_http')!=r['synthetic']:raise ValueError('合成公开检查与接入模式不匹配')
        def run(db):
            latest=self.load(db,'onboarding',key);latest['initial_check']={**report,'checked_at':utc_now()};latest['updated_at']=utc_now()
            if latest['phase']=='cancelled':raise ValueError('接入已取消，不写入检查结果')
            latest['google']=current_connections(latest['google'])
            latest['phase']='checked' if all(x['status'] in {'read_ok','no_rows'} for x in latest['google'].values()) else 'checked_with_gaps'
            p=self.load(db,'seo_project',key);p['runs']=[x for x in p['runs'] if x.get('id')!='initial-check']+[{'id':'initial-check','kind':'diagnosis','status':'succeeded' if report['results'][0]['status']=='ok' else 'failed','title':'首次接入公开检查'+('（合成）' if r['synthetic'] else ''),'summary':report['scope'],'limitations':'Google与公开读取分开；未改变网站或配置巡检。','updated_at':latest['updated_at'],'verification':'仅记录有限只读证据','deployment':'not_performed','effect':'not_observed'}]
            self.save(db,'onboarding',key,latest);self.save(db,'seo_project',key,p);return latest
        return self.transaction(run)
