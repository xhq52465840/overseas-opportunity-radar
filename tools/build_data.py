#!/usr/bin/env python3
"""Generate lean UI index, on-demand details and portable AI downloads from public facts."""
import argparse,json,hashlib,zipfile,shutil
from pathlib import Path
from datetime import datetime,timezone
from redaction import scrub,redact_text
from monitor import semantic_hash
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
def build(root=ROOT):
    data=root/'data';original=read(data/'projects.json');obj=scrub(original)
    # A publication redaction changes facts. Keep every embedded/exported version in sync,
    # including when an earlier safety pass already rewrote the input before this build.
    fact_version=semantic_hash(obj['projects'])
    obj.setdefault('metadata',{})['semantic_version_sha256']=fact_version
    if obj!=original:write(data/'projects.json',obj)
    version=read(data/'version.json')
    if version.get('semantic_version_sha256')!=fact_version:
        version['semantic_version_sha256']=fact_version;write(data/'version.json',version)
    if(data/'monitor-state.json').exists():
        state=read(data/'monitor-state.json')
        if state.get('latest_version')!=fact_version:
            state['latest_version']=fact_version;write(data/'monitor-state.json',scrub(state))
    for raw in(data/'raw').rglob('*'):
        if not raw.is_file():continue
        if raw.suffix=='.json':
            value=read(raw);clean=scrub(value)
            if clean!=value:write(raw,clean)
        elif raw.suffix=='.jsonl':
            lines=[json.loads(x)for x in raw.read_text().splitlines()if x.strip()];clean=scrub(lines)
            if clean!=lines:raw.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n'for x in clean))
        elif raw.suffix in['.md','.txt']:
            value=raw.read_text();clean=redact_text(value)
            if clean!=value:raw.write_text(clean)
    ps=obj['projects'];ann=read(data/'annotations.json')['projects'];index=[]
    for i,p in enumerate(ps):
        ms=p.get('metrics',{});v=lambda k:(ms.get(k)or{}).get('amount');precision=lambda k:(ms.get(k)or{}).get('precision','unknown')
        index.append({'s':p['slug'],'n':p['name'],'d':(p.get('core_function_original')or'')[:260],'m':v('mrr'),'r':v('revenue_30d'),'t':v('revenue_total'),'c':list(dict.fromkeys(c['name']for c in p.get('source_categories',[]))),'v':p.get('verification_level','?'),'w':p.get('website_url'),'read':p.get('read_at'),'sync':p.get('revenue_synced_at'),'j':i//100+1,'a':[precision(k)for k in['mrr','revenue_30d','revenue_total']],'watch':bool(ann.get(p['slug'],{}).get('watch'))})
    for start in range(0,len(ps),100):write(data/'details'/f'part-{start//100+1:03d}.json',{p['slug']:p for p in ps[start:start+100]})
    metadata={**obj['metadata'],'site_built_at':datetime.now(timezone.utc).isoformat(),'total_exported_projects':len(ps),'public_profiles_read_and_parsed':sum(bool(p.get('profile_read'))for p in ps),'official_deep_verified_from_prior_cache':sum(bool(p.get('official_deep_check'))for p in ps),'watchlist_count':sum(bool(v.get('watch'))for v in ann.values()),'profiles_with_website_url':sum(bool(p.get('website_url'))for p in ps),'index_bytes_note':'Initial load is the compact index only; full details are fetched in 100-project chunks.','independent_project':True,'source_site':'https://trustmrr.com/','not_official':'独立商机研究库，非TrustMRR官方；不构成投资或收益承诺。'}
    write(data/'index.json',{'metadata':metadata,'projects':index});write(data/'metadata.json',metadata)
    # Preserve the complete machine-readable data pool and generate AI-friendly 250-row text parts.
    with(data/'projects.jsonl').open('w')as f:
        for p in ps:f.write(json.dumps(p,ensure_ascii=False,separators=(',',':'))+'\n')
    def esc(x):return str(x or'未知').replace('|','\\|').replace('\n',' ')
    parts=[]
    for start in range(0,len(ps),250):
        sub=ps[start:start+250];path=data/'markdown'/f'projects-{start//250+1:03d}.md';path.parent.mkdir(exist_ok=True);parts.append(path.relative_to(data).as_posix())
        lines=[f'# TrustMRR公开项目 {start+1}–{start+len(sub)} / {len(ps)}','无预筛；功能/类别为来源原文。收入非利润；目录值可能舍入；未知不等于0；新入池/成立日不代表上线。','|slug / 产品|功能原文|原站类别|MRR / 30天 / 累计（USD）|来源级别|链接|','|---|---|---|---|---|---|']
        for p in sub:
            desc=p.get('core_function_original')or'未知';desc=desc[:400]+('…〔全文见JSON〕'if len(desc)>400 else'');ms=p.get('metrics',{});metric=lambda k:(ms.get(k)or{}).get('display')or'未知';cats='/'.join(dict.fromkeys(c['name']for c in p.get('source_categories',[])))or'未知';urls=f'[TrustMRR]({p["trustmrr_url"]})'+(f' [官网]({p["website_url"]})'if p.get('website_url')else'')
            lines.append(f'|{p["slug"]} / {esc(p["name"])}|{esc(desc)}|{esc(cats)}|{metric("mrr")} / {metric("revenue_30d")} / {metric("revenue_total")}|{p.get("verification_level","?")}|{urls}|')
        path.write_text('\n'.join(lines)+'\n')
    (data/'markdown/INDEX.md').write_text('# AI分片索引\n\n'+'\n'.join(f'- [{p}](./{Path(p).name})'for p in parts)+'\n')
    # ZIP uses a strict data/document allowlist; never exports runtime caches, credentials or annotations.
    files=[data/'projects.json',data/'projects.jsonl',data/'metadata.json',data/'version.json']
    files+=list((data/'markdown').glob('*.md'))+list((root/'docs/export').glob('*.md'))+list((data/'raw').rglob('*.md'))+list((data/'raw').glob('*.json'))+list((data/'raw').glob('*.jsonl'))+[data/'raw/robots.txt']
    with zipfile.ZipFile(data/'trustmrr-data.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p in sorted(set(files)):
            if p.is_file():z.write(p,p.relative_to(root).as_posix())
    with zipfile.ZipFile(data/'trustmrr-data.zip')as z:assert z.testzip()is None
    assert len({p['s']for p in index})==len(ps)
    print(json.dumps({'projects':len(ps),'detail_chunks':(len(ps)+99)//100,'markdown_parts':len(parts),'index_bytes':(data/'index.json').stat().st_size,'zip_bytes':(data/'trustmrr-data.zip').stat().st_size}))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=ROOT);args=a.parse_args();build(args.root.resolve())
