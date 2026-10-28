"""Thin native-client handoffs. Production work stays in the user's own chat.

The optional CLI launcher accepts marked synthetic workspaces only. It never
claims, repairs, publishes, authenticates, or retries on behalf of a client.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from .paths import owned_root
from .skill_scan import linked
from .tickets import Tickets,identifier,prompt,digest
from .clients_process import execute

CLIENTS={'codex','claude'}
MARKER='.luxixi-client-test.json'
MARKER_VALUE={'app':'luxixi-workbench','scope':'synthetic-client-test','version':1}
# Remove values only in the new process; never alter the user's environment or credentials.
ROUTING={'OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','OPENAI_API_BASE','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_OAUTH_TOKEN','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY','ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL'}

def clean_environment(source=None):
    result={k:v for k,v in (os.environ if source is None else source).items() if k not in ROUTING}
    result['GIT_TERMINAL_PROMPT']='0';result['GCM_INTERACTIVE']='never'
    return result

def safe_directory(value):
    path=Path(value).expanduser().absolute()
    if not path.is_dir() or any(linked(x) for x in [path,*path.parents]):raise ValueError('目录不存在或经过链接/junction')
    return path.resolve()

def executable(client):
    if client not in CLIENTS:raise ValueError('仅支持Codex和Claude Code本机入口')
    if client=='codex':
        value=shutil.which('codex.exe' if os.name=='nt' else 'codex')
        return [value] if value else None
    value=shutil.which('claude.exe' if os.name=='nt' else 'claude')
    if value:return [value]
    # Avoid Windows batch-shell argument interpolation for npm's public CLI shim.
    shim=shutil.which('claude.cmd');node=shutil.which('node')
    if shim and node:
        cli=Path(shim).parent/'node_modules/@anthropic-ai/claude-code/cli.js'
        if cli.is_file():return [node,str(cli)]
    return None

def probe_process(argv,cwd=None):
    return subprocess.run(argv,cwd=cwd,env=clean_environment(),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,shell=False,**({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))

def detect(client,probe=probe_process):
    entry=executable(client)
    result={'client':client,'entry_available':bool(entry),'version':'unavailable','subscription_login':False,'auth_status':'not_checked','format_ready':False,'native_workflow':'not_verified','model_api_key_required':False,'personal_config_read_by_adapter':False}
    if not entry:return result
    version=probe([*entry,'--version']);help_result=probe([*entry,'exec','--help'] if client=='codex' else [*entry,'--help'])
    result['version']=version.stdout.strip()[:120] if version.returncode==0 else 'version_failed'
    required=['--ephemeral','--ignore-user-config','--ignore-rules','--sandbox','--json','--output-schema','--skip-git-repo-check','--add-dir'] if client=='codex' else ['--print','--output-format','--no-session-persistence','--setting-sources','--strict-mcp-config','--json-schema','--permission-mode','--tools','--allowedTools']
    result['format_ready']=help_result.returncode==0 and all(flag in help_result.stdout for flag in required)
    status=probe([*entry,'login','status'] if client=='codex' else [*entry,'--setting-sources','project','auth','status','--json'])
    if client=='codex':
        words=(status.stdout+status.stderr).lower()
        result['subscription_login']=status.returncode==0 and 'chatgpt' in words and 'api key' not in words
    else:
        try:payload=json.loads(status.stdout)
        except (ValueError,TypeError):payload={}
        if not isinstance(payload,dict):payload={}
        result['subscription_login']=status.returncode==0 and payload.get('loggedIn') is True and payload.get('authMethod') in {'claude.ai','oauth','oauth_token'}
    result['auth_status']='subscription_available' if result['subscription_login'] else 'subscription_not_available'
    return result

def final_schema(plan):
    fields={'client':{'type':'string','enum':[plan['client']]},'database_id':{'type':'string','enum':[plan['database_id']]},'ticket_id':{'type':'string','enum':[plan['ticket_id']]},'revision':{'type':'integer','enum':[plan['revision']]},'content_hash':{'type':'string','enum':[plan['content_hash']]},'state':{'type':'string','enum':['completed','already_completed','blocked','needs_reconciliation','incomplete']},'summary':{'type':'string'}}
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}

def handoff(flow,ticket,client,workspace,run_id):
    skill=workspace/('.agents' if client=='codex' else '.claude')/'skills/luxixi-workbench'
    if not (skill/'SKILL.md').is_file() or linked(skill):raise ValueError('所选工作区未安装本Skill；先使用包内项目级安装器')
    for path in [skill,skill.parent,skill.parent.parent]:
        if linked(path):raise ValueError('Skill入口不能经过链接/junction')
    actor=client+'-'+run_id[:12];operation='native-'+run_id
    instruction=('$luxixi-workbench' if client=='codex' else '/luxixi-workbench')+'\n请先实际读取本工作区 '+str(skill/'SKILL.md')+' 及其引用的 '+client+'.md 和 tickets.md，再处理以下用户执行指令。\n'
    if ticket['synthetic']:
        instruction+='本次仅隔离合成资源；仅可读取本工作区和工单明确给出的本包记录程序，只有本工作区可写。禁止访问真实网站、Google、其他工作台/配置/凭据/旧聊天，不调用网络/浏览器/MCP或子代理。不要读取领取密钥正文。\n'
    else:
        instruction+='只处理当前工单明确授权的目标与所选工作区；准备交接不扩大网站、Google或外部动作授权。不得读取无关工作台、配置、凭据或旧聊天。不要读取领取密钥正文。\n'
    instruction+=prompt(ticket,flow.root)+'\n'
    instruction+='本次若需要新领取，actor固定为 '+actor+'，operation-id固定为 '+operation+'。不要替换为其他标识绕过已有领取。\n'
    instruction+='若show已完成，先核对既有验证证据和产物，绝不再claim、修改或report。若需核对/冲突，只报告缺口，不retry业务动作。\n'
    instruction+='完成后最终JSON只报告实际同库状态；client='+client+'，database_id='+flow.database_id+'，ticket_id='+ticket['id']+'，revision='+str(ticket['revision'])+'，content_hash='+ticket['content_hash']+'；state为completed/already_completed/blocked/needs_reconciliation/incomplete，summary说明实际结果。最终回复本身不代替回执。'
    return {'client':client,'run_id':run_id,'database_id':flow.database_id,'data_dir':str(flow.root),'workspace':str(workspace),'ticket_id':ticket['id'],'revision':ticket['revision'],'content_hash':ticket['content_hash'],'actor':actor,'operation_id':operation,'skill':str(skill),'prompt':instruction,'created_at':datetime.now(timezone.utc).isoformat()}

class Clients:
    def __init__(self,root,db_id):self.flow=Tickets(root,db_id);self.root=self.flow.root
    def prepare(self,key,client,workspace):
        if client not in CLIENTS:raise ValueError('客户端无效')
        workspace=safe_directory(workspace);ticket=self.flow.show(identifier(key));run_id=uuid.uuid4().hex
        plan=handoff(self.flow,ticket,client,workspace,run_id)
        path=self.flow.immutable(Path('client_handoffs')/(run_id+'.json'),plan)
        self.flow.tx(lambda db:db.execute('INSERT INTO records VALUES(?,?,?)',('client_handoff',run_id,json.dumps({'run_id':run_id,'sha256':digest(plan),'client':client,'ticket_id':ticket['id']},separators=(',',':')))))
        return {'plan_file':str(path),'run_id':run_id,'client':client,'ticket_state':ticket['state'],'ticket_state_changed':False}
    def read_plan(self,path):
        plan=self.flow.read_owned(path,'client_handoffs')
        binding=self.flow.tx(lambda db:db.execute("SELECT payload FROM records WHERE kind='client_handoff' AND id=?",(plan.get('run_id'),)).fetchone())
        if not binding or json.loads(binding[0]).get('sha256')!=digest(plan):raise ValueError('handoff内容或原始记录不一致')
        if plan.get('client') not in CLIENTS:raise ValueError('计划客户端无效')
        identifier(plan['run_id']);ticket=self.flow.show(plan['ticket_id'])
        self.flow.match(ticket,plan['revision'],plan['content_hash'])
        if plan['database_id']!=self.flow.database_id or Path(plan['data_dir'])!=self.root:raise ValueError('计划不属于本库/数据根')
        workspace=safe_directory(plan['workspace'])
        expected=handoff(self.flow,ticket,plan['client'],workspace,plan['run_id'])
        # The original prompt is immutable across state transitions; bind all execution fields.
        for key in ['client','run_id','database_id','data_dir','workspace','ticket_id','revision','content_hash','actor','operation_id','skill']:
            if plan.get(key)!=expected[key]:raise ValueError('计划执行字段被修改')
        if not isinstance(plan.get('prompt'),str) or len(plan['prompt'])>30000:raise ValueError('handoff文本无效')
        if Path(path).name!=plan['run_id']+'.json':raise ValueError('计划文件身份不符')
        return plan,ticket,workspace
    def arguments(self,plan,run_root,entry):
        client=plan['client'];schema=final_schema(plan);self.flow.immutable(run_root.relative_to(self.root)/'schema.json',schema)
        if client=='codex':
            args=[*entry,'exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','workspace-write','-c','approval_policy="never"','-c','project_doc_max_bytes=0','-c','web_search="disabled"','--json','-C',plan['workspace'],'--add-dir',str(self.root),'--output-schema',str(run_root/'schema.json'),'-o',str(run_root/'final.json'),'-']
            if os.name=='nt':args[2:2]=['-c','windows.sandbox="mxc"']
            return args
        self.flow.immutable(run_root.relative_to(self.root)/'mcp-empty.json',{'mcpServers':{}})
        return [*entry,'-p','--output-format','json','--no-session-persistence','--setting-sources','project','--strict-mcp-config','--mcp-config',str(run_root/'mcp-empty.json'),'--no-chrome','--permission-mode','dontAsk','--tools','Read,Edit,Write,Bash,Glob,Grep,Skill','--allowedTools','Read','Edit','Write','Glob','Grep','Skill','Bash(python:*)','--add-dir',str(self.root),'--json-schema',json.dumps(schema,separators=(',',':'))]
    execute=staticmethod(execute)
    def inspect_business(self,plan,before):
        current=self.flow.show(plan['ticket_id']);business={'state':current['state'],'completed':False,'attribution':'none','evidence_valid':False}
        try:self.flow.match(current,plan['revision'],plan['content_hash'])
        except (ValueError,TypeError):return {**business,'identity_changed':True}
        if current['state']!='completed':return business
        last=current.get('last_result')
        if not last:return business
        try:self.flow.validate_receipt(last)
        except (ValueError,TypeError,KeyError,OSError):return {**business,'evidence_error':'receipt_or_artifacts_invalid'}
        unchanged=all(current.get(k)==before.get(k) for k in ['revision','content_hash','attempts','events','receipts','updated_at','last_result'])
        owned=(current.get('claim') or {}).get('owner')==plan['actor'] and (current.get('claim') or {}).get('operation_id')==plan['operation_id']
        if before['state']=='completed':return {**business,'completed':unchanged,'attribution':'existing_result' if unchanged else 'unexpected_changes','evidence_valid':True}
        return {**business,'completed':owned,'attribution':'this_client' if owned else 'other_executor','evidence_valid':True}
    @staticmethod
    def native_final(plan,run_root):
        try:
            root=run_root.resolve()
            if any(linked(x) for x in [run_root,*run_root.parents]):return None
            if plan['client']=='codex':
                file=run_root/'final.json'
                if linked(file) or not file.resolve().is_relative_to(root) or not file.is_file() or file.stat().st_size>65536:return None
                value=json.loads(file.read_text(encoding='utf-8'))
            else:
                file=run_root/'stdout.jsonl'
                if linked(file) or not file.resolve().is_relative_to(root) or file.stat().st_size>2097152:return None
                result=json.loads(file.read_text(encoding='utf-8'))
                if not isinstance(result,dict):return None
                if result.get('is_error'):return None
                value=result.get('structured_output')
                if value is None:value=json.loads(result.get('result',''))
            if not isinstance(value,dict):return None
            if any(value.get(k)!=plan[k] for k in ['client','database_id','ticket_id','revision','content_hash']):return None
            if value.get('state') not in {'completed','already_completed','blocked','needs_reconciliation','incomplete'} or not isinstance(value.get('summary'),str):return None
            return value
        except (OSError,ValueError,TypeError):return None
    def run_isolated(self,path,timeout=480,detector=detect,executor=None):
        if executor is None and os.name!='nt':raise ValueError('原生隔离启动器目前仅验证Windows；其他系统仅准备本机交接，不自动启动')
        if type(timeout)!=int or not 1<=timeout<=900:raise ValueError('超时仅支持1到900秒')
        plan,before,workspace=self.read_plan(path)
        marker=workspace/MARKER
        if linked(marker) or not marker.is_file() or json.loads(marker.read_text(encoding='utf-8'))!=MARKER_VALUE:raise ValueError('仅运行明确标记的新隔离测试工作区')
        if not self.root.is_relative_to(workspace) or not before['synthetic'] or before['content']['external']['kind']!='none':raise ValueError('只允许同一隔离工作区内的合成库/无外部动作工单')
        if before['state'] not in {'pending','completed'}:raise ValueError('当前工单已被领取/待核对，不启动另一个客户端')
        status=detector(plan['client'])
        if not status['entry_available'] or not status['format_ready'] or not status['subscription_login']:
            return {'client':plan['client'],'run_id':plan['run_id'],'started':False,'status':'client_or_subscription_unavailable','transport':{'status':'client_or_subscription_unavailable'},'capability':status,'business':self.inspect_business(plan,before),'safe_to_retry_business':False}
        run_root=self.flow.safe(Path('client_runs')/plan['run_id'])
        if run_root.exists():raise ValueError('此原生运行已尝试；先读既有输出和同库结果，不自动再次运行')
        run_root.mkdir(parents=True)
        args=self.arguments(plan,run_root,executable(plan['client']))
        (run_root/'prompt.txt').write_text(plan['prompt'],encoding='utf-8')
        execute=executor or self.execute
        try:transport=execute(args,plan['prompt'],workspace,clean_environment(),timeout,run_root)
        except Exception as error:transport={'exit_code':None,'timed_out':False,'process_exited':False,'error':type(error).__name__}
        if transport.get('timed_out') or transport.get('exit_code')!=0:
            current=self.flow.show(plan['ticket_id']);claim=current.get('claim') or {}
            if current['revision']==plan['revision'] and current['content_hash']==plan['content_hash'] and current['state']=='in_progress' and claim.get('owner')==plan['actor'] and claim.get('operation_id')==plan['operation_id'] and transport.get('process_exited'):
                name=hashlib.sha256(json.dumps([plan['ticket_id'],plan['operation_id']],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()+'.json'
                self.flow.interrupt(self.root/'claims'/name,'本次原生客户端已退出或超时终止，先核对已有结果，不重新执行')
        native=self.native_final(plan,run_root);business=self.inspect_business(plan,before)
        transport_ok=transport.get('exit_code')==0 and not transport.get('timed_out') and not transport.get('output_limit_exceeded') and not transport.get('reader_failed')
        if executor is None:transport_ok=transport_ok and transport.get('process_exited') is True and transport.get('tree_cleanup_confirmed') is True and not transport.get('tree_cleanup_error')
        if business['completed']:status_name='verified_completion' if native and native['state'] in {'completed','already_completed'} and transport_ok else 'business_completed_client_unconfirmed'
        else:status_name='needs_reconciliation' if business['state'] in {'in_progress','needs_reconciliation','incomplete'} else 'no_verified_business_receipt'
        result={'client':plan['client'],'run_id':plan['run_id'],'started':True,'source':'native_cli' if executor is None else 'simulated_transport','transport':transport,'native_final_valid':native is not None,'business':business,'status':status_name,'safe_to_retry_business':False,'output_dir':str(run_root),'note':'客户端退出/回复不等于业务结果；失败或超时先查同库，不重做'}
        self.flow.immutable(run_root.relative_to(self.root)/'observation.json',result)
        return result
