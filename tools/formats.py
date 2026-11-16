"""Pure parsing helpers reused from validated 2026-11-16 public exports."""

import re,json

from bs4 import BeautifulSoup

def money(v):
 if not v:return None
 s=v.replace('$','').replace(',','').strip().lower()
 try:return float(s[:-1])*{'k':1000,'m':1e6,'b':1e9}[s[-1]]if s[-1:]in['k','m','b']else float(s)
 except:return None

def line(text,key):
 m=re.search(r'^- '+re.escape(key)+r':\s*(.*)$',text,re.M);v=m.group(1).strip()if m else None
 return None if v in[None,'','Not provided','Unknown','N/A','None','Not available']else v

def section(text,name):
 m=re.search(r'^## '+re.escape(name)+r'\s*\n(.*?)(?=^## |\Z)',text,re.M|re.S);return m.group(1).strip()if m else None

def links(text):return [{'name':n,'url':u}for n,u in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',text or'')]

def initial(slug,name,url):
 return {'slug':slug,'name':name,'trustmrr_url':url,'website_url':None,'core_function_original':None,'core_function_zh':None,'source_categories':[],'metrics':{'mrr':None,'revenue_30d':None,'revenue_total':None},'revenue_synced_at':None,'founded_date':None,'launch_date':None,'launch_evidence':None,'target_customers_original':None,'pricing_original':None,'distribution_channels_original':None,'tech_stack_original':None,'value_proposition_original':None,'problem_solved_original':None,'audience_type_original':None,'country':None,'payment_verification_provider':None,'directory_present':False,'profile_read':False,'official_deep_check':None,'is_web_product':None,'replication_cost':{'status':'unknown_not_verified','startup_usd':None,'monthly_usd':None},'analysis':None,'sources':[]}

def source(url,at,kind,**kw):return {'source_url':url,'read_at':at,'source_kind':kind,**kw}

def metric(display,url,at,precision,synced=None):
 return None if display is None else {'amount':money(display),'currency':'USD'if '$'in display else None,'display':display,'precision':precision,'synced_at':synced,'source_url':url,'read_at':at}

def esc(v):return str(v or'未知').replace('|','\\|').replace('\n',' ').replace('\r',' ')

def parse_num(s):
 if not s:return None
 s=s.replace('$','').replace(',','').strip().lower()
 try:
  return float(s[:-1])*{'k':1000,'m':1000000,'b':1000000000}[s[-1]]if s[-1:]in['k','m','b']else float(s)
 except:return None

def public_url(n):return 'https://trustmrr.com/startups'+(''if n==1 else '/page/'+str(n))

def parse(n,text,path,cached,at):
 s=BeautifulSoup(text,'html.parser');out=[]
 for pos,a in enumerate(s.select('section[aria-label="Startup profiles"] a[href^="/startup/"]'),1):
  h=a.find('h2');ps=a.find_all('p');metrics={}
  for p in ps:
   label=p.get_text(' ',strip=True)
   if label in ['MRR','Revenue (30d)','Total','GMV']:
    q=p.find_next_sibling('p');v=q.get_text(' ',strip=True)if q else None
    metrics[{'MRR':'mrr','Revenue (30d)':'revenue_30d','Total':'revenue_total','GMV':'gmv'}[label]]={'amount':parse_num(v),'currency':'USD'if v and '$'in v else None,'display':v,'precision':'directory_display_rounded_or_unknown','synced_at':None,'source_url':public_url(n),'read_at':at}
  desc=next((p.get_text(' ',strip=True)for p in ps if p.get_text(' ',strip=True)not in ['MRR','Revenue (30d)','Total'] and p.find_next_sibling('p')is None),None)
  # The first paragraph is the actual public card description, not inferred from its name.
  desc=ps[0].get_text(' ',strip=True)if ps and ps[0].get_text(' ',strip=True)not in['MRR','Revenue (30d)','Total']else None
  out.append({'slug':a['href'].split('/')[-1],'name':h.get_text(' ',strip=True)if h else None,'profile_url':'https://trustmrr.com'+a['href'],'description_original':desc,'description_precision':'public_directory_card_may_be_truncated','metrics':metrics,'is_for_sale':bool(a.find(string=re.compile('FOR SALE'))),'directory_page':n,'directory_position':pos,'source_url':public_url(n),'source_kind':'public_directory_page','source_category':'全部公开项目目录；非产品类别','read_at':at,'cached_page_reused':cached,'raw_file':str(path)})
 return out

def parse_profile(text,slug,at):
    if '## Profile' not in text or '## Revenue' not in text:
        raise ValueError('Not a normal public Markdown profile')
    u='https://trustmrr.com/startup/'+slug+'.md'
    x=initial(slug,line(text,'Name')or slug,u[:-3]);x['profile_read']=True
    x['profile_source_url']=u;x['profile_read_at']=at;x['source_url']=u;x['read_at']=at
    ws=links(line(text,'Website'));x['website_url']=ws[0]['url']if ws else None
    desc=line(text,'Description')
    if desc:x.update(core_function_original=desc,core_function_precision='public_profile_description_original',core_function_source_url=u,core_function_read_at=at)
    x['country']=line(text,'Country');x['founded_date']=line(text,'Founded date')
    x['revenue_synced_at']=line(text,'Revenue last synced')or line(text,'Revenue data last synced')
    x['payment_verification_provider']=line(text,'Verified payment provider API source')
    for key,pattern in [('mrr',r'^- Current MRR:\s*(.+)$'),('revenue_30d',r'^\| Last 30 days \|\s*([^|]+)\|'),('revenue_total',r'^\| All time \|\s*([^|]+)\|')]:
        m=re.search(pattern,text,re.M)
        if m:x['metrics'][key]=metric(m.group(1).strip(),u,at,'public_profile_published_snapshot',x['revenue_synced_at'])
    insight=section(text,'Startup Insights')or''
    for key,label in [('value_proposition_original','Value proposition'),('problem_solved_original','Problem solved'),('pricing_original','Pricing model'),('target_customers_original','Target persona'),('audience_type_original','Audience type'),('additional_info_original','Additional info')]:x[key]=line(insight,label)
    x['tech_stack_original']=section(text,'Tech Stack');x['distribution_channels_original']=section(text,'Distribution')
    x['source_categories']=[{**c,'source_url':u,'read_at':at,'provenance':'profile_markets_founder_supplied'}for c in links(line(insight,'Markets'))if'/category/'in c['url']]
    x['profile_fields_provenance']={'source_url':u,'read_at':at,'product_details_verification':'Founder supplied; no independent audit.'}
    x['sources']=[source(u,at,'public_markdown_profile')]
    m=re.search(r'next refresh expected around\s+([0-9TZ:.+\-]+)',text)
    x['_next_refresh_at']=m.group(1).rstrip('.')if m else None
    # Launch dates are never inferred from founded date, entry date, or filenames.
    return x


def parse_recent(text,at):
    soup=BeautifulSoup(text,'html.parser');rows=[];seen=set()
    for a in soup.select('a[href^="/startup/"]'):
        slug=a['href'].split('/')[-1];card=a.parent;h=card.find('h3')
        if not h or slug in seen:continue
        seen.add(slug);x=initial(slug,h.get_text(' ',strip=True),'https://trustmrr.com/startup/'+slug)
        ps=card.find_all('p');desc=ps[0].get_text(' ',strip=True)if ps else None
        if desc:x.update(core_function_original=desc,core_function_precision='public_recent_card_may_be_truncated',core_function_source_url='https://trustmrr.com/recent',core_function_read_at=at)
        for div in card.find_all('div'):
            label=div.get_text(' ',strip=True)
            if label not in['Revenue','MRR']:continue
            q=div.find_next_sibling('div')
            if q:
                # The recent page does NOT specify a period for Revenue.
                key='mrr'if label=='MRR'else'revenue_unspecified'
                x['metrics'][key]=metric(q.get_text(' ',strip=True),'https://trustmrr.com/recent',at,'recent_display_rounded_or_unknown')
        x['sources']=[source('https://trustmrr.com/recent',at,'public_recent_page')];x['source_url']='https://trustmrr.com/recent';x['read_at']=at
        x['entry_semantics']='first observed in recently-added directory, NOT product launch'
        rows.append(x)
    if not rows:raise ValueError('Empty/unrecognized recent-page cards; keep prior dataset')
    return rows


def directory_record(d):
    x=initial(d['slug'],d['name'],d['profile_url']);x.update(directory_present=True,directory_page=d['directory_page'],core_function_original=d['description_original'],core_function_precision=d['description_precision'],core_function_source_url=d['source_url'],core_function_read_at=d['read_at'])
    x['metrics'].update(d['metrics']);x['directory_snapshot']={'name':d['name'],'description_original':d['description_original'],'metrics':d['metrics']}
    x['sources']=[source(d['source_url'],d['read_at'],'public_directory_page')];x['source_url']=d['source_url'];x['read_at']=d['read_at'];return x
