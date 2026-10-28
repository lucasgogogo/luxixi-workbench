"""Only approved Skill directories, frontmatter metadata; no private bodies/config."""
from pathlib import Path
import hashlib
import re
import os

def linked(path):
    if path.is_symlink():return True
    if os.name=='nt':
        if hasattr(path,'is_junction'):return path.is_junction()
        try:return bool(path.lstat().st_file_attributes & 0x400)
        except FileNotFoundError:return False
    return False

def scan_metadata(roots):
    if len(roots)>10:raise ValueError('扫描目录过多')
    items=[]
    for value in roots:
        root=Path(value)
        if any(linked(p) for p in [root,*root.parents]) or not root.is_dir():raise ValueError('获准目录不存在或经过链接/junction')
        candidates=[root/'SKILL.md']+[p/'SKILL.md' for p in root.iterdir() if p.is_dir() and not linked(p) and not p.name.startswith('.')]
        for file in candidates:
            if not file.is_file() or linked(file) or not file.resolve().is_relative_to(root.resolve()):continue
            if len(items)>=200:raise ValueError('扫描最多200个Skill，请缩小范围')
            with file.open('rb') as stream:
                if stream.readline(257).strip()!=b'---':continue
                lines=[];size=0
                for _ in range(80):
                    line=stream.readline(2049);size+=len(line)
                    if size>16384:raise ValueError('Skill元数据过大')
                    if line.strip()==b'---':break
                    lines.append(line.decode('utf-8',errors='replace'))
                else:continue
            fields={}
            for index,line in enumerate(lines):
                match=re.match(r'^(name|description|version):\s*[\'"]?(.*?)[\'"]?\s*$',line)
                if match:
                    value=match[2]
                    if value in {'>','|','>-','|-','>+','|+'}:
                        block=[]
                        for continuation in lines[index+1:]:
                            if continuation.strip() and not continuation[0].isspace():break
                            block.append(continuation.strip())
                        value=('\n' if value.startswith('|') else ' ').join(block)
                    fields[match[1]]=value[:500]
                if line.strip()=='metadata:':
                    for continuation in lines[index+1:]:
                        if continuation.strip() and not continuation[0].isspace():break
                        version=re.match(r'^\s+version:\s*[\'"]?(.*?)[\'"]?\s*$',continuation)
                        if version:fields['version']=version[1][:80]
            name=fields.get('name',file.parent.name)
            items.append({'id':hashlib.sha256(str(file.resolve()).encode()).hexdigest()[:20],'name':name,'title':name,'summary':fields.get('description','用途未提供'),'category':'tools','source':'用户允许的Skill目录','package':'','enabled':None,'capability':'已发现元数据；加载、依赖和权限未核验','version':fields.get('version','未提供')})
    return items
