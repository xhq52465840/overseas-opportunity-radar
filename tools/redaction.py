"""Conservative public-export boundary. Never print, validate or use matched credentials."""
import html,re
from functools import lru_cache
from urllib.parse import unquote,urlsplit,parse_qsl
MARKER='[REDACTED_POSSIBLE_CREDENTIAL]'
LINK_MARKER='[REMOVED_UNSAFE_URL]'
PATTERNS=[
 re.compile(r'(?:sk|rk)_(?:live|test)_[A-Za-z0-9_]{16,}'),
 re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'),re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),
 re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{24,}'),re.compile(r'xox[baprs]-[A-Za-z0-9-]{20,}'),
 re.compile(r'AKIA[A-Z0-9]{16}'),re.compile(r'AIza[A-Za-z0-9_-]{30,}'),
 re.compile(r'(?:eyJ[A-Za-z0-9_-]{8,}\.){2}[A-Za-z0-9_-]{10,}'),
 re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
 re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}'),
]
CREDENTIAL_KEY=re.compile(r'(?i)^(?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|authorization|cookie|session[_-]?token|stripe[_-]?(?:secret|restricted)[_-]?key)$')
QUERY_KEY=re.compile(r'(?i)^(?:key|api[_-]?key|access[_-]?token|refresh[_-]?token|token|auth|authorization|password|passwd|secret|client[_-]?secret|signature|sig|credential|x-amz-(?:signature|credential|security-token)|x-goog-(?:signature|credential))$')
URL_PATTERN=re.compile(r'(?i)(?:https?://|(?:javascript|vbscript|data|file|mailto|tel):)[^\s<>"\[\]`]+')
DANGEROUS_HTML=re.compile(r'(?is)<\s*(?:script|iframe|object|embed|form|base|meta|link)\b[^>]*>(?:.*?<\s*/\s*(?:script|iframe|object|form)\s*>)?')
EVENT_ATTR=re.compile(r'(?i)\bon(?:error|load|click|mouseover|focus|submit)\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27|[^\s>]+)')
def decoded(text):
 text=html.unescape(text)
 for _ in range(2):
  other=unquote(text)
  if other==text:break
  text=other
 return text

@lru_cache(maxsize=131072)
def sensitive(text):
 if not isinstance(text,str):return False
 value=decoded(text)
 return any(p.search(value)for p in PATTERNS)
@lru_cache(maxsize=131072)
def url_problem(raw):
 try:
  raw=decoded(raw).strip();u=urlsplit(raw)
  if u.scheme.lower()not in['http','https']or not u.hostname:return'url_scheme_or_missing_host'
  if any(ord(c)<33 for c in raw):return'url_control_or_space'
  if u.username is not None or u.password is not None:return'url_userinfo'
  if sensitive(raw):return'credential_pattern_in_url'
  for k,v in parse_qsl(u.query,keep_blank_values=True)+parse_qsl(u.fragment,keep_blank_values=True):
   if QUERY_KEY.fullmatch(k):return'credential_query_or_fragment'
  return None
 except(ValueError,TypeError):return'malformed_url'

@lru_cache(maxsize=131072)
def text_findings(text):
 if not isinstance(text,str):return[]
 out=[]
 if sensitive(text):out.append('credential_pattern')
 if DANGEROUS_HTML.search(text)or EVENT_ATTR.search(text):out.append('unsafe_html')
 for match in URL_PATTERN.finditer(html.unescape(text)):
  issue=url_problem(match.group().rstrip(').,;'))
  if issue:out.append(issue)
 return sorted(set(out))

def redact_text(text):
 # Encoded credential-like values are omitted whole rather than guessed/decoded into output.
 if decoded(text)!=text and sensitive(text):return MARKER
 for p in PATTERNS:text=p.sub(MARKER,text)
 text=DANGEROUS_HTML.sub('[REMOVED_UNSAFE_MARKUP]',text);text=EVENT_ATTR.sub('[REMOVED_UNSAFE_ATTRIBUTE]',text)
 text=URL_PATTERN.sub(lambda m:LINK_MARKER if url_problem(m.group().rstrip(').,;'))else m.group(),text)
 text=re.sub(r'^- Website:.*(?:'+re.escape(MARKER)+'|'+re.escape(LINK_MARKER)+r').*$', '- Website: Not provided (redacted unsafe source URL)',text,flags=re.M)
 return text

def scrub(obj):
 if isinstance(obj,dict):
  out={};removed=[]
  for k,v in obj.items():
   if k in['cached_content_file','raw_file','raw_profile_path']:continue
   urlfield=k.lower().endswith('url')or k.lower().endswith('_url')or k.lower()in['website','uri','href']
   if isinstance(v,str)and v and(CREDENTIAL_KEY.fullmatch(k)or urlfield and url_problem(v)):
    out[k]=None;removed.append(k)
   else:
    cleaned=scrub(v);out[k]=cleaned
    if cleaned!=v and isinstance(v,str):removed.append(k)
  if removed:
   out['publication_redactions']=sorted(set(out.get('publication_redactions',[])+removed))
   out['publication_redaction_note']='Unsafe credential-like/source-link content omitted without validation or use; other project facts retained.'
  return out
 if isinstance(obj,list):return[scrub(v)for v in obj]
 if isinstance(obj,str):return redact_text(obj)
 return obj
