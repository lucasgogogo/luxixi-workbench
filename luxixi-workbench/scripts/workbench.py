"""Standalone Skill helper: bootstrap only its bundled runtime, then typed CLIs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
import stat

SKILL=Path(__file__).resolve().parents[1]
RUNTIME=SKILL/'assets/runtime'
ENV=RUNTIME/'.venv'
ENV_INDEX=RUNTIME/'.luxixi-environment-files.json'

def linked(path):
    try:return path.is_symlink() or (os.name=='nt' and bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT))
    except FileNotFoundError:return False

def environment_paths(environment=None):
    environment=Path(environment or ENV)
    files={};directories=set();pending=[environment]
    while pending:
        parent=pending.pop()
        for path in parent.iterdir():
            if linked(path) or not path.resolve().is_relative_to(environment.resolve()):raise ValueError('独立环境含链接/junction，不接管')
            name=path.relative_to(environment).as_posix()
            if path.is_dir():directories.add(name);pending.append(path)
            elif path.is_file():files[name]=path
            else:raise ValueError('独立环境含不明文件类型')
    return files,directories

def read_environment_index(path=None):
    path=Path(path or ENV_INDEX)
    if linked(path) or not path.is_file() or path.stat().st_size>2097152:raise ValueError('独立环境归属清单缺失/过大；保留环境，不接管')
    value=json.loads(path.read_text(encoding='utf-8'))
    if set(value)!={'app','schema','files','directories'} or value['app']!='luxixi-workbench' or value['schema']!=1 or not isinstance(value['files'],dict) or not isinstance(value['directories'],list):raise ValueError('独立环境归属清单无效')
    for name in [*value['files'],*value['directories']]:
        if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts or Path(name).as_posix()!=name:raise ValueError('环境归属路径无效')
    if any(not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h) for h in value['files'].values()):raise ValueError('环境归属摘要无效')
    return value

def write_environment_index(value):
    if linked(ENV_INDEX):raise ValueError('环境归属清单不能是链接')
    temp=ENV_INDEX.with_name(ENV_INDEX.name+'.'+os.urandom(6).hex()+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(temp,ENV_INDEX)
    finally:
        if temp.exists():temp.unlink()

def python_path():return ENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def verify_runtime():
    manifest=json.loads((SKILL/'bundle-manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        if not item['path'].startswith('assets/runtime/'):continue
        path=SKILL/item['path']
        if path.is_symlink() or not path.resolve().is_relative_to(RUNTIME.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('附带运行程序摘要不匹配')

def execute(module,args,capture=False):
    return subprocess.run([str(python_path()),'-X','utf8','-B','-m',module,*args],cwd=RUNTIME,capture_output=capture,text=True,encoding='utf-8',shell=False)

def setup(argv):
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--port',type=int);args=parser.parse_args(argv)
    verify_runtime()
    marker=RUNTIME/'.luxixi-environment.json'
    if marker.is_symlink() or (hasattr(ENV,'is_junction') and ENV.is_junction()):raise ValueError('环境或标记不能是链接')
    if ENV.exists() and (ENV.is_symlink() or not marker.is_file()):raise ValueError('已有不明Python环境，不覆盖')
    if not marker.exists():marker.write_text(json.dumps({'app':'luxixi-workbench','scope':'bundled-runtime'}),encoding='utf-8')
    if json.loads(marker.read_text(encoding='utf-8'))!={'app':'luxixi-workbench','scope':'bundled-runtime'}:raise ValueError('环境身份不匹配')
    if not ENV.exists():
        venv.EnvBuilder(with_pip=True).create(ENV)
        files,dirs=environment_paths()
        write_environment_index({'app':'luxixi-workbench','schema':1,'files':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()},'directories':sorted(dirs)})
    index=read_environment_index();before,before_dirs=environment_paths()
    hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in before.items() if n in index['files']}
    try:
        subprocess.run([str(python_path()),'-B','-X','utf8','-m','pip','--isolated','--disable-pip-version-check','install','--quiet','--index-url','https://pypi.org/simple','-r',str(RUNTIME/'requirements.lock')],check=True)
        subprocess.run([str(python_path()),'-B','-X','utf8','-m','pip','check'],check=True,stdout=subprocess.DEVNULL)
    finally:
        after,after_dirs=environment_paths()
        for name,path in after.items():
            if name not in before or (name in index['files'] and hashes[name]==index['files'][name]):index['files'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
        index['directories']=sorted(set(index['directories'])|(after_dirs-before_dirs))
        write_environment_index(index)
    data=args.data_dir
    if not data:
        probe=subprocess.run([str(python_path()),'-X','utf8','-c','from luxixi_workbench.paths import data_path;print(data_path())'],cwd=RUNTIME,capture_output=True,text=True,encoding='utf-8',check=True)
        data=probe.stdout.strip()
    start_args=['start','--data-dir',data]
    if args.port is not None:start_args+=['--port',str(args.port)]
    result=execute('luxixi_workbench',start_args,capture=True)
    if result.returncode:raise ValueError(result.stderr.strip() or '服务未启动')
    status=execute('luxixi_workbench',['status','--data-dir',data],capture=True)
    if status.returncode:raise ValueError('启动后未能核验服务')
    print(json.dumps({'data_dir':str(Path(data).resolve()),'skill':'luxixi-workbench','service':json.loads(status.stdout),'google':'inspect_per_site_onboarding_status','schedule':'not_configured'},ensure_ascii=False))

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    try:
        if len(sys.argv)==2 and sys.argv[1] in {'-h','--help'}:
            print('用法：workbench.py setup [--data-dir PATH] [--port PORT] | onboard --data-dir PATH 子命令 | ticket/seo/cycle --data-dir PATH --db-id ID 子命令 | client detect/prepare/run-isolated | service start/status/stop --data-dir PATH。巡检见references/seo.md。');return 0
        if len(sys.argv)<2:raise ValueError('用法：workbench.py setup|onboard|service|ticket 后接参数')
        action=sys.argv[1]
        if action=='setup':setup(sys.argv[2:]);return 0
        if action not in {'onboard','service','ticket','client','seo','cycle'}:raise ValueError('只支持setup/onboard/service/ticket/client/seo/cycle')
        if not python_path().is_file():raise ValueError('尚未安装运行环境，请先setup')
        verify_runtime()
        return execute({'onboard':'luxixi_workbench.onboard_cli','ticket':'luxixi_workbench.ticket_cli','client':'luxixi_workbench.client_cli','seo':'luxixi_workbench.seo_cli','cycle':'luxixi_workbench.cycle_cli','service':'luxixi_workbench'}[action],sys.argv[2:]).returncode
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)[:500]},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
