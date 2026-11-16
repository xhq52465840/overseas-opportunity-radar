#!/usr/bin/env python3
"""Build a static site without copying private/runtime files or huge raw downloads into Pages."""
from pathlib import Path
import argparse,shutil,json
from redaction import scrub
ROOT=Path(__file__).resolve().parents[1]
def build(root,out):
    out.mkdir(parents=True,exist_ok=True)
    for name in['index.html','app.js','style.css']:shutil.copy2(root/'web'/name,out/name)
    (out/'data').mkdir(exist_ok=True)
    for name in['index.json','annotations.json','metadata.json','version.json','monitor-status.json']:(out/'data'/name).write_text(json.dumps(scrub(json.loads((root/'data'/name).read_text())),ensure_ascii=False,separators=(',',':')))
    shutil.copytree(root/'data/details',out/'data/details',dirs_exist_ok=True)
    (out/'.nojekyll').write_text('')
    size=sum(p.stat().st_size for p in out.rglob('*')if p.is_file());assert size<250_000_000,'Unexpected site size; refuse oversized Pages artifact'
    print(json.dumps({'site':str(out),'bytes':size}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'_site');a=p.parse_args();build(ROOT,a.out)
