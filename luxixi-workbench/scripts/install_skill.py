"""Project-scoped native Skill installation. No global configuration writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import uuid

NAME='luxixi-workbench'

def promote(stage,target,manifest,fingerprint):
    for attempt in range(4):
        if target.exists() or linked(target):raise ValueError('目标在安装期间已出现，不覆盖')
        if any(linked(p) for p in [stage,*stage.parents]):raise ValueError('暂存目录路径已变化，不重试')
        expected={x['path'] for x in manifest['files']}|{'bundle-manifest.json','installation.json'}
        actual=set()
        for path in stage.rglob('*'):
            if linked(path) or not path.resolve().is_relative_to(stage.resolve()):raise ValueError('暂存树含链接/junction或越界')
            if path.is_file():actual.add(path.relative_to(stage).as_posix())
        if actual!=expected:raise ValueError('暂存文件白名单不一致')
        if json.loads((stage/'installation.json').read_text(encoding='utf-8'))!={'skill':NAME,'manifest':fingerprint}:raise ValueError('暂存身份不匹配')
        if hashlib.sha256((stage/'bundle-manifest.json').read_bytes()).hexdigest()!=fingerprint:raise ValueError('暂存manifest已变化')
        for item in manifest['files']:
            file=stage/item['path']
            if any(linked(p) for p in [file,*file.parents]) or not file.resolve().is_relative_to(stage.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('暂存内容已变化，不重试')
        try:
            os.rename(stage,target)
            return attempt
        except OSError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in {5,32} or attempt==3:raise
            time.sleep((.15,.4,1.0)[attempt])

def linked(path):
    if path.is_symlink():return True
    try:return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name=='nt' else False
    except FileNotFoundError:return False

def source_root():
    here=Path(__file__).resolve()
    return here.parents[1] if here.parent.name=='scripts' else here.parent/'skills'/NAME

def install(workspace,client,source=None,dry_run=False):
    source=Path(source or source_root())
    manifest=json.loads((source/'bundle-manifest.json').read_text(encoding='utf-8'))
    fingerprint=hashlib.sha256((source/'bundle-manifest.json').read_bytes()).hexdigest()
    workspace=Path(workspace).expanduser()
    if not workspace.is_absolute():raise ValueError('工作区必须使用绝对路径')
    if any(linked(p) for p in [workspace,*workspace.parents]):raise ValueError('工作区及祖先目录不能是链接/junction')
    workspace=workspace.resolve()
    if not workspace.is_dir():raise ValueError('先选择已存在的工作区')
    clients=['codex','claude'] if client=='both' else [client]
    if any(c not in {'codex','claude'} for c in clients):raise ValueError('客户端无效')
    for item in manifest['files']:
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('包路径越界')
        file=source/relative
        if file.is_symlink() or not file.resolve().is_relative_to(source.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Skill包文件摘要不匹配')
    results=[]
    for choice in clients:
        parent=workspace/('.agents' if choice=='codex' else '.claude')/'skills'
        for ancestor in [parent.parent,parent]:
            if linked(ancestor):raise ValueError('目标父目录不能是链接')
        target=parent/NAME
        if target.exists():
            marker=target/'installation.json'
            if linked(target) or not marker.is_file() or linked(marker):raise ValueError('同名Skill不是本包安装，不覆盖')
            identity=json.loads(marker.read_text(encoding='utf-8'))
            if identity!={'skill':NAME,'manifest':fingerprint}:raise ValueError('已有Skill版本不同，不静默覆盖')
            for item in manifest['files']:
                file=target/item['path']
                if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('已有Skill被修改，不覆盖')
            results.append({'client':choice,'path':str(target),'status':'already_installed'});continue
        if dry_run:
            results.append({'client':choice,'path':str(target),'status':'planned'});continue
        parent.mkdir(parents=True,exist_ok=True)
        stage=parent/('.luxixi-stage-'+uuid.uuid4().hex)
        stage.mkdir()
        for item in manifest['files']:
            destination=stage/item['path'];destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/item['path'],destination)
        shutil.copy2(source/'bundle-manifest.json',stage/'bundle-manifest.json')
        (stage/'installation.json').write_text(json.dumps({'skill':NAME,'manifest':fingerprint}),encoding='utf-8')
        retries=promote(stage,target,manifest,fingerprint)
        results.append({'client':choice,'path':str(target),'status':'installed','rename_retries':retries})
    return results

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='把工作台Skill安装到指定工作区；不改用户级Skill/MCP配置')
    parser.add_argument('--workspace',required=True);parser.add_argument('--client',choices=['codex','claude','both'],required=True);parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(install(args.workspace,args.client,dry_run=args.dry_run),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
