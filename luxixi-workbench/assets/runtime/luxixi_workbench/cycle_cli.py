"""Typed local protocol. Only the client's native tool can actually schedule work."""
import argparse
import json
import sys
from .paths import owned_root
from .clients import safe_directory
from .cycle import Cycle
from .seo_cli import read_import
from .effects import Effects
from .methods import Methods

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description='唯一原生任务绑定/巡检周期/效果/方法；本工具没有时钟或发布器')
    p.add_argument('--data-dir',required=True);p.add_argument('--db-id',required=True);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('plan');s.add_argument('--client',required=True);s.add_argument('--cadence',required=True);s.add_argument('--timezone',required=True)
    s=sub.add_parser('bind');s.add_argument('--receipt',required=True)
    s=sub.add_parser('site-state');s.add_argument('--id',required=True);s.add_argument('--state',required=True,choices=['enabled','paused'])
    s=sub.add_parser('begin');s.add_argument('--operation-id',required=True);s.add_argument('--trigger',choices=['manual','native'],default='manual');s.add_argument('--invocation')
    s=sub.add_parser('prepare-project');s.add_argument('--cycle',required=True);s.add_argument('--id',required=True);s.add_argument('--start');s.add_argument('--end');s.add_argument('--gsc-resource');s.add_argument('--ga4-resource');s.add_argument('--ga4-timezone')
    s=sub.add_parser('record-project');s.add_argument('--cycle',required=True);s.add_argument('--id',required=True);s.add_argument('--error')
    s=sub.add_parser('complete');s.add_argument('--cycle',required=True)
    s=sub.add_parser('show');s.add_argument('--cycle',required=True)
    s=sub.add_parser('research-result');s.add_argument('--receipt',required=True)
    s=sub.add_parser('effect-review');s.add_argument('--id',required=True);s.add_argument('--inspection',required=True)
    sub.add_parser('status')
    args=p.parse_args()
    try:
        root=owned_root(safe_directory(args.data_dir),create=False);c=Cycle(root,args.db_id)
        if args.command=='plan':result=c.plan(args.client,args.cadence,args.timezone)
        elif args.command=='bind':result=c.bind(read_import(c,args.receipt))
        elif args.command=='site-state':result=c.site_state(args.id,args.state)
        elif args.command=='begin':result=c.begin(args.operation_id,args.trigger,read_import(c,args.invocation) if args.invocation else None)
        elif args.command=='prepare-project':result=c.prepare_project(args.cycle,args.id,start=args.start,end=args.end,gsc=args.gsc_resource,ga4=args.ga4_resource,ga_timezone=args.ga4_timezone)
        elif args.command=='record-project':result=c.record_project(args.cycle,args.id,args.error)
        elif args.command=='complete':result=c.complete(args.cycle)
        elif args.command=='show':result=c.get(args.cycle)
        elif args.command=='research-result':result=Methods(root,args.db_id).record(read_import(c,args.receipt))
        elif args.command=='effect-review':result=Effects(root,args.db_id).review_project(args.id,args.inspection)
        else:result={'seo':c.flow.store.snapshot('seo')['schedule'],'research_due':Methods(root,args.db_id).due()}
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:400],'native_task_created':False,'website_changed':False},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
