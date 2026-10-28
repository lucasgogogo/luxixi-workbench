"""Same-database ticket protocol. No executor, model, scheduler or external writes."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
from urllib.parse import urlsplit
from .store import Store
from .skill_scan import linked
from .onboarding import forbid_secrets,stamp

LABELS={'pending':'待处理','in_progress':'执行中','completed':'执行完毕','incomplete':'未完成 / 需核对','needs_reconciliation':'需核对'}
IDENT=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')

def text(value,limit=1000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('文本字段无效')
    return value

def identifier(value):
    if not isinstance(value,str) or not IDENT.fullmatch(value):raise ValueError('标识字段无效')
    return value

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()

def shape(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or not set(required)<=set(value):raise ValueError('协议字段不完整或包含未知字段')

def content(value):
    shape(value,{'title','rationale','scope','validation','mutation_type','external'},{'expected_effect'})
    for field in ['title','rationale','scope','validation']:text(value[field],200 if field=='title' else 4000)
    if 'expected_effect' in value:text(value['expected_effect'],1000)
    if value['mutation_type'] not in {'investigation','technical_fix','content_update','analytics','analytics_setup','domain_verification'}:raise ValueError('修改类型无效')
    shape(value['external'],{'kind','target'})
    if value['external']['kind'] not in {'none','publish'}:raise ValueError('外部动作类型无效')
    if value['external']['kind']=='none':
        if value['external']['target'] is not None:raise ValueError('无外部动作时target应为空')
    else:
        target=text(value['external']['target'],2048);url=urlsplit(target)
        if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password or url.query or url.fragment:raise ValueError('发布目标只接受不含认证/查询/片段的网址')
    forbid_secrets(value);return deepcopy(value)

def version_hash(ticket):return digest({k:ticket[k] for k in ['kind','project_id','issue_key','content']})

def visible(record,now=None):
    r=deepcopy(record);now=now or datetime.now(timezone.utc)
    if version_hash(r)!=r['content_hash']:raise ValueError('工单内容摘要不匹配')
    if r['state']=='in_progress' and r.get('claim') and stamp(r['claim']['lease_until'])<=now:
        r['state']='needs_reconciliation';r['reason']='领取已失联；先核对已有文件和外部结果，不自动重新执行'
    for attempt in r['attempts']:
        attempt.pop('secret_digest',None)
    if r.get('claim'):r['claim'].pop('secret_digest',None)
    r['state_label']=LABELS[r['state']];r['copy_allowed']=r['state'] in {'pending','needs_reconciliation','incomplete'}
    return r

def prompt(record,root):
    r=visible(record);tool={'cwd':str(Path(__file__).resolve().parent.parent),'argv_prefix':[sys.executable,'-B','-X','utf8','-m','luxixi_workbench.ticket_cli','--data-dir',str(root),'--db-id',r['database_id']]}
    mode='只核对已有结果，禁止重复执行/发布。' if r['state']!='pending' else '仅在领取明确返回can_execute=true后开始本修订范围。'
    return ('【同库工单'+(' · 合成测试' if r['synthetic'] else '')+'】\n请按本条执行指令处理当前工单；若用户只要求审阅则不领取。\n'
        +'工单：'+r['number']+'；ID：'+r['id']+'；项目：'+r['project_id']+'；站点：'+r['site']+'\n'
        +'数据库：'+r['database_id']+'；修订：'+str(r['revision'])+'；内容SHA256：'+r['content_hash']+'\n'
        +'目标：'+r['content']['title']+'\n范围：'+r['content']['scope']+'\n依据：'+r['content']['rationale']+'\n验收：'+r['content']['validation']+'\n'
        +'外部动作范围：'+json.dumps(r['content']['external'],ensure_ascii=False)+'\n'
        +'记录工具（参数数组；在给定cwd执行，勿拼接不受控shell）：'+json.dumps(tool,ensure_ascii=False)+'\n'
        +'先show --id '+r['id']+'核对同库/当前修订/既有结果，再claim --id '+r['id']+' --revision '+str(r['revision'])+' --hash '+r['content_hash']+' --actor <当前客户端会话名> --operation-id <本次稳定唯一ID>。\n'
        +mode+'保存claim_file；它是本机领取凭据，不粘贴密钥正文。长执行用heartbeat。\n'
        +'复制不领取，不另建批准状态。外部动作仅限本消息已授权范围；先external-begin落意图，只有proceed=true可执行一次；失败/中断/重复意图先核目标结果，绝不自动重发。\n'
        +'将实际修改、验证/证据文件摘要、外部结果及时间写成回执，再report --claim-file <返回路径> --receipt <JSON文件>。回写失败先recover/核对已落回执，不重复业务动作。未知或失败如实回写，不以退出码或聊天完成关单。\n'
        +'格式与恢复规则见本包Skill的references/tickets.md；缺本机执行能力则说明缺口，不能称已领取或执行。不得超范围发布、改权限、付款或恢复暂停任务。')

class Tickets:
    def __init__(self,root,db_id=None,clock=None):
        self.root=Path(root);self.store=Store(self.root);self.clock=clock or (lambda:datetime.now(timezone.utc))
        def init(db):
            row=db.execute("SELECT value FROM metadata WHERE key='database_id'").fetchone()
            if row:
                if db_id is not None and db_id!=row[0]:raise ValueError('数据库标识不符，拒绝其他库')
                bound=db.execute("SELECT value FROM metadata WHERE key='database_root'").fetchone()
                if not bound or bound[0]!=os.path.normcase(str(self.root.resolve())):raise ValueError('数据库被复制/移到其他根；不自动建立第二个执行库')
                return row[0]
            if db_id is not None:raise ValueError('该库尚无协议身份，不接受其他库的提示')
            value=secrets.token_hex(16);db.execute('INSERT INTO metadata VALUES(?,?)',('database_id',value));db.execute('INSERT INTO metadata VALUES(?,?)',('database_root',os.path.normcase(str(self.root.resolve()))));return value
        self.database_id=self.tx(init)
        if db_id is not None and db_id!=self.database_id:raise ValueError('数据库标识不符，拒绝写入其他库')
    def tx(self,fn):
        with closing(sqlite3.connect(self.store.path,timeout=5,isolation_level=None)) as db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            try:result=fn(db);db.commit();return result
            except BaseException:db.rollback();raise
    def now(self):return self.clock().astimezone(timezone.utc)
    @staticmethod
    def load(db,key):
        row=db.execute("SELECT payload FROM records WHERE kind='ticket' AND id=?",(key,)).fetchone()
        if not row:raise ValueError('工单不存在')
        r=json.loads(row[0])
        if version_hash(r)!=r['content_hash']:raise ValueError('工单内容摘要不匹配')
        return r
    @staticmethod
    def save(db,r):db.execute("INSERT INTO records VALUES('ticket',?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload",(r['id'],encoded(r).decode()))
    def view(self,r):return visible(r,self.now())
    def match(self,r,revision,hash_value):
        if type(revision)!=int or r['revision']!=revision or not hmac.compare_digest(r['content_hash'],hash_value):raise ValueError('工单修订/摘要已变化，拒绝旧提示')
        if r['database_id']!=self.database_id:raise ValueError('工单属于其他数据库')
    def event(self,r,kind,detail):
        r['events'].append({'at':self.now().isoformat(),'kind':kind,'detail':detail});r['updated_at']=self.now().isoformat()
    def safe(self,relative):
        candidate=self.root/relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or not candidate.resolve().is_relative_to(self.root.resolve()):raise ValueError('协议文件越界')
        for part in [candidate,*candidate.parents]:
            if linked(part):raise ValueError('协议文件不能经过链接/junction')
            if part==self.root:break
        return candidate
    def immutable(self,relative,value):
        path=self.safe(relative);path.parent.mkdir(parents=True,exist_ok=True);data=encoded(value)
        if path.exists():
            if path.read_bytes()!=data:raise ValueError('不可变协议文件发生冲突')
            return path
        temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            # Windows rename refuses an existing target, including inside MXC.
            # POSIX rename would overwrite, so retain no-replace hardlink there.
            try:
                if os.name=='nt':os.rename(temporary,path)
                else:os.link(temporary,path)
            except FileExistsError:
                if path.read_bytes()!=data:raise ValueError('不可变协议文件并发冲突')
        finally:temporary.unlink(missing_ok=True)
        return path
    def read_owned(self,path,folder):
        supplied=Path(path).absolute();relative=supplied.relative_to(self.root.absolute())
        if relative.parts[0]!=folder:raise ValueError('协议文件位置不符')
        p=self.safe(relative)
        if not p.is_file() or p.stat().st_size>262144:raise ValueError('协议文件不存在或过大')
        return json.loads(p.read_text(encoding='utf-8'))
    def create(self,definition,connection=None):
        shape(definition,{'kind','project_id','issue_key','content'});kind=definition['kind'];project=identifier(definition['project_id']);issue=identifier(definition['issue_key']);c=content(definition['content'])
        if kind not in {'seo','automation'}:raise ValueError('工单归属无效')
        key=hashlib.sha256(encoded([kind,project,issue])).hexdigest()[:20]
        def run(db):
            owner=db.execute('SELECT payload FROM records WHERE kind=? AND id=?',('seo_project' if kind=='seo' else 'automation',project)).fetchone()
            if not owner:raise ValueError('目标项目/任务不存在，先接入自己的对象')
            owner=json.loads(owner[0]);found=db.execute("SELECT payload FROM records WHERE kind='ticket' AND id=?",(key,)).fetchone()
            r={'id':key,'number':('SEO-' if kind=='seo' else 'AW-')+key[:8].upper(),'database_id':self.database_id,'kind':kind,'project_id':project,'site':owner.get('site','本机任务'),'issue_key':issue,'content':c,'revision':1,'synthetic':owner.get('source')=='synthetic','state':'pending','reason':'尚未领取','created_at':self.now().isoformat(),'updated_at':self.now().isoformat(),'claim':None,'attempts':[],'events':[],'versions':[],'receipts':{},'last_result':None}
            r['content_hash']=version_hash(r)
            if found:
                old=self.load(db,key)
                if old['content_hash']!=r['content_hash']:raise ValueError('同问题已有工单，须显式修订，不重复建单')
                return self.view(old)
            self.event(r,'created','工单建立；未领取');self.save(db,r);return self.view(r)
        return run(connection) if connection is not None else self.tx(run)
    def show(self,key):return self.tx(lambda db:self.view(self.load(db,identifier(key))))
    def list(self):return self.tx(lambda db:[self.view(json.loads(row[0])) for row in db.execute("SELECT payload FROM records WHERE kind='ticket' ORDER BY id")])
    def revise(self,key,revision,hash_value,value):
        c=content(value)
        def run(db):
            r=self.load(db,key);self.match(r,revision,hash_value)
            if r['state']!='pending' or r['claim'] or r['attempts']:raise ValueError('只有尚未执行工单可修订，历史结果不覆盖')
            if c==r['content']:return self.view(r)
            r['versions'].append({k:deepcopy(r[k]) for k in ['revision','content_hash','content']});r['content']=c;r['revision']+=1;r['content_hash']=version_hash(r)
            self.event(r,'revised','当前修订已更新，旧提示无效');self.save(db,r);return self.view(r)
        return self.tx(run)
    def journal(self,r,actor,operation):
        name=hashlib.sha256(encoded([r['id'],operation])).hexdigest()+'.json';relative=Path('claims')/name;path=self.safe(relative)
        if path.exists():
            value=self.read_owned(path,'claims')
            if any(value[k]!=v for k,v in {'database_id':self.database_id,'ticket_id':r['id'],'revision':r['revision'],'content_hash':r['content_hash'],'actor':actor,'operation_id':operation}.items()):raise ValueError('领取操作ID已用于其他上下文')
            return path,value
        value={'database_id':self.database_id,'ticket_id':r['id'],'revision':r['revision'],'content_hash':r['content_hash'],'actor':actor,'operation_id':operation,'attempt_id':secrets.token_hex(16),'secret':secrets.token_hex(32)}
        return self.immutable(relative,value),value
    def claim(self,key,revision,hash_value,actor,operation):
        identifier(actor);identifier(operation)
        def run(db):
            r=self.load(db,key);self.match(r,revision,hash_value)
            if r.get('claim'):
                claim=r['claim']
                if claim['operation_id']==operation and claim['owner']==actor:
                    path,j=self.journal(r,actor,operation);self.owns(r,j)
                    return {'ticket':self.view(r),'claim_file':str(path),'can_execute':False,'decision':'inspect_existing_result'}
                raise ValueError('已有领取/结果记录；不自动解锁或重复执行')
            if r['state']!='pending':raise ValueError('当前状态不能领取，先核对已有结果')
            # An old operation remains consumed even after explicit safe retry.
            if any(x['operation_id']==operation for x in r['attempts']):raise ValueError('旧领取操作ID不能再执行')
            path,j=self.journal(r,actor,operation)
            claim={'attempt_id':j['attempt_id'],'owner':actor,'operation_id':operation,'secret_digest':hashlib.sha256(j['secret'].encode()).hexdigest(),'started_at':self.now().isoformat(),'lease_until':(self.now()+timedelta(minutes=15)).isoformat(),'external':None}
            r['claim']=claim;r['attempts'].append(claim);r['state']='in_progress';r['reason']='已领取，等待实际执行结果'
            self.event(r,'claimed','当前修订由'+actor+'领取');self.save(db,r)
            return {'ticket':self.view(r),'claim_file':str(path),'can_execute':True,'decision':'new_attempt'}
        return self.tx(run)
    def owns(self,r,j):
        self.match(r,j['revision'],j['content_hash']);c=r.get('claim')
        if not c or c['attempt_id']!=j['attempt_id'] or not hmac.compare_digest(c['secret_digest'],hashlib.sha256(j['secret'].encode()).hexdigest()):raise ValueError('领取凭据不属于当前attempt')
        if j['database_id']!=self.database_id:raise ValueError('领取文件属于其他库')
        return c
    def active(self,r,c):
        if r['state']!='in_progress' or stamp(c['lease_until'])<=self.now():raise ValueError('领取已中断或待核对，不能恢复执行；先reconcile已有结果')
    def heartbeat(self,claim_file):
        j=self.read_owned(claim_file,'claims')
        def run(db):
            r=self.load(db,j['ticket_id']);c=self.owns(r,j);self.active(r,c);c['lease_until']=(self.now()+timedelta(minutes=15)).isoformat()
            r['attempts'][-1]=c;self.save(db,r);return self.view(r)
        return self.tx(run)
    def external_begin(self,claim_file):
        j=self.read_owned(claim_file,'claims')
        def run(db):
            r=self.load(db,j['ticket_id']);c=self.owns(r,j);self.active(r,c)
            if r['content']['external']['kind']=='none':raise ValueError('本工单没有外部动作范围')
            if c['external']:
                r['state']='needs_reconciliation';r['reason']='外部意图已发出，必须先核对目标结果，不重复发布';self.event(r,'reconciliation_required',r['reason']);self.save(db,r)
                return {'proceed':False,'ticket':self.view(r),'intent_id':c['external']['intent_id']}
            intent={'intent_id':secrets.token_hex(16),'target':r['content']['external']['target'],'status':'pending','at':self.now().isoformat()}
            c['external']=intent;r['attempts'][-1]=c
            self.immutable(Path('intents')/(intent['intent_id']+'.json'),{'database_id':self.database_id,'ticket_id':r['id'],'attempt_id':c['attempt_id'],**intent})
            self.event(r,'external_intent','只允许一次外部动作；结果不明先核对');self.save(db,r)
            return {'proceed':True,'intent_id':intent['intent_id'],'target':intent['target'],'ticket':self.view(r)}
        return self.tx(run)
    def evidence(self,items,required=False):
        if not isinstance(items,list) or len(items)>8 or (required and not items):raise ValueError('需要有限实际证据')
        file_count=0
        for item in items:
            shape(item,{'kind','ref','sha256'})
            if item['kind']!='file' or not isinstance(item['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',item['sha256']):raise ValueError('证据需为本产品artifacts下的文件及实际SHA256')
            relative=Path(text(item['ref'],1024))
            if not relative.parts or relative.parts[0]!='artifacts':raise ValueError('证据只限本数据根artifacts目录')
            f=self.safe(relative)
            if not f.is_file() or f.stat().st_size>2097152 or hashlib.sha256(f.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('证据缺失/过大/摘要不符')
            file_count+=1
        return file_count
    def validate_receipt(self,value):
        if len(encoded(value))>65536:raise ValueError('回执超过64KiB')
        forbid_secrets(value);shape(value,{'receipt_id','ticket_id','revision','content_hash','attempt_id','outcome','summary','verification','external','retry_safe','observed_at'},{'deployed_at'})
        for k in ['receipt_id','ticket_id','attempt_id']:identifier(value[k])
        if type(value['revision'])!=int or not isinstance(value['content_hash'],str):raise ValueError('回执修订/摘要无效')
        if value['outcome'] not in {'succeeded','no_change','failed','blocked','needs_reconciliation'}:raise ValueError('执行结果无效')
        text(value['summary'],4000)
        if type(value['retry_safe'])!=bool:raise ValueError('retry_safe必须为布尔值')
        observed=stamp(value['observed_at'])
        if observed>self.now()+timedelta(minutes=5):raise ValueError('回执时间在未来')
        v=value['verification'];shape(v,{'status','checks'})
        if v['status'] not in {'passed','failed','not_run'} or not isinstance(v['checks'],list) or len(v['checks'])>20:raise ValueError('验证字段无效')
        for c in v['checks']:
            shape(c,{'name','status','evidence'});text(c['name'],200)
            if c['status'] not in {'passed','failed'}:raise ValueError('检查结果无效')
            self.evidence(c['evidence'],required=True)
        if v['status']=='passed' and (not v['checks'] or any(c['status']!='passed' for c in v['checks'])):raise ValueError('验证通过需要实际检查及证据')
        if value['outcome'] in {'succeeded','no_change'} and v['status']!='passed':raise ValueError('未验证不能标执行完毕')
        external=value['external'];shape(external,{'status','intent_id','target','evidence'})
        if external['status'] not in {'not_required','not_attempted','confirmed_absent','confirmed_success','unknown'}:raise ValueError('外部结果状态无效')
        if 'deployed_at' in value:
            if external['status']!='confirmed_success' or stamp(value['deployed_at'])>observed:raise ValueError('上线时间须来自已确认发布且不晚于回执观察')
        self.evidence(external['evidence'],required=external['status'] in {'confirmed_success','confirmed_absent'})
        if value['retry_safe'] and (value['outcome'] not in {'failed','blocked'} or v['status']!='passed' or external['status'] not in {'not_required','not_attempted','confirmed_absent'}):raise ValueError('未证明可安全重试')
        return deepcopy(value)
    def after_stage(self):pass  # fault injection seam for isolated tests; never a CLI bypass
    def report(self,claim_file,receipt):
        j=self.read_owned(claim_file,'claims');return self._report(j['ticket_id'],receipt,j=j)
    def reconcile(self,key,revision,hash_value,receipt):
        return self._report(key,receipt,expected=(revision,hash_value))
    def _report(self,key,receipt,j=None,expected=None):
        value=self.validate_receipt(receipt);fingerprint=digest(value)
        def run(db):
            r=self.load(db,key)
            if j:self.owns(r,j)
            else:
                self.match(r,*expected)
                if self.view(r)['state'] not in {'needs_reconciliation','incomplete'}:raise ValueError('仅中断/未完成工单可无领取凭据核对')
            self.match(r,value['revision'],value['content_hash']);c=r.get('claim')
            if value['ticket_id']!=r['id'] or not c or value['attempt_id']!=c['attempt_id'] or stamp(value['observed_at'])<stamp(c['started_at']):raise ValueError('回执不属于当前attempt或时间早于领取')
            if value['receipt_id'] in r['receipts']:
                if r['receipts'][value['receipt_id']]!=fingerprint:raise ValueError('相同回执ID内容冲突')
                return {'ticket':self.view(r),'idempotent':True,'replayed_business':False}
            if r['state']=='completed':raise ValueError('已完成工单不能被新回执覆盖')
            if r['last_result'] and stamp(value['observed_at'])<stamp(r['last_result']['observed_at']):raise ValueError('旧回执不能覆盖较新结果')
            ext=value['external'];configured=r['content']['external'];intent=c['external']
            if configured['kind']=='none':
                if ext['status']!='not_required' or ext['intent_id'] is not None or ext['target'] is not None:raise ValueError('无外部动作工单不能回填发布')
            else:
                if ext['target']!=configured['target']:raise ValueError('外部目标不匹配')
                if intent:
                    if ext['intent_id']!=intent['intent_id'] or ext['status'] in {'not_attempted','not_required'}:raise ValueError('已有意图必须核对结果，不能声称尚未执行')
                    if value.get('deployed_at') and stamp(value['deployed_at'])<stamp(intent['at']):raise ValueError('上线时间不能早于本次外部意图')
                    if intent['status']=='confirmed_success' and ext['status']!='confirmed_success':raise ValueError('已确认外部成功不能降级或重发')
                elif ext['status']!='not_attempted' or ext['intent_id'] is not None:raise ValueError('没有先记录外部意图')
                if value['outcome'] in {'succeeded','no_change'} and ext['status']!='confirmed_success':raise ValueError('未确认外部结果不能关单')
            relative=Path('receipts')/(r['id']+'-'+value['receipt_id']+'.json');self.immutable(relative,value);self.after_stage()
            if intent:intent['status']=ext['status']
            c['result']=value;r['attempts'][-1]=c;r['last_result']=value;r['receipts'][value['receipt_id']]=fingerprint
            r['state']='completed' if value['outcome'] in {'succeeded','no_change'} else 'needs_reconciliation' if value['outcome']=='needs_reconciliation' or ext['status']=='unknown' else 'incomplete'
            r['reason']=value['summary'];self.event(r,'result_recorded',value['summary']);self.save(db,r)
            return {'ticket':self.view(r),'idempotent':False,'receipt_file':str(self.root/relative),'replayed_business':False}
        return self.tx(run)
    def recover(self,claim_file,receipt_id):
        j=self.read_owned(claim_file,'claims');identifier(receipt_id)
        value=self.read_owned(self.root/'receipts'/(j['ticket_id']+'-'+receipt_id+'.json'),'receipts')
        return self.report(claim_file,value)
    def interrupt(self,claim_file,reason):
        j=self.read_owned(claim_file,'claims');text(reason,1000);forbid_secrets(reason)
        def run(db):
            r=self.load(db,j['ticket_id']);self.owns(r,j)
            if r['state']=='completed':raise ValueError('已完成记录不改成中断')
            r['state']='needs_reconciliation';r['reason']=reason;self.event(r,'interrupted',reason);self.save(db,r);return self.view(r)
        return self.tx(run)
    def retry(self,key,revision,hash_value):
        def run(db):
            r=self.load(db,key);self.match(r,revision,hash_value);last=r['last_result']
            if r['state']!='incomplete' or not last or not last['retry_safe']:raise ValueError('没有可安全重试的核对证据')
            if r['claim']['external']:raise ValueError('外部意图已经发出；本协议不重发，即使暂未查到结果也不能排除在途执行')
            r['claim']=None;r['state']='pending';r['reason']='已核对可安全重试，仍需新的显式领取操作ID';self.event(r,'retry_ready',r['reason']);self.save(db,r);return self.view(r)
        return self.tx(run)

def project_records(grouped,root):
    """Projection only: GET never claims, seeds, renews or modifies records."""
    rows=[visible(r) for r in grouped.get('ticket',[])]
    for t in rows:t['prompt']=prompt(t,root)
    for p in grouped.get('seo_project',[]):
        own=[r for r in rows if r['kind']=='seo' and r['project_id']==p['id']]
        p['suggestions']=p.get('suggestions',[])+[{**t,'protocol':True,'status':t['state']} for t in own]
        p['runs']=p.get('runs',[])+[{'id':a['attempt_id'],'suggestion_id':t['id'],'revision':t['revision'],'content_hash':t['content_hash'],'kind':'attempt','status':{'in_progress':'started','completed':(t['last_result'] or {}).get('outcome','succeeded'),'incomplete':'failed','needs_reconciliation':'needs_reconciliation','pending':'failed'}[t['state']] if a['attempt_id']==(t.get('claim') or {}).get('attempt_id') else a.get('result',{}).get('outcome','needs_reconciliation'),'title':t['content']['title'],'mutation_type':t['content']['mutation_type'],'summary':a.get('result',{}).get('summary','已领取，等待实际结果'),'updated_at':a.get('result',{}).get('observed_at',a['started_at']),'verification':a.get('result',{}).get('verification',{}).get('status','not_run'),'deployment':a.get('result',{}).get('external',{}).get('status',(a.get('external') or {}).get('status','not_required' if t['content']['external']['kind']=='none' else 'not_attempted')),'effect':'not_observed','deployed_at':a.get('result',{}).get('deployed_at')} for t in own for a in t['attempts']]
    auto=[{'id':t['id'],'code':t['number'],'target':t['project_id'],'state':{'completed':'resolved','in_progress':'executing'}.get(t['state'],t['state']),'state_label':t['state_label'],'fault':t['content']['title'],'opened':t['created_at'],'type':'protocol','protocol':True,'diagnosis':{'summary':t['reason'],'evidence':t['content']['rationale'],'repair_scope':t['content']['scope']},'prompt':t['prompt'],'events':t['events'],'protocol_result':t['last_result']} for t in rows if t['kind']=='automation']
    grouped['automation_ticket']=grouped.get('automation_ticket',[])+auto
    grouped['automation_event']=grouped.get('automation_event',[])+[{'ticket':t['id'],'code':t['code'],**ev} for t in auto for ev in t['events']]
    return rows
