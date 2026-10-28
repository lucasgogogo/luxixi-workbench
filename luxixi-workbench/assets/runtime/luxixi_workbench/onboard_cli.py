import argparse
import json
import platform
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .paths import owned_root
from .onboarding import Onboarding

def doctor(client):
    executable=shutil.which('codex' if client=='codex' else ('claude.cmd' if os.name=='nt' else 'claude'))
    version='未发现命令入口'
    if executable:
        result=subprocess.run([executable,'--version'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10,shell=False)
        version=(result.stdout.strip()[:120] if result.returncode==0 else '版本读取失败')
    return {'system':platform.system(),'python':platform.python_version(),'client':client,'version':version,'helper_local_execution':True,'skill_loaded':'requires_client_confirmation','native_schedule':'not_configured','google':'requires_native_client_mcp','model_api_key_required':False}

def main():
    parser=argparse.ArgumentParser(description='在AI聊天中建立自己的工作台接入记录；不读凭据、不配置SEO时钟')
    parser.add_argument('--data-dir',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('doctor');p.add_argument('--client',choices=['codex','claude'],required=True)
    p=commands.add_parser('begin');p.add_argument('--site',required=True);p.add_argument('--name',default='');p.add_argument('--goal',default='');p.add_argument('--client',choices=['codex','claude'],required=True);p.add_argument('--synthetic',action='store_true')
    for name in ['status','cancel','resume','scan','check']:
        p=commands.add_parser(name);p.add_argument('--id',required=True)
    p=commands.add_parser('configure');p.add_argument('--id',required=True);p.add_argument('--goal');p.add_argument('--name');p.add_argument('--timezone');p.add_argument('--allow-skill-dir',action='append',default=None)
    p=commands.add_parser('google-result');p.add_argument('--id',required=True);p.add_argument('--receipt',required=True)
    args=parser.parse_args()
    try:
        if args.command=='doctor':result=doctor(args.client)
        else:
            root=owned_root(args.data_dir,create=True);flow=Onboarding(root)
            if args.command=='begin':result=flow.begin(args.site,args.name,args.goal,args.client,args.synthetic)
            elif args.command=='status':result=flow.get(args.id)
            elif args.command=='configure':result=flow.configure(args.id,args.goal,args.name,args.timezone,args.allow_skill_dir)
            elif args.command in {'cancel','resume'}:result=flow.phase(args.id,cancel=args.command=='cancel')
            elif args.command=='scan':result=flow.scan(args.id)
            elif args.command=='check':result=flow.check(args.id)
            else:
                path=Path(args.receipt)
                if path.is_symlink() or not path.is_file() or path.stat().st_size>262144:raise ValueError('回执文件不存在/过大/符号链接')
                result=flow.google(args.id,json.loads(path.read_text(encoding='utf-8')))
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:240]},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
