import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler, Request, HTTPRedirectHandler
from . import APP_ID
from .paths import owned_root, service_port

def read_runtime(root):
    try:
        value=json.loads((root/'runtime.json').read_text(encoding='utf-8'))
        if (isinstance(value,dict) and value.get('app') == APP_ID
                and isinstance(value.get('port'),int) and 1024 <= value['port'] <= 65535
                and isinstance(value.get('instance'),str) and len(value['instance']) == 32
                and isinstance(value.get('token'),str) and len(value['token']) >= 32
                and isinstance(value.get('pid'),int) and value['pid'] > 0):
            return value
    except (OSError, ValueError):
        pass
    return None

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def request_local(runtime, stop=False):
    url=f"http://127.0.0.1:{runtime['port']}" + ('/_control/stop' if stop else '/health')
    request=Request(url, method='POST' if stop else 'GET')
    if stop:
        request.add_header('Authorization','Bearer '+runtime['token'])
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=2) as response:
        return json.load(response)

def status(root):
    runtime=read_runtime(root)
    if runtime:
        try:
            reply=request_local(runtime)
            if isinstance(reply,dict) and reply.get('app') == APP_ID and reply.get('instance') == runtime['instance']:
                return runtime
        except (OSError, ValueError):
            pass
    return None

def main():
    parser=argparse.ArgumentParser(description='撸西西的本地工作台：只监听127.0.0.1，不配置SEO时钟')
    parser.add_argument('command', choices=['start','status','stop','run'])
    parser.add_argument('--data-dir')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    try:
        root=owned_root(args.data_dir,create=args.command in {'start','run'})
        if args.command=='run':
            from .server import serve
            serve(str(root),service_port(root,args.port))
            return 0
        current=status(root)
        if args.command=='status':
            print(json.dumps({'running':bool(current),'url':f"http://127.0.0.1:{current['port']}/" if current else None},ensure_ascii=False))
            return 0 if current else 1
        if args.command=='stop':
            if not current:
                print('没有匹配的本工作台实例；未停止任何进程。')
                return 0
            request_local(current,stop=True)
            for _ in range(50):
                if not status(root):
                    print('本工作台已停止，数据库保留。')
                    return 0
                time.sleep(.1)
            raise RuntimeError('停止尚未确认；未强杀进程')
        if current:
            print(f"工作台已运行：http://127.0.0.1:{current['port']}/")
            return 0
        port=service_port(root,args.port)
        command=[sys.executable,'-X','utf8','-B','-m','luxixi_workbench','run','--data-dir',str(root),'--port',str(port)]
        # DETACHED_PROCESS would make Windows ignore CREATE_NO_WINDOW.
        options={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
        with (root/'service.log').open('ab') as log:
            child=subprocess.Popen(command,cwd=str(Path(__file__).resolve().parent.parent),stdin=subprocess.DEVNULL,stdout=log,stderr=log,**options)
        for _ in range(100):
            current=status(root)
            if current:
                print(f"工作台已启动：http://127.0.0.1:{current['port']}/")
                return 0
            if child.poll() is not None:
                raise RuntimeError('启动失败，检查独立数据目录中的service.log；未接管其他服务')
            time.sleep(.1)
        raise RuntimeError('启动未能确认；请用同一数据目录检查status，未启动第二实例')
    except (ValueError,OSError,RuntimeError) as error:
        print(str(error),file=sys.stderr)
        return 1
