#!/usr/bin/env python3
"""Read-only audit. Reports only type/path/count, never a matched value."""
import argparse,json,zipfile,io,collections
from pathlib import Path
from redaction import sensitive,text_findings,url_problem,CREDENTIAL_KEY
ROOT=Path(__file__).resolve().parents[1]
URL_KEYS=lambda k:k.lower().endswith('url')or k.lower()in['website','uri','href']
def audit(root,include_archives=True):
 issues=[];counts=collections.Counter();files=0
 def add(path,kind):issues.append({'location':path,'type':kind});counts[kind]+=1
 def walk(obj,path):
  if isinstance(obj,dict):
   for key,value in obj.items():
    where=path+'/'+str(key)
    if isinstance(value,str)and value:
     if CREDENTIAL_KEY.fullmatch(key):add(where,'credential_named_field')
     if URL_KEYS(key):
      problem=url_problem(value)
      if problem:add(where,problem)
    walk(value,where)
  elif isinstance(obj,list):
   for n,value in enumerate(obj):walk(value,path+'/'+str(n))
  elif isinstance(obj,str):
   for kind in text_findings(obj):add(path,kind)
 def inspect(name,body,depth=0):
  nonlocal files
  files+=1;suffix=Path(name).suffix.lower()
  if suffix=='.zip'and include_archives:
   if depth>3:add(name,'archive_depth_limit');return
   try:
    with zipfile.ZipFile(io.BytesIO(body))as z:
     if sum(i.file_size for i in z.infolist())>500_000_000:add(name,'archive_size_limit');return
     for item in z.infolist():
      if item.is_dir():continue
      if item.filename.startswith('/')or'..'in Path(item.filename).parts:add(name,'archive_path_traversal');continue
      inspect(name+'!'+item.filename,z.read(item),depth+1)
   except zipfile.BadZipFile:add(name,'invalid_zip')
  elif suffix=='.json':
   try:walk(json.loads(body),name)
   except(ValueError,UnicodeError):add(name,'invalid_json')
  elif suffix=='.jsonl':
   for n,line in enumerate(body.decode().splitlines(),1):
    if line.strip():
     try:walk(json.loads(line),name+':line'+str(n))
     except ValueError:add(name+':line'+str(n),'invalid_jsonl')
  elif suffix in['.md','.txt','.html','.csv']:
   text=body.decode(errors='replace')
   for kind in text_findings(text):add(name,kind)
 for p in sorted((root/'data').rglob('*')):
  if p.is_file():inspect(str(p.relative_to(root)),p.read_bytes())
 # Source files may contain deliberately unsafe test strings; scan them for actual credential shapes only.
 for directory in['web','tools','.github','docs']:
  for p in(root/directory).rglob('*'):
   if p.is_file()and'__pycache__'not in p.parts:
    if sensitive(p.read_text(errors='replace')):add(str(p.relative_to(root)),'credential_pattern_in_code_or_docs')
 return{'files_and_archive_members_scanned':files,'issue_count':len(issues),'counts':dict(counts),'issues':issues,'secret_values_printed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--report',type=Path);p.add_argument('--no-archives',action='store_true');a=p.parse_args();out=audit(a.root,not a.no_archives)
 if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({'files_and_archive_members_scanned':out['files_and_archive_members_scanned'],'issue_count':out['issue_count'],'counts':out['counts'],'secret_values_printed':False},ensure_ascii=False));raise SystemExit(1 if out['issue_count']else 0)
