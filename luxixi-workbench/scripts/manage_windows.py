"""Explicit Windows lifecycle for this installed Skill; user data is never deleted."""
import argparse
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode=True
from workbench import verify_runtime, execute, read_environment_index, environment_paths
from windows_shell import shortcut, startup_directory

SKILL=Path(__file__).resolve().parents[1]

@contextmanager
def management_lock(ctx):
    import msvcrt
    path=ctx['root']/('windows-manage-'+ctx['scope']+'.lock')
    if linked(path):raise ValueError('管理锁不能是链接')
    with path.open('a+b') as f:
        f.seek(0)
        if not f.read(1):f.write(b'0');f.flush()
        deadline=time.monotonic()+5
        while True:
            f.seek(0)
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                if time.monotonic()>=deadline:raise ValueError('另一项Windows管理正在执行；请先核对同库状态')
                time.sleep(.05)
        try:yield
        finally:
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def serialized(function):
    @wraps(function)
    def wrapped(ctx,*args,**kwargs):
        with management_lock(ctx):return function(ctx,*args,**kwargs)
    return wrapped

def linked(path):
    try:return path.is_symlink() or bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except FileNotFoundError:return False

def safe_path(path):
    path=Path(path).expanduser()
    if not path.is_absolute() or any(linked(p) for p in [path,*path.parents]):
        raise ValueError('只接受绝对路径，不能经过链接/junction')
    return path.resolve()

def load(path):
    if linked(path) or not path.is_file() or path.stat().st_size>262144:raise ValueError('管理记录不存在/过大或是链接')
    return json.loads(path.read_text(encoding='utf-8'))

def save(path,value):
    if linked(path):raise ValueError('管理记录不能是链接')
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def context(data):
    if os.name!='nt':raise ValueError('本入口仅适用于Windows；其他系统未由此入口验收')
    safe_path(SKILL)
    if SKILL.name!='luxixi-workbench' or SKILL.parent.name!='skills' or SKILL.parents[1].name not in {'.agents','.claude'}:
        raise ValueError('请在项目原生目录中已安装的Skill副本运行本入口')
    manifest=load(SKILL/'bundle-manifest.json');signature=fingerprint(SKILL/'bundle-manifest.json')
    if load(SKILL/'installation.json')!={'skill':'luxixi-workbench','manifest':signature}:raise ValueError('安装身份不匹配')
    for item in manifest['files']:
        file=safe_path(SKILL/item['path'])
        if not file.is_relative_to(SKILL) or fingerprint(file)!=item['sha256']:raise ValueError('已安装文件被修改；不操作')
    verify_runtime()
    root=safe_path(data)
    if root.is_relative_to(SKILL) or SKILL.is_relative_to(root):raise ValueError('数据目录必须在安装目录外，且不能包含安装目录')
    identity=execute('luxixi_workbench.ticket_cli',['--data-dir',str(root),'identity'],capture=True)
    if identity.returncode:raise ValueError(identity.stderr.strip() or '无法核对数据根')
    database=json.loads(identity.stdout)['database_id']
    scope=hashlib.sha256((str(SKILL)+'\n'+database).encode('utf-8')).hexdigest()[:24]
    return {'root':root,'database_id':database,'scope':scope,'manifest':signature,'files':manifest['files']}

def startup_folder(ctx,fixture):
    if fixture:
        directory=safe_path(fixture)
        marker=load(directory/'.luxixi-startup-fixture.json')
        if marker!={'app':'luxixi-workbench','synthetic':True,'data_dir':str(ctx['root'])}:raise ValueError('隔离Startup目录标记与数据根不符')
        return directory,'synthetic_directory'
    return safe_path(startup_directory()),'current_user_startup'

def receipt_path(ctx):return ctx['root']/('windows-startup-'+ctx['scope']+'.json')

def expected(ctx,directory,mode):
    target=Path(sys.executable).with_name('pythonw.exe')
    if not target.is_file() or target.resolve().is_relative_to(SKILL):raise ValueError('请使用安装时的外部Python运行管理入口，不能从将卸载的venv运行')
    args=['-X','utf8','-B',str(Path(__file__).resolve()),'startup-run','--data-dir',str(ctx['root'])]
    return {'app':'luxixi-workbench','schema':1,'scope':ctx['scope'],'skill':str(SKILL),'database_id':ctx['database_id'],'manifest':ctx['manifest'],
            'mode':mode,'path':str(directory/('LuxixiWorkbench-'+ctx['scope']+'.lnk')),'target':str(target),'arguments':subprocess.list2cmdline(args),'cwd':str(SKILL)}

def shortcut_read(record):
    path=safe_path(record['path'])
    actual=shortcut(path)
    return actual=={k:record[k] for k in ['target','arguments','cwd']}

def read_owned(ctx):
    path=receipt_path(ctx)
    if not path.exists():return None
    value=load(path)
    if any(value.get(k)!=v for k,v in {'app':'luxixi-workbench','schema':1,'scope':ctx['scope'],'skill':str(SKILL),'database_id':ctx['database_id'],'manifest':ctx['manifest']}.items()):raise ValueError('登录启动记录不属于当前安装/数据根')
    folder=safe_path(Path(value['path']).parent)
    if value['mode']=='synthetic_directory':
        startup_folder(ctx,str(folder))
    elif value['mode']=='current_user_startup':
        if startup_folder(ctx,None)[0]!=folder:raise ValueError('当前用户Startup目录已变化，先核对原记录')
    else:raise ValueError('启动目录类型无效')
    if Path(value['path']).name!='LuxixiWorkbench-'+ctx['scope']+'.lnk':raise ValueError('快捷方式路径与范围不符')
    if any(value.get(k)!=v for k,v in expected(ctx,folder,value['mode']).items()):raise ValueError('启动参数或外部Python与原安装不一致，先核对原记录')
    if Path(value['path']).exists():
        if not shortcut_read(value) or (value.get('sha256') and fingerprint(Path(value['path']))!=value['sha256']):raise ValueError('快捷方式被修改；不覆盖或删除')
    return value

@serialized
def enable(ctx,fixture):
    directory,mode=startup_folder(ctx,fixture);record=expected(ctx,directory,mode)
    current=read_owned(ctx)
    if current and current['path']!=record['path']:raise ValueError('已有另一启动目录绑定，先显式禁用原项')
    target=Path(record['path'])
    if target.exists():
        if not current or not shortcut_read(record):raise ValueError('同名快捷方式不是当前已绑定入口，不覆盖')
        record.update(state='enabled',sha256=fingerprint(target));save(receipt_path(ctx),record);return record
    record.update(state='prepared',sha256=None);save(receipt_path(ctx),record)
    temp=directory/('.luxixi-stage-'+uuid.uuid4().hex+'.lnk')
    shortcut(temp,write=True,**{k:record[k] for k in ['target','arguments','cwd']})
    if not shortcut_read({**record,'path':str(temp)}):raise ValueError('快捷方式实际读回不一致，保留待核对')
    os.rename(temp,target)
    record.update(state='enabled',sha256=fingerprint(target));save(receipt_path(ctx),record)
    return record

def _disable(ctx):
    record=read_owned(ctx)
    if not record:return {'state':'not_configured'}
    path=Path(record['path'])
    if path.exists():path.unlink()
    record['state']='disabled';save(receipt_path(ctx),record);return record

@serialized
def disable(ctx):return _disable(ctx)

def service(ctx,action):
    result=execute('luxixi_workbench',[action,'--data-dir',str(ctx['root'])],capture=True)
    if action=='status' and result.returncode in {0,1}:
        try:return json.loads(result.stdout)
        except ValueError:pass
    if result.returncode:raise ValueError(result.stderr.strip() or '服务操作未能确认')
    return {'message':result.stdout.strip()}

def preflight_remove(ctx):
    if Path(sys.executable).resolve().is_relative_to(SKILL):raise ValueError('卸载请使用安装时的外部Python，不能删除正在执行的venv')
    if fingerprint(SKILL/'bundle-manifest.json')!=ctx['manifest'] or load(SKILL/'installation.json')!={'skill':'luxixi-workbench','manifest':ctx['manifest']}:raise ValueError('卸载期间安装身份已变化，不删除')
    for item in ctx['files']:
        file=safe_path(SKILL/item['path'])
        if not file.is_relative_to(SKILL) or fingerprint(file)!=item['sha256']:raise ValueError('卸载期间包文件已变化，不删除')
    allowed={x['path'] for x in ctx['files']}|{'bundle-manifest.json','installation.json','assets/runtime/.luxixi-environment.json','assets/runtime/.luxixi-environment-files.json'}
    allowed_dirs={p.as_posix() for x in allowed for p in Path(x).parents if p!=Path('.')}
    runtime=SKILL/'assets/runtime';env=runtime/'.venv'
    if env.exists() and load(runtime/'.luxixi-environment.json')!={'app':'luxixi-workbench','scope':'bundled-runtime'}:raise ValueError('运行环境身份不匹配')
    if env.exists():
        index=read_environment_index(runtime/'.luxixi-environment-files.json');files,dirs=environment_paths(env)
        if not dirs<=set(index['directories']):raise ValueError('独立环境有不明目录，不删除')
        for name,path in files.items():
            if name not in index['files'] or fingerprint(path)!=index['files'][name]:raise ValueError('独立环境有未知或修改文件，不删除：'+name)
    for path in SKILL.rglob('*'):
        if linked(path):raise ValueError('安装树含链接/junction，不删除')
        if path.is_relative_to(env):continue
        relative=path.relative_to(SKILL).as_posix()
        if path.is_file() and relative not in allowed or path.is_dir() and relative not in allowed_dirs:
            raise ValueError('安装目录有非包文件/目录，不删除：'+relative)
    read_owned(ctx)
    # Resolve the exact target again immediately before recursive removal.
    if safe_path(SKILL)!=SKILL or not SKILL.is_relative_to(SKILL.parents[2]):raise ValueError('卸载目标不在所选工作区')

@serialized
def uninstall(ctx):
    preflight_remove(ctx)
    service(ctx,'stop')
    if service(ctx,'status')['running']:raise ValueError('服务未停止，不删除程序')
    _disable(ctx)
    receipt=ctx['root']/('windows-uninstall-'+ctx['scope']+'.json')
    result={'app':'luxixi-workbench','skill':str(SKILL),'database_id':ctx['database_id'],'data_dir':str(ctx['root']),'policy':'keep_data','state':'prepared','observed_at':datetime.now(timezone.utc).isoformat()}
    save(receipt,result)
    try:
        preflight_remove(ctx)
        shutil.rmtree(SKILL)
        result['state']='uninstalled';save(receipt,result)
    except OSError as error:
        result.update(state='incomplete',error=str(error)[:400]);save(receipt,result);raise
    return result

@serialized
def startup_run(ctx):
    record=read_owned(ctx)
    if not record or record['state']!='enabled' or not Path(record['path']).is_file():raise ValueError('登录入口未启用，不启动服务')
    service(ctx,'start');result={'service':service(ctx,'status'),'origin':'startup_entry_invocation','os_logon_verified':False}
    save(ctx['root']/('windows-last-invocation-'+ctx['scope']+'.json'),result)
    return result

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Windows页面服务启动管理与保留数据卸载；不管理SEO排期')
    parser.add_argument('action',choices=['status','entry','enable-startup','disable-startup','startup-run','uninstall'])
    parser.add_argument('--data-dir',required=True);parser.add_argument('--synthetic-startup-dir')
    args=parser.parse_args()
    try:
        ctx=context(args.data_dir)
        if args.synthetic_startup_dir and args.action!='enable-startup':raise ValueError('合成Startup目录只用于显式启用验收入口')
        if args.action=='enable-startup':result=enable(ctx,args.synthetic_startup_dir)
        elif args.action=='disable-startup':result=disable(ctx)
        elif args.action=='uninstall':result=uninstall(ctx)
        elif args.action=='startup-run':result=startup_run(ctx)
        elif args.action=='entry':
            current=service(ctx,'status')
            if not current['running']:raise ValueError('服务未运行，先start并核对固定入口')
            path=ctx['root']/'open-workbench.url';content='[InternetShortcut]\nURL='+current['url']+'\n'
            if linked(path) or (path.exists() and path.read_text(encoding='utf-8')!=content):raise ValueError('入口文件已存在且不同，不覆盖')
            if not path.exists():path.write_text(content,encoding='utf-8')
            result={'url':current['url'],'entry_file':str(path)}
        else:result={'service':service(ctx,'status'),'startup':read_owned(ctx) or {'state':'not_configured'},'data_policy':'keep_data'}
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)[:700],'data_policy':'keep_data'},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
