#!/usr/bin/env python3
"""Restore portable monitor state, run the shared collector, publish only an explicit public-data allowlist."""
import argparse,hashlib,json,shutil,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
from monitor import refresh,RunLock,load,save,atomic_bytes,semantic_hash
from build_data import build
from redaction import scrub,redact_text,sensitive
ROOT=Path(__file__).resolve().parents[1]
def sanitize(obj):return scrub(obj)

def seed(root,work):
    data=root/'data';(work/'snapshots/seed').mkdir(parents=True)
    for name in['projects.json','metadata.json','version.json']:shutil.copy2(data/name,work/'snapshots/seed'/name)
    (work/'latest').symlink_to('snapshots/seed',target_is_directory=True)
    state=load(data/'monitor-state.json');state['latest_snapshot']='snapshots/seed';save(work/'state.json',state)
    config=load(root/'tools/config.example.json');save(work/'config.json',config)
    shutil.copy2(data/'watchlist.json',work/'watchlist.json');shutil.copytree(data/'raw',work/'source-library');shutil.copytree(root/'docs/export',work/'export-docs')
    (work/'changes').mkdir()
    for source in(data/'history').rglob('*.json')if(data/'history').exists()else[]:shutil.copy2(source,work/'changes'/source.name)
    for url,cache in state.get('url_cache',{}).items():
        path=None
        if url.endswith('/robots.txt'):path=data/'raw/robots.txt'
        elif '/startup/'in url and url.endswith('.md'):path=data/'raw/public-profiles'/(url.rsplit('/',1)[-1])
        if path and path.is_file():
            body=path.read_text()
            if '[REDACTED_POSSIBLE_CREDENTIAL]'not in body and 'redacted possible credential'not in body:atomic_bytes(work/cache['body_file'],body.encode())
    return config

def run(root=ROOT,check=False):
    data=root/'data';before=hashlib.sha256((data/'annotations.json').read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='radar-collector-')as temp:
        work=Path(temp)/'monitor';config=seed(root,work)
        projects=load(data/'projects.json')['projects'];version=load(data/'version.json')['semantic_version_sha256']
        if semantic_hash(projects)!=version:raise ValueError('Data fact hash differs from recorded version; review manual changes before collecting')
        if check:
            result={'status':'offline_check_passed','projects':len(projects),'profiles':sum(bool(x.get('profile_read'))for x in projects),'official_evidence':sum(bool(x.get('official_deep_check'))for x in projects),'network_requests':0};print(json.dumps(result));return result
        with RunLock(work):result=refresh(work,config,'auto')
        # Preserve a block/backoff and a visible status even when source collection fails.
        state=sanitize(load(work/'state.json'));state['latest_snapshot']='snapshots/seed';save(data/'monitor-state.json',state);public_status=sanitize(result);public_status.pop('new_attachment_needed',None);save(data/'monitor-status.json',public_status)
        for source in(work/'source-library/public-profiles').glob('*.md'):atomic_bytes(data/'raw/public-profiles'/source.name,redact_text(source.read_text()).encode())
        robot_cache=state.get('url_cache',{}).get('https://trustmrr.com/robots.txt',{})
        robot_body=work/robot_cache.get('body_file','missing')
        if robot_body.is_file():shutil.copy2(robot_body,data/'raw/robots.txt')
        for source in(work/'changes').glob('*.json'):
            day=load(source)['at'][:10];dest=data/'history'/day/source.name
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        for source in(work/'daily').glob('*')if(work/'daily').exists()else[]:
            dest=data/'daily'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        if result.get('fact_version_changed'):
            current=work/'latest';obj=sanitize(load(current/'projects.json'));atomic_bytes(data/'projects.json',json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode())
            for name in['metadata.json','version.json']:shutil.copy2(current/name,data/name)
            public_version=semantic_hash(obj['projects']);version_doc=load(data/'version.json');version_doc['semantic_version_sha256']=public_version;save(data/'version.json',version_doc);state['latest_version']=public_version;save(data/'monitor-state.json',state)
            # Strict allowlist; annotations and unrelated files never enter this copy loop.
            for source in(work/'source-library/public-profiles').glob('*.md'):atomic_bytes(data/'raw/public-profiles'/source.name,redact_text(source.read_text()).encode())
            build(root)
        assert hashlib.sha256((data/'annotations.json').read_bytes()).hexdigest()==before,'Collector must never overwrite manual annotations'
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true',help='Offline restore/consistency check, no network or data writes');a=p.parse_args();run(check=a.check)
