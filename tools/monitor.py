#!/usr/bin/env python3
"""Public TrustMRR snapshots; local-only. No scheduler, login or external writes."""
import argparse,copy,fcntl,hashlib,json,os,re,shutil,sys,tempfile,time,uuid,zipfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo
import requests
from formats import parse,parse_profile,parse_recent,directory_record,initial
from redaction import scrub,redact_text,sensitive

ROOT=Path(__file__).absolute().parent
TZ=ZoneInfo('Asia/Shanghai')
def now():return datetime.now(timezone.utc).isoformat()
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))if s else None
def localday(s=None):return(dt(s)if s else datetime.now(timezone.utc)).astimezone(TZ).date().isoformat()
def load(p,default=None):return json.loads(Path(p).read_text())if Path(p).exists()else copy.deepcopy(default)
def atomic_bytes(path,body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb')as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def save(p,obj):atomic_bytes(p,json.dumps(obj,ensure_ascii=False,indent=2).encode())
def append_jsonl(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a')as f:f.write(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
def link_atomic(target,dest):
    dest=Path(dest);tmp=dest.parent/('.'+dest.name+'.'+uuid.uuid4().hex)
    os.symlink(os.path.relpath(target,dest.parent),tmp);os.replace(tmp,dest)
class Locked(Exception):pass
class FetchError(Exception):pass
class Blocked(FetchError):pass
class RunLock:
    def __init__(self,root):self.path=Path(root)/'.run.lock';self.f=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.f=self.path.open('a+')
        try:fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.f.close();raise Locked('Another monitor process owns the lock; no requests or writes performed')
        self.f.seek(0);self.f.truncate();self.f.write(str(os.getpid()));self.f.flush();return self
    def __exit__(self,*args):fcntl.flock(self.f,fcntl.LOCK_UN);self.f.close()

def semantic_hash(projects):
    """Fact version, not a byte checksum: ignore fetch times/pagination/provider-sync-only updates."""
    fields=['name','website_url','core_function_original','founded_date','launch_date','target_customers_original','pricing_original','distribution_channels_original','tech_stack_original','value_proposition_original','problem_solved_original','country','payment_verification_provider']
    def ms(metrics):return{k:{f:v.get(f)for f in['amount','currency','display','precision']}for k,v in sorted(metrics.items())if isinstance(v,dict)}
    h=hashlib.sha256()
    for x in sorted(projects,key=lambda p:p['slug']):
        view={k:x.get(k)for k in fields};view['slug']=x['slug'];view['metrics']=ms(x.get('metrics',{}));view['directory_metrics']=ms((x.get('directory_snapshot')or{}).get('metrics',{}));view['categories']=sorted((c.get('name'),c.get('url'))for c in x.get('source_categories',[]))
        h.update(json.dumps(view,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    return h.hexdigest()
def group(m):
    p=(m or{}).get('precision','unknown')
    return p  # Directory rounded, recent rounded, profile snapshots and JSON-LD never cross-compare.
def obskey(slug,key,g):return slug+'|'+key+'|'+g

def seed_observations(projects):
    ob={};positive={}
    for x in projects:
        channels=[x.get('metrics',{}),(x.get('directory_snapshot')or{}).get('metrics',{})]
        for metrics in channels:
            for key,m in metrics.items():
                if not isinstance(m,dict)or m.get('amount')is None:continue
                if x.get('metric_label_conflict')and metrics is channels[-1]and key in['revenue_30d','revenue_total']:continue
                ob[obskey(x['slug'],key,group(m))]=copy.deepcopy(m)
                if key in['mrr','revenue_30d','revenue_total']and m['amount']>0:positive[x['slug']+'|'+key]=True
    return ob,positive

def compare_metric(slug,key,old,new,positive_seen,at):
    if not isinstance(new,dict)or new.get('amount')is None:return []
    if old is None:return [] # Missing->positive / new precision channel is not 0->positive.
    if not old.get('currency')or not new.get('currency')or group(old)=='unknown'or old.get('currency')!=new.get('currency')or group(old)!=group(new):return []
    a=old.get('amount');b=new.get('amount')
    if a is None or a==b:return []
    if old.get('synced_at')and new.get('synced_at')and dt(new['synced_at'])<=dt(old['synced_at']):
        return[{'type':'source_revision_noncomparable','slug':slug,'metric':key,'before':a,'after':b,'at':at,'material':False,'note':'Provider sync time did not advance; not counted as growth.'}]
    e={'slug':slug,'metric':key,'before':a,'after':b,'currency':new.get('currency'),'at':at,'source_url':new.get('source_url'),'before_read_at':old.get('read_at'),'after_read_at':new.get('read_at'),'precision':group(new),'material':False}
    if key=='revenue_unspecified':return[]
    rounded='rounded'in group(new)
    e['type']='display_change'if rounded else'metric_increase'if b>a else'metric_decrease'
    e['delta']=b-a
    if not rounded and a!=0:e['relative_change']=(b-a)/abs(a)
    e['note']='Public display changed; may reflect rounding, not confirmed economic growth.'if rounded else'Same-metric, same-source-precision published snapshot changed; not a profit/customer-count claim.'
    if key=='revenue_30d'and b<a:e['note']+=' Rolling-window decline does NOT prove churn.'
    if key=='revenue_total'and b<a:e['note']+=' Refunds/source corrections are possible.'
    if not rounded and b>a and b-a>=10 and (a==0 or(b-a)/abs(a)>=0.10):e['material']=True
    events=[e];pk=slug+'|'+key
    if key in['mrr','revenue_30d','revenue_total']and a==0 and b>0 and not positive_seen.get(pk):
        events.append({**e,'type':'first_observed_positive','material':True,'note':'First observed positive value after a comparable observed zero; NOT proof of the actual first sale or product launch.'})
    return events

def observe(state,project,at):
    events=[];slug=project['slug']
    for key,m in project.get('metrics',{}).items():
        if not isinstance(m,dict)or m.get('amount')is None:continue
        k=obskey(slug,key,group(m));old=state['observations'].get(k)
        if old and old.get('synced_at')and m.get('synced_at')and dt(m['synced_at'])<dt(old['synced_at']):continue
        events+=compare_metric(slug,key,old,m,state['positive_seen'],at)
        state['observations'][k]=copy.deepcopy(m)
        if key in['mrr','revenue_30d','revenue_total']and m['amount']>0:state['positive_seen'][slug+'|'+key]=True
    return events

def merge_project(old,incoming):
    incoming=scrub(incoming)
    if old is None:
        result=copy.deepcopy(incoming);result.pop('_next_refresh_at',None);return result
    out=copy.deepcopy(old);is_profile=incoming.get('profile_read',False);is_dir=incoming.get('directory_present',False)
    if is_dir:out['directory_snapshot']=copy.deepcopy(incoming['directory_snapshot']);out['directory_present']=True;out['directory_page']=incoming.get('directory_page')
    for k,v in incoming.items():
        if k in['metrics','sources','directory_snapshot','directory_present','id','launch_date','launch_evidence','official_deep_check','replication_cost','analysis','missing_fields','_next_refresh_at']:continue
        if v is None or v==[]:continue
        if not is_profile and old.get('profile_read')and k in['name','core_function_original','core_function_precision','core_function_source_url','core_function_read_at','source_url','read_at','profile_read']:continue
        if k=='source_categories':
            seen={(c['name'],c.get('url'))for c in out.get(k,[])};out.setdefault(k,[]).extend(c for c in v if(c['name'],c.get('url'))not in seen);continue
        if k=='profile_read':out[k]=bool(old.get(k)or v)
        else:out[k]=copy.deepcopy(v)
    for key,m in incoming.get('metrics',{}).items():
        if not isinstance(m,dict)or m.get('amount')is None:continue
        prev=out.setdefault('metrics',{}).get(key)
        if prev and prev.get('synced_at')and m.get('synced_at')and dt(m['synced_at'])<dt(prev['synced_at']):continue
        if prev and group(prev)=='public_profile_published_snapshot'and not is_profile:continue
        if old.get('metric_label_conflict')and key in['revenue_30d','revenue_total']:continue
        out['metrics'][key]=copy.deepcopy(m)
    sources={(s.get('source_kind'),s.get('source_url')):s for s in out.get('sources',[])}
    for s in incoming.get('sources',[]):
        kind=s.get('source_kind');url=s.get('source_url')
        # Keep latest directory provenance, not an ever-growing history of pagination URLs.
        if kind=='public_directory_page':sources={k:v for k,v in sources.items()if k[0]!=kind}
        sources[(kind,url)]=s
    out['sources']=list(sources.values());return out

class PublicClient:
    def __init__(self,root,state,config):self.root=Path(root);self.state=state;self.config=config;self.last=0.0;self.requests=0;self.cache_hits=0;self.session=requests.Session();self.session.headers['User-Agent']='TrustMRR-public-monitor/1.0';self.robots=None
    def fail(self,url,message,status=None):
        append_jsonl(self.root/'logs/failures.jsonl',{'at':now(),'source_url':url,'status':status,'message':message});raise FetchError(message)
    def get(self,url,ttl_hours,validator=None):
        parsed=urlparse(url)
        if parsed.scheme!='https'or parsed.netloc!='trustmrr.com'or not re.fullmatch(r'/(?:robots\.txt|recent|startups(?:/page/\d+)?|startup/[a-zA-Z0-9_%\-]+\.md)',parsed.path):raise FetchError('Only allowlisted normal public TrustMRR URLs are permitted')
        if self.state.get('manual_review_required'):raise Blocked('Prior challenge/403 requires manual review; no network request')
        if self.state.get('not_before')and dt(self.state['not_before'])>datetime.now(timezone.utc):raise Blocked('Rate-limit backoff is still active; no network request')
        if self.robots and not self.robots.can_fetch(self.session.headers['User-Agent'],url):raise Blocked('robots.txt disallows this path')
        cache=self.state.setdefault('url_cache',{});old=cache.get(url);bodypath=self.root/old['body_file']if old else None
        if old and bodypath.is_file():
            due=dt(old['validated_at'])+timedelta(hours=ttl_hours)
            if old.get('public_next_refresh_at'):due=max(due,dt(old['public_next_refresh_at']))
            if datetime.now(timezone.utc)<due:
                self.cache_hits+=1;return bodypath.read_text(),old['body_read_at']
        headers={}
        if old and bodypath.is_file():
            if old.get('etag'):headers['If-None-Match']=old['etag']
            if old.get('last_modified'):headers['If-Modified-Since']=old['last_modified']
        for attempt in range(2):
            delay=self.config['request_interval_seconds']-(time.monotonic()-self.last)
            if delay>0:time.sleep(delay)
            self.last=time.monotonic();self.requests+=1
            try:r=self.session.get(url,headers=headers,timeout=self.config['request_timeout_seconds'],allow_redirects=False)
            except requests.RequestException as e:
                if attempt==0:time.sleep(3);continue
                self.fail(url,str(e))
            at=now();challenge=any(s in r.text.lower()for s in['just a moment...','verify you are human','cf-chl-','captcha-container'])
            if r.status_code in[403,429]or challenge:
                hours=self.config['rate_limit_backoff_hours'];retry=r.headers.get('Retry-After','')
                try:seconds=max(hours*3600,int(retry))
                except ValueError:seconds=hours*3600
                self.state['not_before']=(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat()
                self.state['manual_review_required']=r.status_code==403 or challenge
                append_jsonl(self.root/'logs/failures.jsonl',{'at':at,'source_url':url,'status':r.status_code,'message':'Stopped all requests: denial/rate limit/challenge; no alternate route'})
                raise Blocked('Stopped on challenge/403/429; no retry or alternate endpoint')
            if r.status_code==304:
                if not old or not bodypath.is_file():self.fail(url,'304 without a cached validated body',304)
                old['validated_at']=at;self.cache_hits+=1;return bodypath.read_text(),old['body_read_at']
            if r.status_code>=500 and attempt==0:time.sleep(3);continue
            if r.status_code!=200:self.fail(url,'Non-200 public response; old data preserved',r.status_code)
            if not r.text.strip():self.fail(url,'Empty response; old data/cache preserved',200)
            if validator:
                try:validator(r.text)
                except Exception as e:self.fail(url,'Parser rejected response: '+str(e),200)
            file='cache/'+hashlib.sha256(url.encode()).hexdigest()+'.txt';atomic_bytes(self.root/file,r.text.encode())
            m=re.search(r'next refresh expected around\s+([0-9TZ:.+\-]+)',r.text)
            cache[url]={'body_file':file,'body_read_at':at,'validated_at':at,'etag':r.headers.get('ETag'),'last_modified':r.headers.get('Last-Modified'),'public_next_refresh_at':m.group(1).rstrip('.')if m else None}
            return r.text,at
        self.fail(url,'Retry budget exhausted')
    def check_robots(self):
        body,_=self.get('https://trustmrr.com/robots.txt',self.config['robots_min_interval_hours']);rp=RobotFileParser();rp.parse(body.splitlines());self.robots=rp


def serialize_metric(m):return(m.get('display')or str(m.get('amount')))if isinstance(m,dict)else'未知'
def copy_link(src,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(src,dest)
    except OSError:shutil.copy2(src,dest)
def export_snapshot(root,projects,metadata,events,library,baseline=False):
    root=Path(root);projects=scrub(projects);version=semantic_hash(projects);at=now();runid=datetime.now(TZ).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    parent=root/'snapshots'/localday();parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.building-',dir=parent));final=parent/(runid+'-'+version[:12])
    try:
        metadata={**metadata,'total_exported_projects':len(projects),'created_at':at,'semantic_version_sha256':version,'version_scope':'Relevant project facts, not request times, pagination order or provider-sync-only changes. Byte checksums are separate.','public_profiles_read_and_parsed':sum(bool(p.get('profile_read'))for p in projects),'official_deep_verified_from_prior_cache':sum(bool(p.get('official_deep_check'))for p in projects),'initial_baseline_no_comparable_history':baseline,'verification_level_counts':{k:sum(p.get('verification_level')==k for p in projects)for k in['O','P','D','R','N']}}
        read_times=[v.get('read_at')for p in projects for v in p.get('sources',[])if v.get('read_at')]
        if read_times:metadata['read_at_utc_range']=[min(read_times,key=dt),max(read_times,key=dt)]
        save(stage/'metadata.json',metadata);save(stage/'changes.json',{'at':at,'baseline_no_history':baseline,'events':events})
        with(stage/'projects.json').open('w')as f:
            f.write('{"metadata":');json.dump(metadata,f,ensure_ascii=False);f.write(',"projects":[')
            for i,p in enumerate(projects):
                if i:f.write(',\n')
                json.dump(p,f,ensure_ascii=False,separators=(',',':'))
            f.write(']}\n')
        with(stage/'projects.jsonl').open('w')as f:
            for p in projects:f.write(json.dumps(p,ensure_ascii=False,separators=(',',':'))+'\n')
        def esc(s):return str(s or'未知').replace('|','\\|').replace('\n',' ')
        index=[]
        for start in range(0,len(projects),250):
            sub=projects[start:start+250];name=f'markdown/projects-{start//250+1:03d}.md';index.append(name)
            lines=[f'# 项目 {start+1}–{start+len(sub)} / {len(projects)}','无预筛；美元展示值可能舍入；P=已读档案，O=另有既存官网正文，D=目录，R=推荐。收入不是利润；未知不等于0。','|slug / 项目|功能原文|原站类别|MRR / 30天 / 累计|来源|','|---|---|---|---|---|']
            for p in sub:
                desc=p.get('core_function_original')or'未知';desc=desc[:400]+('…〔全文见JSON〕'if len(desc)>400 else'');cats='/'.join(dict.fromkeys(c['name']for c in p.get('source_categories',[])))or'未知';ms=p.get('metrics',{});rev=' / '.join(serialize_metric(ms.get(k))for k in['mrr','revenue_30d','revenue_total']);urls=f'[TrustMRR]({p["trustmrr_url"]})'+(f' [官网]({p["website_url"]})'if p.get('website_url')else'')
                lines.append(f'|{p["slug"]} / {esc(p["name"])}|{esc(desc)}|{esc(cats)}|{esc(rev)}|{p.get("verification_level","?")} {urls}|')
            atomic_bytes(stage/name,('\n'.join(lines)+'\n').encode())
        atomic_bytes(stage/'INDEX.md',('\n'.join(['# 250项分片索引']+[f'- [{p}]({p})'for p in index])+'\n').encode())
        for filename in['README.md','FIELD-GUIDE.md','ANALYSIS-PROMPT.md']:
            source=root/'export-docs'/filename
            if source.exists():shutil.copy2(source,stage/filename)
        if Path(library).exists():
            for source in Path(library).rglob('*'):
                if source.is_file():
                    target=stage/'sources'/source.relative_to(library)
                    if source.suffix in['.md','.json','.jsonl','.txt']and redact_text(source.read_text(errors='replace'))!=source.read_text(errors='replace'):atomic_bytes(target,redact_text(source.read_text()).encode())
                    else:copy_link(source,target)
        save(stage/'version.json',{'semantic_version_sha256':version,'created_at':at,'project_count':len(projects),'baseline':baseline})
        checksum=[]
        for p in sorted(stage.rglob('*')):
            if p.is_file():checksum.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(stage)))
        atomic_bytes(stage/'checksums-sha256.txt',('\n'.join(checksum)+'\n').encode())
        with zipfile.ZipFile(stage/'trustmrr-latest.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file()and p.name!='trustmrr-latest.zip':z.write(p,'trustmrr-data/'+str(p.relative_to(stage)))
        with zipfile.ZipFile(stage/'trustmrr-latest.zip')as z:
            if z.testzip()is not None:raise ValueError('ZIP CRC validation failed')
        os.replace(stage,final)
        return final,version
    except Exception:
        shutil.rmtree(stage,ignore_errors=True);raise


def recover_commit(root):
    pending=Path(root)/'.pending-commit.json'
    if not pending.exists():return False
    obj=load(pending);state=obj['state'];snapshot=Path(root)/state['latest_snapshot']
    version=load(snapshot/'version.json')
    if not version or version['semantic_version_sha256']!=state['latest_version']:raise ValueError('Pending snapshot/version mismatch; stop for manual review')
    link_atomic(snapshot,Path(root)/'latest')
    if obj.get('baseline')and not(Path(root)/'baseline').exists():link_atomic(snapshot,Path(root)/'baseline')
    save(Path(root)/'state.json',state);save(Path(root)/'changes'/obj['change_filename'],obj['change']);pending.unlink()
    return True

def commit(root,state,change,filename,baseline=False):
    # Durable roll-forward journal: a process crash cannot silently split latest/state/change.
    save(Path(root)/'.pending-commit.json',{'state':state,'change':change,'change_filename':filename,'baseline':baseline})
    recover_commit(root)

def init(root,config):
    if(root/'state.json').exists()or(root/'latest').exists():raise ValueError('Baseline already exists; refusing to overwrite')
    original=Path(config['initial_exports']);dataset=load(original/'trustmrr-all-projects-2026-11-16.json');projects=dataset['projects'];at=dataset['metadata']['created_at']
    if len(projects)!=12590:raise ValueError('Expected verified initial 12590-project dataset')
    library=root/'source-library';shutil.copytree(original/'sources',library,dirs_exist_ok=True)
    (root/'export-docs').mkdir(exist_ok=True)
    for name in['README.md','FIELD-GUIDE.md','ANALYSIS-PROMPT.md']:shutil.copy2(original/name,root/'export-docs'/name)
    # Keep the original package documents, with a prominent monitor-version addendum.
    p=root/'export-docs/README.md';p.write_text('# 持续更新数据包\n\n当前文件名：projects.json / projects.jsonl / metadata.json；基线为2026-11-16，后续版本和覆盖以metadata为准。动态目录可能重复/漏项，不声称全站100%。源站卡片和历史档案不会因本轮失败或缺失被删除。首次观察正值≠实际首单，新入池≠新上线，滚动收入下跌≠流失。\n\n以下为初始采集说明（其中数量/日期仅代表基线，不代表当前快照）：\n\n'+p.read_text())
    ob,pos=seed_observations(projects);state={'schema_version':1,'initialized_at':now(),'baseline_observed_at':at,'last_full_at':at,'last_full_day':localday(at),'last_full_attempt_day':localday(at),'last_success_at':now(),'last_completed_full_slugs':[p['slug']for p in projects if p.get('directory_present')],'url_cache':{},'observations':ob,'positive_seen':pos,'first_seen':{p['slug']:at for p in projects},'latest_version':None,'manual_review_required':False,'not_before':None}
    def cache_seed(url,src,read_at):
        src=Path(src)
        if not src.is_file():return
        body=src.read_text();relative='cache/'+hashlib.sha256(url.encode()).hexdigest()+'.txt';atomic_bytes(root/relative,body.encode());m=re.search(r'next refresh expected around\s+([0-9TZ:.+\-]+)',body)
        state['url_cache'][url]={'body_file':relative,'body_read_at':read_at,'validated_at':read_at,'etag':None,'last_modified':None,'public_next_refresh_at':m.group(1).rstrip('.')if m else None,'seeded_from_prior_verified_cache':True}
    pages=load(library/'directory-pages-manifest.json',[])
    for page in pages:
        file=Path(config['initial_collection_root'])/'raw-directory'/f'page-{page["page"]:03d}.html';cache_seed(page['source_url'],file,page['read_at'])
    for p in projects:
        if p.get('profile_read'):cache_seed(p['trustmrr_url']+'.md',library/'public-profiles'/(p['slug']+'.md'),p.get('profile_read_at')or p['read_at'])
        for i,s in enumerate((p.get('official_deep_check')or{}).get('sources',[])):
            source=Path(s.get('cached_content_file',''))
            if source.is_file():copy_link(source,library/'official-prior'/p['slug']/(str(i)+'-'+source.name))
    recent=Path(config['initial_recent_cache']);cache_seed('https://trustmrr.com/recent',recent,datetime.fromtimestamp(recent.stat().st_mtime,timezone.utc).isoformat())
    robots=library/'robots.txt';cache_seed('https://trustmrr.com/robots.txt',robots,datetime.fromtimestamp(robots.stat().st_mtime,timezone.utc).isoformat())
    final,version=export_snapshot(root,projects,dataset['metadata'],[],library,baseline=True);state['latest_version']=version;state['latest_snapshot']=str(final.relative_to(root));commit(root,state,{'at':now(),'baseline_no_history':True,'events':[]},'baseline-'+localday()+'.json',baseline=True)
    write_status(root,{'at':now(),'status':'baseline_initialized','network_requests':0,'project_count':len(projects),'semantic_version':version,'baseline_no_history':True,'material_change_count':0})
    save(root/'delivery-state.json',{'last_delivered_semantic_version':version,'noted_at':now(),'basis':'Parent confirms original 12590-project export was already delivered; baseline contains the same source facts.'})
    digest(root,24)
    return{'baseline_projects':len(projects),'public_profiles':sum(p.get('profile_read',False)for p in projects),'official_deep':sum(bool(p.get('official_deep_check'))for p in projects),'version':version,'baseline':str(final)}

def write_status(root,status):save(root/'run-status.json',status);append_jsonl(root/'logs/runs.jsonl',status)
def select_mode(state,config,at,requested):
    if requested=='incremental':return'incremental'
    elapsed=(dt(at)-dt(state['last_full_at'])).total_seconds()/3600 if state.get('last_full_at')else 1e6
    if localday(at)!=state.get('last_full_attempt_day')and elapsed>=config['full_min_interval_hours']:return'full'
    return'incremental'
def normalize_known_gmv(incoming,old):
    if old and old.get('metric_label_conflict'):
        metrics=incoming['metrics']
        if metrics.get('revenue_30d'):metrics['gmv_30d']=metrics.pop('revenue_30d')
        metrics.pop('revenue_total',None)
        if metrics.get('gmv'):metrics['gmv_total']=metrics.pop('gmv')
    return incoming

def refresh(root,config,requested='auto'):
    state=load(root/'state.json');original_state=copy.deepcopy(state);data=load(root/'latest/projects.json');projects={p['slug']:p for p in data['projects']};at=now();runid=datetime.now(TZ).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6];events=[];failures=[];incoming=[];metadata=copy.deepcopy(data['metadata']);mode=select_mode(state,config,at,requested);client=PublicClient(root,state,config);facts_committed=False;coverage={'mode':mode,'directory_pages_expected':None,'directory_pages_successful':[],'directory_failed_pages':[],'directory_card_occurrences':0,'directory_unique_slugs':0,'full_crawl_completed':False,'is_whole_site_census':False,'note':'Dynamic pagination can shift/duplicate/omit records; absent records are retained, not interpreted as closures.'}
    try:
        client.check_robots()
        if mode=='full':
            state['last_full_attempt_day']=localday(at);url='https://trustmrr.com/startups'
            text,read_at=client.get(url,config['directory_min_interval_hours'],lambda t: parse(1,t,'',False,at)or(_ for _ in()).throw(ValueError('No directory cards')))
            visible=re.sub('<[^>]+>',' ',text);m=re.search(r'of\s+([\d,]+)\s+startups.*?Page\s+1\s+of\s+(\d+)',visible,re.S)
            if not m:raise FetchError('Directory page count not recognized; no guessed pagination limit')
            count=int(m.group(1).replace(',',''));pages=int(m.group(2));coverage.update(directory_reported_total=count,directory_pages_expected=pages)
            seen=set()
            for n in range(1,pages+1):
                try:
                    if n!=1:text,read_at=client.get('https://trustmrr.com/startups/page/'+str(n),config['directory_min_interval_hours'],lambda t: parse(n,t,'',False,at)or(_ for _ in()).throw(ValueError('No directory cards')))
                    rows=parse(n,text,'',False,read_at)
                    if not rows:raise FetchError('Empty directory page')
                    coverage['directory_pages_successful'].append(n);coverage['directory_card_occurrences']+=len(rows)
                    for row in rows:
                        if row['slug']not in seen:incoming.append(normalize_known_gmv(directory_record(row),projects.get(row['slug'])));seen.add(row['slug'])
                except Blocked:raise
                except FetchError as e:coverage['directory_failed_pages'].append({'page':n,'error':str(e)});failures.append(str(e))
            coverage['directory_unique_slugs']=len(seen);coverage['duplicate_card_occurrences']=coverage['directory_card_occurrences']-len(seen)
            coverage['directory_count_difference_vs_reported']=len(seen)-count;coverage['full_crawl_completed']=len(coverage['directory_pages_successful'])==pages
            if coverage['full_crawl_completed']:
                state['last_full_at']=at;state['last_full_day']=localday(at);state['last_completed_full_slugs']=sorted(seen)
                metadata.update(unique_directory_profiles=len(seen),public_directory_reported_total=count,public_directory_reported_pages=pages,directory_pages_successful=pages,raw_directory_card_occurrences=coverage['directory_card_occurrences'],duplicate_directory_card_occurrences_removed=coverage['duplicate_card_occurrences'])
        try:
            text,read_at=client.get('https://trustmrr.com/recent',config['recent_min_interval_hours'],lambda t:parse_recent(t,at));recent=parse_recent(text,read_at);incoming.extend(recent);coverage['recent_cards']=len(recent)
        except Blocked:raise
        except FetchError as e:failures.append('recent: '+str(e))
        watch=load(root/'watchlist.json')['projects'];new=[x['slug']for x in incoming if x['slug']not in projects];slugs=list(dict.fromkeys([x['slug']for x in watch]+new[:config['new_profiles_per_run']]))
        for slug in slugs:
            url='https://trustmrr.com/startup/'+slug+'.md'
            try:
                text,read_at=client.get(url,config['profile_min_interval_hours'],lambda t:parse_profile(t,slug,at));record=parse_profile(text,slug,read_at)
                previous=projects.get(slug)or{}
                if previous.get('revenue_synced_at')and record.get('revenue_synced_at')and dt(record['revenue_synced_at'])<dt(previous['revenue_synced_at']):
                    failures.append(slug+': stale profile sync snapshot ignored');continue
                incoming.append(record)
                profile_file=root/'source-library/public-profiles'/(slug+'.md')
                if not profile_file.exists()or profile_file.read_text()!=text:atomic_bytes(profile_file,text.encode())
            except Blocked:raise
            except FetchError as e:failures.append(slug+': '+str(e))
        if not incoming:raise FetchError('No valid source records; previous latest retained')
        for item in incoming:
            slug=item['slug'];old=projects.get(slug)
            if old is None:
                state['first_seen'][slug]=at;events.append({'type':'new_project','slug':slug,'at':at,'source_url':item['source_url'],'material':True,'note':'New to our observed pool, NOT proof of recent product launch or first sale.'})
            events.extend(observe(state,item,at));projects[slug]=merge_project(old,item)
        allp=list(projects.values())
        for i,p in enumerate(allp,1):p['id']=i;p['verification_level']='O'if p.get('official_deep_check')else'P'if p.get('profile_read')else'D'if p.get('directory_present')else'N'if any(q.get('source_kind')=='public_recent_page'for q in p.get('sources',[]))else'R';p['missing_fields']=[k for k in['website_url','core_function_original','source_categories','launch_date','pricing_original','target_customers_original','tech_stack_original']if not p.get(k)]
        last_members=set(state.get('last_completed_full_slugs',[]))
        if last_members:
            for p in allp:p['present_in_last_completed_full_directory']=p['slug']in last_members
        metadata.update(profiles_with_original_function_description=sum(bool(p.get('core_function_original'))for p in allp),profiles_with_source_categories=sum(bool(p.get('source_categories'))for p in allp),profiles_with_website_url=sum(bool(p.get('website_url'))for p in allp),profiles_with_explicit_launch_evidence=sum(bool(p.get('launch_date'))for p in allp),extra_public_profiles_or_recommendations_not_in_directory=sum(p['slug']not in last_members for p in allp)if last_members else None)
        version=semantic_hash(allp);changed=version!=state['latest_version'];metadata['last_refresh_coverage']=coverage;metadata['initial_baseline_no_comparable_history']=False
        if changed:
            final,version=export_snapshot(root,allp,metadata,events,root/'source-library');state['latest_version']=version;state['latest_snapshot']=str(final.relative_to(root))
        state['last_success_at']=now();state['last_coverage']=coverage
        change={'at':at,'run_id':runid,'mode':mode,'baseline_no_history':False,'events':events,'coverage':coverage,'failures':failures,'fact_version_changed':changed,'semantic_version':version}
        commit(root,state,change,runid+'.json');facts_committed=True
        status={'at':now(),'run_id':runid,'status':'partial_success'if failures else'success','mode':mode,'network_requests':client.requests,'cache_hits':client.cache_hits,'project_count':len(allp),'event_count':len(events),'material_change_count':sum(e.get('material',False)for e in events),'fact_version_changed':changed,'semantic_version':version,'coverage':coverage,'failures':failures,'new_attachment_needed':version!=load(root/'delivery-state.json',{}).get('last_delivered_semantic_version'),'note':'No outgoing messages or routine edits performed.'};write_status(root,status);digest(root,24);return status
    except Exception as e:
        # Keep previous projects, observations and version; retain only request-cache/backoff bookkeeping.
        if facts_committed:original_state=load(root/'state.json')
        for k in['url_cache','not_before','manual_review_required','last_full_attempt_day']:
            if k in state:original_state[k]=state[k]
        save(root/'state.json',original_state);status={'at':now(),'run_id':runid,'status':'blocked'if isinstance(e,Blocked)else'failed','mode':mode,'error':str(e),'network_requests':client.requests,'cache_hits':client.cache_hits,'previous_latest_preserved':not facts_committed,'post_commit_reporting_error':facts_committed,'material_change_count':0,'new_attachment_needed':False,'coverage':coverage};write_status(root,status);append_jsonl(root/'logs/failures.jsonl',status);save(root/'changes'/(runid+'.json'),{'at':at,'run_id':runid,'events':[],'failed':True,'error':str(e),'coverage':coverage});digest(root,24);return status

def digest(root,hours=24):
    cutoff=datetime.now(timezone.utc)-timedelta(hours=hours);runs=[];events=[];initial=False
    for p in sorted((root/'changes').glob('*.json')):
        obj=load(p)
        if dt(obj['at'])>=cutoff:runs.append(obj);events.extend(obj.get('events',[]));initial=initial or obj.get('baseline_no_history',False)
    counts={}
    for e in events:counts[e['type']]=counts.get(e['type'],0)+1
    status=load(root/'run-status.json',{});state=load(root/'state.json',{});out={'generated_at':now(),'window_hours':hours,'run_count':len(runs),'initial_baseline_in_window':initial,'event_counts':counts,'material_event_count':sum(e.get('material',False)for e in events),'events':events,'latest_status':status,'latest_version':state.get('latest_version'),'attachment_changed_since_last_delivery':state.get('latest_version')!=load(root/'delivery-state.json',{}).get('last_delivered_semantic_version'),'baseline_note':'Baseline creation has no comparable history; this is not proof of no business changes.'if initial else None}
    lines=[f'# TrustMRR 最近{hours}小时变化汇总',f'生成：{datetime.now(TZ).strftime("%Y-%m-%d %H:%M")} 北京时间（UTC+8）',f'运行记录 {len(runs)} 次；事件 {len(events)} 条；需人工判断的实质候选事件 {out["material_event_count"]} 条。',f'当前状态：{status.get("status","unknown")}；版本：{state.get("latest_version","")}']
    if initial:lines.append('本时间窗包含首次基线建立：首次没有历史可比，不能把“无事件”解释为项目没有增长。')
    lines.append('新入池≠刚上线；首次观察正值≠实际首单；目录舍入展示变化≠确认增长；滚动收入下降≠流失；收入≠利润。')
    for k,v in counts.items():lines.append(f'- {k}: {v}')
    if not events:lines.append('没有新增的可比变化事件；仍需查看最近运行是否成功及数据是否陈旧。')
    for e in events[:100]:lines.append(f'- {e["slug"]} | {e["type"]} | {e.get("metric","")} {e.get("before","")} → {e.get("after","")} | {e.get("note","")}')
    if len(events)>100:lines.append('完整事件见同名JSON，Markdown只列前100条，不是原池筛除。')
    path=root/'daily';save(path/'latest-24h.json',out);atomic_bytes(path/'latest-24h.md',('\n'.join(lines)+'\n').encode());save(path/(localday()+'.json'),out);atomic_bytes(path/(localday()+'.md'),('\n'.join(lines)+'\n').encode());return out


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init');p=sub.add_parser('refresh');p.add_argument('--mode',choices=['auto','incremental','full'],default='auto');sub.add_parser('status');p=sub.add_parser('mark-delivered');p.add_argument('--version',required=True);p.add_argument('--note',default='Actual attachment delivery confirmed by parent');p=sub.add_parser('digest');p.add_argument('--hours',type=int,default=24)
    args=parser.parse_args();root=args.root.resolve();config=load(root/'config.json')
    try:
        if args.command=='status':
            result=load(root/'run-status.json',{'status':'not_initialized'});version=load(root/'latest/version.json',{}).get('semantic_version_sha256');result['new_attachment_needed']=bool(version and version!=load(root/'delivery-state.json',{}).get('last_delivered_semantic_version'))
        else:
            with RunLock(root):
                recover_commit(root)
                if args.command=='init':result=init(root,config)
                elif args.command=='refresh':result=refresh(root,config,args.mode)
                elif args.command=='mark-delivered':
                    current=load(root/'latest/version.json')['semantic_version_sha256']
                    if args.version!=current:raise ValueError('Only the current fact version may be acknowledged; no sending performed')
                    result={'last_delivered_semantic_version':args.version,'noted_at':now(),'note':args.note};save(root/'delivery-state.json',result)
                else:result={k:v for k,v in digest(root,args.hours).items()if k!='events'}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get('status')not in['failed','blocked']else 2
    except Locked as e:print(str(e),file=sys.stderr);return 75
    except Exception as e:print(type(e).__name__+': '+str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
