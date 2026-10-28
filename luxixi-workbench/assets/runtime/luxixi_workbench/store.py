"""Fresh, application-owned SQLite only; no importer or business mutations."""
from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
import sqlite3
import time

SQLITE_APP_ID = 1280857938

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def event_time(row):
    try:
        value=row.get('at');return float(value) if isinstance(value,(int,float)) else datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):return float('-inf')

def current_connections(connections):
    for item in connections.values():
        if item.get('status') not in {'read_ok','no_rows','partial'}:continue
        try:
            observed=datetime.fromisoformat(item['observed_at'].replace('Z','+00:00'))
            if observed.tzinfo is None:raise ValueError('missing timezone')
            expired=datetime.now(timezone.utc)-observed>timedelta(hours=24)
        except (KeyError,ValueError,TypeError):expired=True
        if expired:
            item.update(last_status=item['status'],status='stale',label='回执已陈旧',stale=True)
    return connections

class Store:
    def __init__(self, root):
        self.path = root / 'workbench.sqlite3'
        with closing(sqlite3.connect(self.path)) as db:
            app_id = db.execute('PRAGMA application_id').fetchone()[0]
            schema_version = db.execute('PRAGMA user_version').fetchone()[0]
            objects = {(r[0],r[1]) for r in db.execute("SELECT type,name FROM sqlite_master WHERE sql IS NOT NULL")}
            if app_id not in (0, SQLITE_APP_ID) or (app_id == 0 and (objects or schema_version != 0)):
                raise ValueError('拒绝接入其他应用数据库')
            if app_id == SQLITE_APP_ID and schema_version != 1:
                raise ValueError('数据库版本不支持，不自动降级或改写')
            if app_id == SQLITE_APP_ID:
                expected = {'metadata':[('key','TEXT',0,1),('value','TEXT',1,0)],
                            'records':[('kind','TEXT',1,1),('id','TEXT',1,2),('payload','TEXT',1,0)]}
                if objects != {('table','metadata'),('table','records')}:
                    raise ValueError('数据库结构不匹配，不自动改写')
                for table, columns in expected.items():
                    actual=[(r[1],r[2],r[3],r[5]) for r in db.execute(f'PRAGMA table_info({table})')]
                    if actual != columns:
                        raise ValueError('数据库字段不匹配，不自动改写')
                if not db.execute("SELECT value FROM metadata WHERE key='created_at'").fetchone():
                    raise ValueError('数据库初始化记录缺失')
                return
            db.execute('BEGIN IMMEDIATE')
            db.execute(f'PRAGMA application_id={SQLITE_APP_ID}')
            db.execute('PRAGMA user_version=1')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('created_at', ?)", (utc_now(),))
            db.commit()

    def records(self):
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('PRAGMA application_id').fetchone()[0] != SQLITE_APP_ID or db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise ValueError('数据库身份/版本不匹配')
            rows = db.execute('SELECT kind, payload FROM records ORDER BY kind,id').fetchall()
        grouped = {}
        for kind, payload in rows:
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError('记录格式无效')
            grouped.setdefault(kind, []).append(value)
        return grouped

    def snapshot(self, section):
        grouped = self.records()
        from .tickets import project_records
        tickets=project_records(grouped,self.path.parent)
        from .cycle import projection
        schedule,research,cycle_auto=projection(grouped)
        if section=='tickets':return {'items':tickets,'write_transport':'local_cli_only'}
        for row in grouped.get('onboarding',[]):row['google']=current_connections(row['google'])
        for row in grouped.get('seo_project',[]):
            row['connections']=current_connections(row.get('connections',{}))
            if row['connections'].get('gsc',{}).get('status')=='stale' and row.get('ranges'):row['quality']='stale'
            if row['connections'].get('ga4',{}).get('status')=='stale' and row.get('analytics',{}).get('ranges'):row['analytics']['stale']=True
            def expired(value):
                try:return datetime.now(timezone.utc)-datetime.fromisoformat(value.replace('Z','+00:00'))>timedelta(hours=24)
                except (AttributeError,ValueError,TypeError):return True
            for cached in row.get('ranges',{}).values():cached['stale']=expired(cached.get('fetched_at',row.get('fetched_at')))
            for detail in row.get('search_ranges',{}).values():
                for side in detail.values():
                    side['stale']=expired(side.get('fetched_at',row.get('fetched_at')))
                    pages=side.get('pages',{})
                    if pages.get('rows'):pages['stale']=expired(pages.get('fetched_at',side.get('fetched_at',row.get('fetched_at'))))
            for cached in row.get('analytics',{}).get('ranges',{}).values():
                cached['stale']=expired(cached.get('fetched_at',row.get('analytics',{}).get('fetched_at')))
                for groups in cached.get('data',{}).values():
                    if not isinstance(groups,dict):continue
                    for group in groups.values():
                        if isinstance(group,dict) and group.get('rows'):group['stale']=expired(group.get('fetched_at',cached.get('fetched_at',row.get('analytics',{}).get('fetched_at'))))
        if section == 'onboarding':
            rows=grouped.get('onboarding',[])
            return {'items':[{k:r.get(k) for k in ['id','site','name','client','synthetic','phase','timezone','google','initial_check','updated_at']} for r in rows],
                    'skill':'luxixi-workbench','version':'0.6.1','installation':'project-scope','schedule':schedule['status']}
        if section == 'automation':
            return {'at': time.time(), 'fresh': True, 'observation_complete': False,
                    'host': '本机工作区', 'synthetic_records':any(t.get('synthetic') for t in tickets) or any(p.get('source')=='synthetic' for p in grouped.get('seo_project',[])), 'items': grouped.get('automation', [])+cycle_auto,
                    'tickets': grouped.get('automation_ticket', []), 'events': sorted(grouped.get('automation_event', []),key=event_time,reverse=True),
                    'coverage': {'scope': '仅本库统一SEO任务的客户端原生读回与业务记录；不扫描其他任务', 'codex':len(cycle_auto), 'codex_verified': False}}
        if section == 'skills':
            return {'at': time.time(), 'status': 'ok', 'items': grouped.get('skill', []),
                    'categories': [{'id': i, 'name': n} for i,n in [('docs','工作与文档'),('media','创作与影音'),('seo','SEO与增长'),('dev','开发与部署'),('tools','工具与自动化')]]}
        return {'read_at': utc_now(), 'projects': grouped.get('seo_project', []), 'synthetic_records':any(p.get('source')=='synthetic' for p in grouped.get('seo_project',[])),
                'skill_hash':research['fingerprint'],'schedule':schedule,'research':research}
