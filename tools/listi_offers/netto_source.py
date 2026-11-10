"""Read-only official Netto Puchheim reference edition. Never changes store state."""
from datetime import date
import json
import math
import re
from urllib.error import HTTPError
from urllib.parse import urlparse, parse_qs
import collect as c

BRANCH='https://www.netto-online.de/filialen/puchheim/benzstr-38/8342'

class NettoHTTPError(HTTPError):
 def __init__(self,error,stage):
  super().__init__(error.url,error.code,error.msg,error.hdrs,error.fp)
  self.stage=stage
 def __str__(self):
  u=urlparse(self.url)
  return f'Netto {self.stage}: HTTP {self.code} ({u.hostname}{u.path})'


def read_text(url,stage):
 try:return c.text(url)
 except HTTPError as error:raise NettoHTTPError(error,stage) from error


def resolve_netto(today):
 import more_markets as m
 page=read_text(BRANCH,'Filialseite')
 confirmed=False
 def walk(v):
  nonlocal confirmed
  if isinstance(v,list):
   for row in v:walk(row)
  elif isinstance(v,dict):
   a,g=v.get('address'),v.get('geo')
   if isinstance(a,dict) and isinstance(g,dict):
    street=c.normalized(str(a.get('streetAddress',''))).replace('strasse','str').replace('str.','str')
    street=re.sub(r'[^a-z0-9]','',street)
    try:lat,lng=float(g['latitude']),float(g['longitude'])
    except (ValueError,TypeError,KeyError):lat,lng=0,0
    if str(a.get('postalCode'))=='82178' and street=='benzstr38' and math.isfinite(lat) and math.isfinite(lng) and abs(lat-48.173901)<.001 and abs(lng-11.367066)<.001:confirmed=True
   for row in v.values():walk(row)
 for raw in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',page):
  try:walk(json.loads(raw))
  except (ValueError,TypeError):continue
 if not confirmed:raise ValueError('Netto reference branch address not confirmed')
 links={m.unescape(x) for x in re.findall(r'href=["\'](https://wochenprospekt\.netto-online\.de/[^"\']+)["\']',page)
        if parse_qs(urlparse(m.unescape(x)).query).get('storeid')==['8342']}
 paths={urlparse(x).path for x in links}
 if len(paths)!=1:raise ValueError('Netto reference publication ambiguous')
 path=paths.pop();entry='https://wochenprospekt.netto-online.de'+path+'?storeid=8342'
 book=read_text(entry,'Wochenprospekt');slug=path.strip('/')
 match=re.fullmatch(r'([a-z]+\d+)(?:_[a-z]+)*?(?:_(\d+))?',slug,re.I)
 if not match or "routingBaseUrl: 'https://scripts.publitas.com/netto-online/custom-routing'" not in book:raise ValueError('Netto public routing changed')
 key=match[1]+('_'+match[2] if match[2] else '')
 routes=json.loads(read_text('https://scripts.publitas.com/netto-online/custom-routing/'+key+'.json','Regionalzuordnung'))
 mapped=routes.get('8342')
 target=mapped if isinstance(mapped,str) and mapped!=slug else slug+'_sid8342'
 if mapped!=slug:
  if not re.fullmatch(r'[a-zA-Z0-9_-]+',target):raise ValueError('Netto route invalid')
  candidate='https://wochenprospekt.netto-online.de/'+target+'/?storeid=8342'
  try:
   alternate=read_text(candidate,'Optionale Filialausgabe')
   if 'name="asset-root"' not in alternate:raise ValueError('Netto mapped publication missing')
   entry,book=candidate,alternate
  except HTTPError as error:
   if mapped is not None or error.code!=404:raise
 # Explicit printed current period in the viewer metadata, not a guessed week.
 plain=m.unescape(book)
 match=re.search(r'(\d{1,2})\.(\d{1,2})\.\s*[–-]\s*(?:Samstag\s*)?(\d{1,2})\.(\d{1,2})\.(\d{2,4})',plain)
 if not match:raise ValueError('Netto edition dates missing')
 year=int(match[5]);year=year+2000 if year<100 else year
 end=date(year,int(match[4]),int(match[3]));start=date(year-(int(match[2])>end.month),int(match[2]),int(match[1]))
 pdf=re.search(r'"downloadPdfUrl"\s*:\s*"([^"]+)"',book)
 if not pdf:raise ValueError('Netto PDF missing')
 pdf=m.unescape(pdf[1]);u=urlparse(pdf)
 if u.scheme!='https' or u.netloc!='view.publitas.com' or not re.fullmatch(r'/100989/\d+/pdfs/[a-f0-9-]{36}\.pdf',u.path):raise ValueError('Netto PDF publisher mismatch')
 if not 0<=(end-start).days<=6:raise ValueError('Netto edition period invalid')
 return m.current(c.Source('Netto','Puchheim · Benzstraße 38',pdf,entry,start,end),today)
