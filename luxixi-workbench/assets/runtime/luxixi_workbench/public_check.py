"""Bounded public reads. No proxy, browser execution, private IPs or DNS changes."""
from html.parser import HTMLParser
import hashlib
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

def site_url(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2048:
        raise ValueError('请提供网站地址')
    value=value.strip()
    if '://' not in value:value='https://'+value
    parsed=urlsplit(value)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('网站地址仅支持不含登录信息/查询/片段的HTTP或HTTPS地址')
    host=parsed.hostname.rstrip('.').encode('idna').decode('ascii').lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:
        raise ValueError('仅接入公开网站，不接入本机或内网站点')
    try:
        if not ipaddress.ip_address(host).is_global:raise ValueError('不允许私有IP')
    except ValueError as error:
        if '不允许' in str(error):raise
    if parsed.port not in (None,80 if parsed.scheme=='http' else 443):
        raise ValueError('网站只允许标准HTTP/HTTPS端口')
    path=parsed.path or '/'
    if any(ord(c)<32 for c in value) or '\\' in value or any(p in {'.','..'} for p in path.split('/')):
        raise ValueError('网站路径无效')
    return urlunsplit((parsed.scheme,host,path.rstrip('/')+'/' if path!='/' else '/', '', ''))

class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.in_title=False;self.title='';self.description='';self.canonical='';self.robots=''
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='meta' and a.get('name','').lower()=='description':self.description=a.get('content','')[:500]
        if tag=='meta' and a.get('name','').lower()=='robots':self.robots=a.get('content','')[:200]
        if tag=='link' and a.get('rel','').lower()=='canonical':self.canonical=a.get('href','')[:2048]
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title=(self.title+data)[:200]

def public_response(url,deadline=None):
    deadline=deadline or time.monotonic()+8
    def remaining():
        left=deadline-time.monotonic()
        if left<=0:raise TimeoutError('公开读取已到截止时间')
        return left
    parsed=urlsplit(url);host=parsed.hostname
    resolved=[];failed=[];done=threading.Event()
    def resolve():
        try:resolved.extend(socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM))
        except Exception as error:failed.append(error)
        finally:done.set()
    threading.Thread(target=resolve,daemon=True).start()
    if not done.wait(remaining()):raise TimeoutError('DNS读取超时')
    if failed:raise ValueError('DNS读取失败')
    addresses={r[4][0] for r in resolved}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('DNS包含非公开地址，停止读取')
    address=sorted(addresses)[0];port=443 if parsed.scheme=='https' else 80
    if parsed.scheme=='https':
        class PinnedHTTPS(http.client.HTTPSConnection):
            def connect(self):
                raw=socket.create_connection((address,port),timeout=remaining())
                try:
                    raw.settimeout(remaining());self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=host)
                except BaseException:raw.close();raise
        connection=PinnedHTTPS(host,port,timeout=remaining())
    else:connection=http.client.HTTPConnection(address,port,timeout=remaining())
    timer=None
    try:
        connection.connect();raw_socket=connection.sock
        def abort_read():
            try:raw_socket.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        timer=threading.Timer(remaining(),abort_read);timer.daemon=True;timer.start()
        connection.request('GET',urlunsplit(('','',parsed.path or '/',parsed.query,'')),headers={'Host':host,'User-Agent':'LuxixiWorkbench/0.2 read-only initial-check','Accept-Encoding':'identity'})
        response=connection.getresponse();body=response.read(524289)
        remaining()
        if len(body)>524288:raise ValueError('公开响应超过512KiB上限')
        length=response.getheader('Content-Length')
        if length is not None and int(length)!=len(body):raise ValueError('公开响应未完整返回')
        return {'status':response.status,'headers':dict(response.getheaders()),'body':body,'source':'public_http'}
    finally:
        if timer:timer.cancel()
        connection.close()

def initial_check(site,transport=None):
    site=site_url(site);parsed=urlsplit(site);overall=time.monotonic()+20
    transport=transport or (lambda url:public_response(url,deadline=min(overall,time.monotonic()+8)))
    results=[];source='public_http'
    for label,url in [('homepage',site),('robots',urljoin(site,'/robots.txt')),('sitemap',urljoin(site,'/sitemap.xml'))]:
        current=url
        try:
            for _ in range(4):
                if time.monotonic()>=overall:raise TimeoutError('初检总时长达到20秒上限')
                response=transport(current);source=response.get('source','public_http')
                if response['status'] not in {301,302,303,307,308}:break
                location=next((v for k,v in response.get('headers',{}).items() if k.lower()=='location'),None)
                if not location:raise ValueError('重定向缺少地址')
                candidate=urljoin(current,location);target=urlsplit(candidate)
                site_url(candidate)
                if target.hostname not in {parsed.hostname,'www.'+parsed.hostname,parsed.hostname.removeprefix('www.')}:
                    raise ValueError('重定向超出本站范围')
                current=candidate
            else:raise ValueError('重定向超过上限')
            body=response['body'];item={'kind':label,'url':url,'observed_url':current,'http_status':response['status'],'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'status':'ok' if 200<=response['status']<300 else 'http_error'}
            if label=='homepage' and item['status']=='ok':
                doc=Document();doc.feed(body.decode('utf-8',errors='replace'))
                item.update(title=doc.title.strip(),description=doc.description,canonical=doc.canonical,robots=doc.robots)
            results.append(item)
        except Exception as error:
            results.append({'kind':label,'url':url,'status':'read_failed','reason':type(error).__name__})
    return {'source':source,'scope':'仅首页、robots.txt与默认sitemap.xml三项只读抽查；不是全站/收录证明','results':results}
