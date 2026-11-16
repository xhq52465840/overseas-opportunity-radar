#!/usr/bin/env python3
import json,hashlib,zipfile,re
from pathlib import Path
from monitor import semantic_hash
from redaction import sensitive
ROOT=Path(__file__).resolve().parents[1]
def check(root=ROOT):
    data=root/'data';obj=json.loads((data/'projects.json').read_text());ps=obj['projects'];idx=json.loads((data/'index.json').read_text());version=json.loads((data/'version.json').read_text())
    assert len(ps)==len({p['slug']for p in ps})==len(idx['projects'])
    assert len(ps)==sum(1 for _ in(data/'projects.jsonl').open())
    assert semantic_hash(ps)==version['semantic_version_sha256']
    assert all(m.get('semantic_version_sha256')==version['semantic_version_sha256']for m in[obj['metadata'],idx['metadata'],json.loads((data/'metadata.json').read_text())])
    assert len(list((data/'raw/public-profiles').glob('*.md')))==sum(bool(p.get('profile_read'))for p in ps)
    assert all(p.get('source_url')and p.get('read_at')for p in ps)
    assert all(not p.get('launch_date')or p.get('launch_evidence')for p in ps)
    assert all(p['replication_cost']['monthly_usd']is None for p in ps)
    assert not any(p['slug'].startswith('fixture-')for p in ps)
    by={p['slug']:p for p in ps}
    for slug in['gumroad','easytools-sp-z-o-o']:
        assert by[slug]['metrics']['revenue_30d']is None and by[slug]['metrics']['revenue_total']is None
    with zipfile.ZipFile(data/'trustmrr-data.zip')as z:
        assert z.testzip()is None
        for name in z.namelist():
            if Path(name).suffix in['.json','.jsonl','.md','.txt']:assert not sensitive(z.read(name).decode('utf-8',errors='replace')),'Archive contains possible credential: '+name
    names=[]
    for p in root.rglob('*'):
        if not p.is_file()or any(x in p.parts for x in['.git','_site','__pycache__']):continue
        assert p.name not in['.cf-token','.env','credentials','cookies.sqlite','Cookies']
        if p.suffix not in['.zip','.gz','.pyc']:
            body=p.read_text(errors='replace')
            assert not sensitive(body),str(p)+' possible credential'
        if p.stat().st_size>95_000_000:raise AssertionError('File too large for ordinary Git hosting: '+str(p))
    print(json.dumps({'projects':len(ps),'profile_sources':sum(bool(p.get('profile_read'))for p in ps),'official_evidence':sum(bool(p.get('official_deep_check'))for p in ps),'secret_pattern_scan':'passed','version':version['semantic_version_sha256']}))
if __name__=='__main__':check()
