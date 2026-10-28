"""Typed local commands; no webpage mutation or arbitrary command execution."""
import argparse
import json
from pathlib import Path
import sys
from .paths import owned_root
from .tickets import Tickets,prompt
from .skill_scan import linked

def read_json(path):
    p=Path(path).absolute()
    if any(linked(x) for x in [p,*p.parents]) or not p.is_file() or p.stat().st_size>65536:raise ValueError('输入JSON不存在/过大/经过链接')
    def unique(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('JSON字段重复')
            result[k]=v
        return result
    return json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=unique)

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='工单同库领取/验证/回写；不执行修复或发布')
    parser.add_argument('--data-dir',required=True);parser.add_argument('--db-id')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('identity');commands.add_parser('list')
    for name in ['show','prompt']:
        p=commands.add_parser(name);p.add_argument('--id',required=True)
    p=commands.add_parser('create');p.add_argument('--file',required=True)
    for name in ['revise','claim','reconcile','retry']:
        p=commands.add_parser(name);p.add_argument('--id',required=True);p.add_argument('--revision',required=True,type=int);p.add_argument('--hash',required=True)
        if name=='revise':p.add_argument('--file',required=True)
        if name=='claim':p.add_argument('--actor',required=True);p.add_argument('--operation-id',required=True)
        if name=='reconcile':p.add_argument('--receipt',required=True)
    for name in ['heartbeat','external-begin','report','recover','interrupt']:
        p=commands.add_parser(name);p.add_argument('--claim-file',required=True)
        if name=='report':p.add_argument('--receipt',required=True)
        if name=='recover':p.add_argument('--receipt-id',required=True)
        if name=='interrupt':p.add_argument('--reason',required=True)
    args=parser.parse_args()
    try:
        if args.command!='identity' and not args.db_id:raise ValueError('先identity取得本库身份，后续命令必须指定--db-id')
        source=Path(args.data_dir).expanduser().absolute()
        if any(linked(x) for x in [source,*source.parents]):raise ValueError('数据根不能经过链接/junction')
        flow=Tickets(owned_root(args.data_dir,create=False),db_id=args.db_id)
        if args.command=='identity':result={'database_id':flow.database_id,'data_dir':str(flow.root)}
        elif args.command=='list':result=flow.list()
        elif args.command=='show':result=flow.show(args.id)
        elif args.command=='prompt':result={'prompt':prompt(flow.show(args.id),flow.root),'copied_state_changed':False}
        elif args.command=='create':result=flow.create(read_json(args.file))
        elif args.command=='revise':result=flow.revise(args.id,args.revision,args.hash,read_json(args.file))
        elif args.command=='claim':result=flow.claim(args.id,args.revision,args.hash,args.actor,args.operation_id)
        elif args.command=='heartbeat':result=flow.heartbeat(args.claim_file)
        elif args.command=='external-begin':result=flow.external_begin(args.claim_file)
        elif args.command=='report':result=flow.report(args.claim_file,read_json(args.receipt))
        elif args.command=='recover':result=flow.recover(args.claim_file,args.receipt_id)
        elif args.command=='reconcile':result=flow.reconcile(args.id,args.revision,args.hash,read_json(args.receipt))
        elif args.command=='interrupt':result=flow.interrupt(args.claim_file,args.reason)
        else:result=flow.retry(args.id,args.revision,args.hash)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)[:240],'tool_executed_business_action':False,'existing_business_result':'not_inferred_from_command_error','next':'先show/recover或核对外部结果；勿重复业务动作'},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
