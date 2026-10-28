"""Small, bounded public sample; HTTP observations never prove Google indexing."""
from html.parser import HTMLParser
import hashlib
import re
import time
from urllib.parse import urlsplit,urljoin,unquote
from xml.etree import ElementTree
from .public_check import site_url,public_response

def scoped(site,url,root_resource=False):
    selected=urlsplit(site);parsed=urlsplit(url)
    # Reuse strict scheme/port/credentials/query/private-host validation, retaining path bytes.
    site_url(url)
    family={selected.hostname,selected.hostname.removeprefix('www.'),'www.'+selected.hostname.removeprefix('www.')}
    if parsed.hostname not in family:raise ValueError('地址越出本站/apex-www范围')
    def decoded(path):
        for _ in range(4):
            value=unquote(path,errors='strict')
            if value==path:break
            path=value
        else:raise ValueError('路径编码层级不明确')
        if any(ord(c)<32 for c in path) or any(c in path for c in '\\?#') or any(x in {'.','..'} for x in path.split('/')):raise ValueError('拒绝编码后的越界/不明确路径')
        return path
    target_path=decoded(parsed.path or '/');selected_path=decoded(selected.path or '/')
    if not root_resource and not target_path.startswith(selected_path):raise ValueError('地址越出所选站点路径')
    return url

class HTML(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.in_body=False;self.capture=None;self.titles=[];self.h1=[];self.canonical=[];self.description=[];self.robots=[];self.links=[];self.text=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='body':self.in_body=True
        if tag in {'script','style'}:self.depth+=1
        if tag in {'title','h1'}:self.capture=[tag,'']
        if tag=='meta' and a.get('name','').lower()=='description':self.description.append(a.get('content','')[:1000])
        if tag=='meta' and a.get('name','').lower() in {'robots','googlebot'}:self.robots.append(a.get('content','')[:500])
        if tag=='link' and 'canonical' in a.get('rel','').lower().split():self.canonical.append(a.get('href','')[:2048])
        if tag=='a' and a.get('href') and len(self.links)<100:self.links.append(a['href'][:2048])
    def handle_endtag(self,tag):
        if tag=='body':self.in_body=False
        if tag in {'script','style'}:self.depth=max(0,self.depth-1)
        if self.capture and tag==self.capture[0]:
            (self.titles if tag=='title' else self.h1).append(self.capture[1].strip()[:1000]);self.capture=None
    def handle_data(self,data):
        if self.capture:self.capture[1]=(self.capture[1]+data)[:2000]
        if self.in_body and not self.depth:self.text.append(data)

def inspect_public(site,urls=(),transport=None,synthetic=False):
    site=site_url(site);deadline=time.monotonic()+35;source='synthetic_http' if synthetic else 'public_http';cache={};findings=[]
    def fetch(url,root=False):
        if url in cache:return cache[url]
        if len(cache)>=12:raise ValueError('公开抽查最多12项')
        scoped(site,url,root);current=url;chain=[]
        try:
            for _ in range(4):
                if time.monotonic()>=deadline:raise TimeoutError('公开巡检35秒截止')
                response=transport(current) if transport else public_response(current,deadline=min(deadline,time.monotonic()+7))
                if response.get('source')!=source:raise ValueError('公开传输来源与合成标记不一致')
                body=response['body']
                if not isinstance(body,bytes) or len(body)>524288:raise ValueError('公开响应超过512KiB')
                headers={k.lower():v for k,v in response.get('headers',{}).items()};status=response['status']
                if type(status)!=int or not 100<=status<=599:raise ValueError('HTTP状态无效')
                chain.append({'url':current,'status':status})
                if status not in {301,302,303,307,308}:break
                current=scoped(site,urljoin(current,headers['location']),root)
            else:raise ValueError('公开重定向超过上限')
            result={'url':url,'observed_url':current,'http_status':status,'status':'ok' if 200<=status<300 else 'http_error','redirects':chain,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'content_type':headers.get('content-type',''),'x_robots':headers.get('x-robots-tag','')[:500]}
            if result['status']=='ok' and ('html' in result['content_type'] or b'<html' in body[:500].lower()):
                doc=HTML();doc.feed(body.decode('utf-8',errors='replace'))
                result.update(titles=doc.titles,h1=doc.h1,descriptions=doc.description,canonicals=[urljoin(current,x) if x.strip() else '' for x in doc.canonical],robots=doc.robots,html_text_characters=len(' '.join(doc.text).strip()),links=[])
                for link in doc.links:
                    try:
                        candidate=urljoin(current,link)
                        if '#' in candidate:continue
                        scoped(site,candidate)
                        if candidate not in result['links']:result['links'].append(candidate)
                    except (ValueError,UnicodeError):continue
            result['_body']=body
        except Exception as error:result={'url':url,'status':'read_failed','reason':type(error).__name__}
        cache[url]=result;return result
    def finding(code,url,title,detail):findings.append({'key':hashlib.sha256((code+'|'+url).encode()).hexdigest()[:20],'code':code,'url':url,'title':title,'detail':detail,'evidence_class':'observed'})
    home=fetch(site)
    origin=urlsplit(site);base=origin.scheme+'://'+origin.netloc
    robots=fetch(base+'/robots.txt',True);sitemap=fetch(base+'/sitemap.xml',True)
    if robots['status']=='ok':
        directives=[]
        for line in robots['_body'].decode('utf-8',errors='replace').splitlines():
            line=line.split('#',1)[0].strip()
            if ':' not in line:continue
            name,value=line.split(':',1)
            if name.lower().strip() in {'user-agent','allow','disallow','sitemap'}:directives.append({'name':name.strip().lower(),'value':value.strip()[:1000]})
            if len(directives)>=80:break
        robots['directives']=directives;robots['interpretation']='仅源指令观察，不是Google完整robots规则解释器'
        if any(x=={'name':'disallow','value':'/'} for x in directives):finding('robots_rule',base+'/robots.txt','核对robots整站Disallow规则','源文件包含Disallow: /；需核对适用爬虫、Allow规则和配置意图，不据此断言Google禁止抓取')
    sitemap_info={'status':sitemap['status'],'discovered_urls':None,'scope':'默认地图抽查，不代表本站全部地图/URL'}
    if sitemap['status']=='ok':
        try:
            body=sitemap['_body']
            if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():raise ValueError('拒绝XML实体/DTD')
            tree=ElementTree.fromstring(body)
            if tree.tag.split('}')[-1] not in {'urlset','sitemapindex'}:raise ValueError('地图根无效')
            sitemap_info.update(kind=tree.tag.split('}')[-1],discovered_urls=len(tree.findall('.//{*}loc')))
        except (ElementTree.ParseError,ValueError):sitemap_info['status']='invalid_xml'
    alternate=base.replace('://www.','://') if origin.hostname.startswith('www.') else origin.scheme+'://www.'+origin.netloc
    alternate_result=fetch(alternate+(origin.path or '/'))
    samples=list(dict.fromkeys([site,*urls,*home.get('links',[])[:3]]))[:6]
    for url in samples:
        row=fetch(url)
        if row['status']!='ok':
            if row.get('http_status',0)>=400:finding('http_error',url,'抽查页面返回HTTP错误','HTTP '+str(row['http_status'])+'；不等于Google已保存的抓取结果')
            continue
        if 'titles' not in row:
            finding('html_unavailable',url,'未取得可检查的完整HTML','本次静态响应无法检查页面元数据；不是强制SSR要求');continue
        if len(row['titles'])!=1 or not row['titles'][0]:finding('title',url,'检查页面标题','实际HTML标题缺失、为空或不唯一')
        if not any(row['descriptions']):finding('description',url,'检查页面描述','实际HTML未提供非空description；是否修改需结合页面用途判断')
        if len(row['canonicals'])!=1 or not row['canonicals'][0]:finding('canonical',url,'核对规范地址','本次HTML canonical缺失、为空或多值；不是未收录证明')
        elif urlsplit(row['canonicals'][0]).hostname not in {origin.hostname,origin.hostname.removeprefix('www.'),'www.'+origin.hostname.removeprefix('www.')}:
            finding('canonical_external',url,'核对跨站canonical','页面指向其他域名，需核实是否符合预期')
        if re.search(r'\bnoindex\b',' '.join(row['robots'])+' '+row['x_robots'],re.I):finding('noindex',url,'核对页面noindex','实际HTML或HTTP头含noindex；先确认是否有意设置，不能直接修改')
        if not row['h1']:finding('h1',url,'核对页面主标题','抽查HTML没有h1；这是页面结构观察，不是排名或收入结论')
        if not row['html_text_characters']:finding('html_body',url,'核对可读取的页面正文','本次原始HTML未读到正文；可用完整静态HTML或SSR，不强制某一种技术')
    if sitemap_info['status']!='ok':finding('sitemap',base+'/sitemap.xml','核对站点地图入口','默认sitemap读取状态 '+sitemap_info['status']+'；可能使用其他地址，先调查')
    if robots['status']!='ok':finding('robots',base+'/robots.txt','核对robots读取状态','本次robots读取状态 '+robots['status']+'，不据此断言Google禁止抓取')
    for row in cache.values():row.pop('_body',None)
    return {'source':source,'scope':'最多6个页面与robots/默认地图/apex-www的有限只读抽查；不执行JS，不代表全站、Google收录或优化效果','pages':list(cache.values()),'sitemap':sitemap_info,'apex_www':{'selected':site,'alternate':alternate_result,'scope':'只记录实际HTTP/重定向，不改规范域或DNS'},'findings':findings}
