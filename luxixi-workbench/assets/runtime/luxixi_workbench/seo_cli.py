import argparse
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from .paths import owned_root
from .clients import safe_directory
from .seo import SEO

def read_import(flow,file):
    path=Path(file).absolute();relative=path.relative_to(flow.root.absolute())
    if not relative.parts or relative.parts[0]!='imports':raise ValueError('输入文件须在本数据根imports内')
    path=flow.flow.safe(relative)
    if not path.is_file() or path.stat().st_size>8*1024*1024:raise ValueError('输入文件不存在或超过8MiB')
    return json.loads(path.read_text(encoding='utf-8'))

def fixture_transport(value):
    if not isinstance(value,dict) or value.get('source')!='synthetic_http' or not isinstance(value.get('responses'),dict):raise ValueError('仅接受显式synthetic_http fixture')
    def fetch(url):
        row=value['responses'].get(url)
        if row is None:raise ValueError('本隔离fixture没有该地址')
        return {'source':'synthetic_http','status':row['status'],'headers':row.get('headers',{}),'body':base64.b64decode(row['body_base64'],validate=True)}
    return fetch

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='只读SEO巡检；复用同库，不执行优化/发布/排期')
    parser.add_argument('--data-dir',required=True);parser.add_argument('--db-id',required=True);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--id',required=True);p.add_argument('--start');p.add_argument('--end');p.add_argument('--gsc-resource');p.add_argument('--ga4-resource');p.add_argument('--ga4-timezone');p.add_argument('--url',action='append',default=[])
    p=sub.add_parser('receipt-template');p.add_argument('--plan',required=True)
    p=sub.add_parser('finish');p.add_argument('--plan',required=True);p.add_argument('--receipt',required=True);p.add_argument('--public-fixture')
    p=sub.add_parser('show');p.add_argument('--inspection',required=True)
    p=sub.add_parser('propose');p.add_argument('--inspection',required=True);p.add_argument('--finding',required=True)
    args=parser.parse_args()
    try:
        root=owned_root(safe_directory(args.data_dir),create=False);flow=SEO(root,args.db_id)
        if args.command=='prepare':result=flow.prepare(args.id,args.start,args.end,args.gsc_resource,args.ga4_resource,args.ga4_timezone,args.url)
        elif args.command=='receipt-template':
            plan,_=flow.read_plan(args.plan);result={k:plan[k] for k in ['inspection_id','database_id','project_id','challenge']};result.update(source='synthetic_mcp' if plan['synthetic'] else 'client_mcp',observed_at=datetime.now(timezone.utc).isoformat(),calls=[])
        elif args.command=='finish':
            plan,_=flow.read_plan(args.plan)
            if args.public_fixture and not plan['synthetic']:raise ValueError('真实站点不接受隔离fixture')
            result=flow.finish(args.plan,read_import(flow,args.receipt),fixture_transport(read_import(flow,args.public_fixture)) if args.public_fixture else None)
        elif args.command=='show':result=flow.report(args.inspection)
        else:result=flow.propose(args.inspection,args.finding)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:300],'website_changed':False,'schedule_created':False},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
