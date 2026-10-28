"""Bounded read plans and native-MCP result normalization. No Google connection."""
from datetime import date,datetime,timedelta,timezone
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from .onboarding import finite,ga4_result,gsc_covers,stamp,clean_text,forbid_secrets
from .tickets import digest

ERRORS={'missing_tool','not_connected','permission_denied','error','cancelled'}
SUMMARY=['totalUsers','screenPageViews','sessions','newUsers']
GROUPS={'summary':([],SUMMARY),'daily':(['date'],['totalUsers','screenPageViews']),
        'sources':(['sessionDefaultChannelGroup','sessionSourceMedium'],['totalUsers','sessions','engagedSessions']),
        'pages':(['pagePath'],['totalUsers','screenPageViews','activeUsers','userEngagementDuration']),
        'events':(['eventName'],['totalUsers','eventCount'])}

def request_plan(site,start,end,gsc=None,ga4=None,ga_timezone=None,urls=()):
    start=date.fromisoformat(start);end=date.fromisoformat(end)
    if not 0<=(end-start).days<480:raise ValueError('一次巡检历史窗口限1至480天；所有时间指本次提供的已采集范围')
    if end>=datetime.now(ZoneInfo('America/Los_Angeles')).date():raise ValueError('GSC结束日须早于太平洋时区今天')
    if gsc and not gsc_covers(gsc,site):raise ValueError('GSC属性不覆盖本站')
    if ga4:
        if not re.fullmatch(r'properties/\d+',ga4):raise ValueError('GA4资源格式无效')
        if not ga_timezone:raise ValueError('先由所选GA4属性读取实际时区')
        if end>=datetime.now(ZoneInfo(ga_timezone)).date():raise ValueError('GA4结束日须早于属性时区今天')
    requests={};ranges={}
    def add(op,args):
        key=digest({'operation':op,'arguments':args})[:20];requests[key]={'operation':op,'arguments':args};return key
    if gsc:
        add('gsc.list_sites',{})
        filters=[] if gsc==site else [{'groupType':'and','filters':[{'dimension':'page','operator':'includingRegex','expression':'^'+re.escape(site)}]}]
        def query(a,b,dims):return add('gsc.query',{'siteUrl':gsc,'startDate':a.isoformat(),'endDate':b.isoformat(),'dimensions':dims,'type':'web','dataState':'final','rowLimit':1000,'startRow':0,'dimensionFilterGroups':filters})
    for name,days in [('week',7),('month',30),('all',(end-start).days+1)]:
        first=max(start,end-timedelta(days=days-1));length=(end-first).days+1
        current={'start':first.isoformat(),'end':end.isoformat()};previous={'start':(first-timedelta(days=length)).isoformat(),'end':(first-timedelta(days=1)).isoformat()}
        r={'current':current,'previous':previous,'requested_days':days,'gsc':{},'ga4':{}}
        for period,window in [('current',current),('previous',previous)]:
            a=date.fromisoformat(window['start']);b=date.fromisoformat(window['end'])
            if gsc:r['gsc'][period]={'daily':query(a,b,['date']),'pages':query(a,b,['page'])}
            if ga4:
                parsed=urlsplit(site);host={'filter':{'field_name':'hostName','string_filter':{'match_type':'EXACT','value':parsed.hostname,'case_sensitive':False}}}
                scope=host if parsed.path=='/' else {'and_group':{'expressions':[host,{'filter':{'field_name':'pagePath','string_filter':{'match_type':'BEGINS_WITH','value':parsed.path,'case_sensitive':True}}}]}}
                r['ga4'][period]={group:add('ga4.report',{'property_id':ga4.split('/')[1],'date_ranges':[{'start_date':window['start'],'end_date':window['end']}],'dimensions':['hostName',*dims],'metrics':metrics,'dimension_filter':scope,'limit':1000,'offset':0}) for group,(dims,metrics) in GROUPS.items()}
        ranges[name]=r
    if gsc:
        query(start,end,['query'])
        for url in urls:add('gsc.inspect',{'siteUrl':gsc,'inspectionUrl':url,'languageCode':'en-US'})
        add('gsc.sitemaps',{'siteUrl':gsc})
    if ga4:
        add('ga4.property',{'property_id':ga4.split('/')[1]});add('ga4.streams',{'property_id':ga4.split('/')[1]})
    return {'ranges':ranges,'requests':requests,'gsc_resource':gsc,'ga4_resource':ga4,'ga4_timezone':ga_timezone,'search_timezone':'America/Los_Angeles','history_scope':{'start':start.isoformat(),'end':end.isoformat(),'meaning':'本次提供的历史范围，非网站自建站以来全部数据'}}

def calls_from(plan,receipt,now=None):
    now=now or datetime.now(timezone.utc)
    forbid_secrets(receipt)
    observed=stamp(receipt['observed_at'])
    if observed>now+timedelta(minutes=5) or observed<stamp(plan['created_at'])-timedelta(minutes=5):raise ValueError('回执时间不属于本次读取计划')
    if receipt.get('source')!=('synthetic_mcp' if plan['synthetic'] else 'client_mcp'):raise ValueError('合成与真实回执不能混用')
    for k in ['inspection_id','database_id','project_id','challenge']:
        if receipt.get(k)!=plan[k]:raise ValueError('回执计划/同库/站点绑定不符')
    calls=receipt.get('calls',[])
    if not isinstance(calls,list) or len(calls)>len(plan['requests']):raise ValueError('回执调用列表无效')
    result={}
    for item in calls:
        key=item.get('id')
        if key in result or key not in plan['requests']:raise ValueError('重复或计划外调用')
        if any(item.get(k)!=plan['requests'][key][k] for k in ['operation','arguments']):raise ValueError('调用范围与读取计划不符')
        if not clean_text(item.get('tool',''),160):raise ValueError('缺少实际MCP工具名')
        if item.get('error'):
            if item['error'] not in ERRORS:raise ValueError('不支持的读取错误类别')
        elif not isinstance(item.get('result'),dict):raise ValueError('调用结果须为对象')
        result[key]=item
    return result,observed,(now-observed)>timedelta(hours=24)

def metadata(value):
    out={}
    for key in ['subjectToThresholding','dataLossFromOtherRow']:
        if key in value:
            if type(value[key])!=bool:raise ValueError('元数据布尔字段无效')
            out[key]=value[key]
    if value.get('samplingMetadatas'):out['samplingMetadatas']=[{'sampled':True}]
    return out

def gsc_rows(call,site,dimension):
    if not call:return {'status':'missing_tool','rows':[]}
    if call.get('error'):return {'status':call['error'],'rows':[]}
    response=call['result'];rows=response.get('rows',[]);seen=set();out=[]
    if not isinstance(rows,list) or len(rows)>1000:raise ValueError('GSC行数无效')
    args=call['arguments']
    for raw in rows:
        keys=raw.get('keys')
        if not isinstance(keys,list) or len(keys)!=1 or not isinstance(keys[0],str) or keys[0] in seen:raise ValueError('GSC维度/重复行无效')
        key=keys[0];seen.add(key)
        clean_text(key,2048)
        if dimension=='date':
            date.fromisoformat(key)
            if not args['startDate']<=key<=args['endDate']:raise ValueError('GSC日期越界')
        elif dimension=='page' and not gsc_covers(site,key):raise ValueError('GSC结果含其他站点/路径')
        clicks=finite(raw['clicks']);impressions=finite(raw['impressions']);position=finite(raw['position'])
        if clicks>impressions:raise ValueError('GSC点击大于展示')
        out.append({dimension:key,'clicks':clicks,'impressions':impressions,'ctr':clicks/impressions if impressions else None,'position':position if impressions else None})
    return {'status':'partial' if len(rows)==1000 else 'ok' if rows else 'no_rows','rows':out,'limited':len(rows)==1000,'scope':'API返回行，明细不能加总当作站点全部流量'}

def ga_rows(call,site,tz,group):
    if not call:return {'status':'missing_tool','rows':[],'metadata':{}}
    if call.get('error'):return {'status':call['error'],'rows':[],'metadata':{}}
    response=ga4_result(call['result']);args=call['arguments'];dims=args['dimensions'];metrics=args['metrics']
    if [x['name'] for x in response.get('dimensionHeaders',[])]!=dims or [x['name'] for x in response.get('metricHeaders',[])]!=metrics:raise ValueError('GA4列与计划不一致')
    meta=response.get('metadata',{})
    if meta.get('timeZone',tz)!=tz:raise ValueError('GA4响应时区与属性不一致')
    if 'rowCount' in response and 'row_count' in response:raise ValueError('GA4行数字段别名冲突')
    rows=response.get('rows',[]);count=response.get('rowCount',response.get('row_count',len(rows)));out=[];seen=set()
    if not isinstance(rows,list) or len(rows)>1000 or type(count)!=int or count<len(rows):raise ValueError('GA4行数无效')
    for raw in rows:
        if len(raw.get('dimensionValues',[]))!=len(dims) or len(raw.get('metricValues',[]))!=len(metrics):raise ValueError('GA4行列数无效')
        values=[x['value'] for x in raw['dimensionValues']]
        if values[0].lower()!=urlsplit(site).hostname:raise ValueError('GA4响应包含其他网站')
        identity=tuple(values)
        if identity in seen:raise ValueError('GA4重复维度行')
        seen.add(identity);row=dict(zip(dims,values));row.pop('hostName')
        row.update({name:finite(float(v['value'])) for name,v in zip(metrics,raw['metricValues'])})
        if group=='daily':
            d=datetime.strptime(row['date'],'%Y%m%d').date().isoformat();period=args['date_ranges'][0]
            if not period['start_date']<=d<=period['end_date']:raise ValueError('GA4日期越界')
            row['date']=d
        if group=='pages':
            path=row['pagePath']
            if not path.startswith(urlsplit(site).path) or '?' in path or '#' in path:raise ValueError('GA4页面范围不符或含查询信息')
        for k in dims[1:]:clean_text(row[k],2048 if k=='pagePath' else 300)
        out.append(row)
    if group=='summary' and len(out)>1:raise ValueError('GA4去重汇总不能加总多行')
    flags=metadata(meta);partial=count>len(rows) or any(flags.values())
    return {'status':'partial' if partial else 'ok' if rows else 'no_rows','rows':out,'metadata':{**flags,'truncated':count>len(rows)},'row_count':count}

def normalize(plan,calls,stale=False):
    def op(name):return next((c for k,c in calls.items() if plan['requests'][k]['operation']==name),None)
    site=plan['site'];gsc=op('gsc.list_sites');prop=op('ga4.property');streams=op('ga4.streams')
    gsc_status='not_connected' if not plan['gsc_resource'] else 'missing_tool'
    if gsc:
        gsc_status=gsc.get('error') or ('ok' if any(x.get('siteUrl')==plan['gsc_resource'] and x.get('permissionLevel') in {'siteOwner','siteFullUser','siteRestrictedUser'} for x in gsc.get('result',{}).get('siteEntry',[])) else 'permission_denied')
    ga_status='not_connected' if not plan['ga4_resource'] else 'missing_tool';tz=plan['ga4_timezone']
    if prop:
        p=ga4_result(prop.get('result',{}));ga_status=prop.get('error') or ('ok' if p.get('name')==plan['ga4_resource'] and p.get('timeZone')==tz else 'site_mismatch')
    if ga_status=='ok':
        stream=ga4_result((streams or {}).get('result',{}));binding=any(x.get('name','').startswith(plan['ga4_resource']+'/dataStreams/') and gsc_covers(x.get('webStreamData',{}).get('defaultUri',''),site) for x in stream.get('dataStreams',[]))
        # A hostname response can establish binding; empty reports require stream evidence.
        has_host=any(c.get('operation')=='ga4.report' and not c.get('error') and ga4_result(c.get('result',{})).get('rows') for c in calls.values())
        if not binding and not has_host:ga_status='binding_unknown'
    searches={};analytics={}
    for label,r in plan['ranges'].items():
        search={'current':{},'previous':{}};ga={}
        for period in ['current','previous']:
            window=r[period]
            d=gsc_rows(calls.get(r['gsc'].get(period,{}).get('daily')),site,'date') if gsc_status=='ok' else {'status':gsc_status,'rows':[]}
            pages=gsc_rows(calls.get(r['gsc'].get(period,{}).get('pages')),site,'page') if gsc_status=='ok' else {'status':gsc_status,'rows':[]}
            rows=d['rows'];clicks=sum(x['clicks'] for x in rows);impressions=sum(x['impressions'] for x in rows)
            metrics={'clicks':clicks if rows else None,'impressions':impressions if rows else None,'ctr':clicks/impressions if impressions else None,'position':sum(x['position']*x['impressions'] for x in rows if x['position'] is not None)/impressions if impressions else None}
            days=(date.fromisoformat(window['end'])-date.fromisoformat(window['start'])).days+1
            search[period]={**window,'metrics':metrics,'daily':sorted(rows,key=lambda x:x['date']),'pages':pages,'status':'stale' if stale else d['status'],'observed_days':len(rows),'days':days,'complete':d['status']=='ok' and len(rows)==days and days>=r['requested_days'] and not stale}
            ga[period]={group:ga_rows(calls.get(r['ga4'].get(period,{}).get(group)),site,tz,group) if ga_status=='ok' else {'status':ga_status,'rows':[],'metadata':{}} for group in GROUPS}
            for group in ['source_events','page_events']:ga[period][group]={'status':'not_collected','rows':[],'metadata':{}}
        searches[label]=search
        actual_days=(date.fromisoformat(r['current']['end'])-date.fromisoformat(r['current']['start'])).days+1
        analytics[label]={'current':r['current'],'previous':r['previous'],'actual_days':actual_days,'requested_days':r['requested_days'],'complete':actual_days>=r['requested_days'] and all(g['status'] in {'ok','no_rows'} for side in ga.values() for g in side.values() if g['status']!='not_collected') and not stale,'data':ga}
    inspections=[]
    for k,c in calls.items():
        if plan['requests'][k]['operation']=='gsc.inspect':
            result=c.get('result',{}).get('inspectionResult',{}).get('indexStatusResult',{})
            record={key:clean_text(result[key],2048) for key in ['verdict','coverageState','robotsTxtState','indexingState','pageFetchState','lastCrawlTime','googleCanonical','userCanonical'] if key in result}
            if record.get('lastCrawlTime'):stamp(record['lastCrawlTime'])
            inspections.append({'url':c['arguments']['inspectionUrl'],'status':c.get('error') or 'ok' if result else c.get('error') or 'missing_result','record':record,'scope':'Google保存的索引版本，非实时抓取'})
    if gsc_status=='ok':gsc_status=searches['all']['current']['status']
    summaries=[r['data']['current']['summary'] for r in analytics.values()]
    if ga_status=='ok':
        if any(g['rows'] and g['status'] in {'ok','partial'} for g in summaries):
            ga_status='partial' if any(g['status'] not in {'ok','no_rows','not_collected'} for r in analytics.values() for side in r['data'].values() for g in side.values()) else 'ok'
        else:
            states={g['status'] for g in summaries};ga_status=next((x for x in ['permission_denied','error','cancelled','missing_tool','no_rows'] if x in states),'missing_tool')
    query=next((c for c in calls.values() if c['operation']=='gsc.query' and c['arguments']['dimensions']==['query']),None)
    queries=gsc_rows(query,site,'query') if gsc_status in {'ok','partial','no_rows'} else {'status':gsc_status,'rows':[]}
    maps=op('gsc.sitemaps');google_map={'status':(maps or {}).get('error') or ('ok' if maps else 'missing_tool'),'items':[]}
    if maps and not maps.get('error'):
        for raw in maps['result'].get('sitemap',[])[:100]:
            path=raw.get('path','')
            if not gsc_covers(site,path):continue
            item={key:raw[key] for key in ['path','isPending','lastDownloaded'] if key in raw}
            if 'isPending' in item and type(item['isPending'])!=bool:raise ValueError('地图isPending类型无效')
            if item.get('lastDownloaded'):stamp(item['lastDownloaded'])
            if 'errors' in raw:item['errors']=finite(float(raw['errors']))
            google_map['items'].append(item)
    return {'searches':searches,'analytics':analytics,'gsc_status':'stale' if stale and plan['gsc_resource'] else gsc_status,'ga4_status':'stale' if stale and plan['ga4_resource'] else ga_status,'index_records':inspections,'queries':queries,'google_sitemaps':google_map,'stale':stale}
