import argparse
import json
from pathlib import Path
import sys
from .paths import owned_root
from .clients import Clients,detect,safe_directory

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Codex/Claude本机薄适配；原生试运行仅限标记的合成工作区')
    parser.add_argument('--data-dir');parser.add_argument('--db-id');commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('detect');p.add_argument('--client',choices=['codex','claude'],required=True)
    p=commands.add_parser('prepare');p.add_argument('--client',choices=['codex','claude'],required=True);p.add_argument('--workspace',required=True);p.add_argument('--id',required=True)
    p=commands.add_parser('run-isolated');p.add_argument('--plan',required=True);p.add_argument('--timeout',type=int,default=480)
    args=parser.parse_args()
    try:
        if args.command=='detect':result=detect(args.client)
        else:
            if not args.data_dir or not args.db_id:raise ValueError('必须提供同一data-dir与db-id')
            root=safe_directory(args.data_dir);flow=Clients(owned_root(root,create=False),args.db_id)
            result=flow.prepare(args.id,args.client,args.workspace) if args.command=='prepare' else flow.run_isolated(args.plan,args.timeout)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0 if args.command!='run-isolated' or result.get('status')=='verified_completion' else 1
    except Exception as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:240],'business_result':'not_inferred','safe_to_retry_business':False},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
