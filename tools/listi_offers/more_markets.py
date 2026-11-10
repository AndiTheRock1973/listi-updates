"""Official live-edition resolvers and conservative native PDF field extraction."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import html
from pathlib import Path
import re
from urllib.parse import urljoin
import fitz
import collect as c
import product_types
import pantry
import pantry_fields
import staples
import staple_fields

ENTRY = {
 'ALDI SÜD': ('Alling · Gilchinger Straße 35', 'https://www.aldi-sued.de/prospekte'),
 'EDEKA': ('Eichenau · Hauptstraße 55', 'https://blaetterkatalog.edeka.de/SUEDBAYERN/NeukaufSued/index.html'),
 'REWE': ('Alling · Gilchinger Straße 33', 'https://www.rewe.de/angebote/alling/461921/rewe-gilchinger-str-33/'),
 'AEZ': ('Fürstenfeldbruck · City Point', 'https://aez.de/wochenangebot/'),
 'Netto': ('Puchheim · Benzstraße 38', 'https://www.netto-online.de/filialen/Puchheim/Benzstr-38/8342'),
 'MÜLLER': ('Puchheim · Dornierstraße 3', 'https://www.mueller.de/prospekte/'),
}


def unescape(s):
 return html.unescape(s.replace('\\/', '/').replace('\\u0026', '&'))


def range_in(text, year):
 # Explicit printed range, with the source metadata supplying an omitted year.
 clean = re.sub(r'\b(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|Mo\.|Di\.|Mi\.|Do\.|Fr\.|Sa\.|So\.)', '', text, flags=re.I)
 match = re.search(r'(?:g[üu]ltig\s+(?:vom|von)\s*)?(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(?:20\d{2})?\s*(?:–|—|-|bis)\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*((?:20)?\d{2})?', clean, re.I)
 if not match:return None
 end_year = int(match[5] or year)
 if end_year<100:end_year+=2000
 try:
  end = date(end_year, int(match[4]), int(match[3]))
  start_year = end_year - (int(match[2]) > end.month)
  start = date(start_year, int(match[2]), int(match[1]))
 except ValueError:return None
 if not 0 <= (end - start).days <= 6:return None
 return start, end


def page_ranges(text,year):
 clean=re.sub(r'\b(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|Mo\.|Di\.|Mi\.|Do\.|Fr\.|Sa\.|So\.)','',text,flags=re.I)
 pattern=r'(?:g[üu]ltig\s+(?:vom|von)\s*)?\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*(?:20\d{2})?\s*(?:–|—|-|bis)\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*(?:(?:20)?\d{2})?'
 return {value for hit in re.finditer(pattern,clean,re.I) if (value:=range_in(hit[0],year)) is not None}


def current(source, today):
 if not source.start <= today <= source.end:raise ValueError('No current retailer edition')
 return source


def resolve(market, today):
 location, entry = ENTRY[market]
 if market=='Netto':
  from netto_source import resolve_netto
  return resolve_netto(today)
 if market == 'EDEKA':
  xml = c.text(urljoin(entry, 'blaetterkatalog/xml/catalog.xml'))
  start = date.fromisoformat(re.search(r'<from>([^<]+)', xml)[1])
  end = date.fromisoformat(re.search(r'<to>([^<]+)', xml)[1])
  return current(c.Source(market, location, urljoin(entry, 'blaetterkatalog/pdf/complete.pdf'), entry, start, end), today)
 if market == 'REWE':
  # Public official embed endpoint linked by the local REWE Alling offer page.
  week = today.isocalendar().week
  viewer = f'https://services.publitas.com/rewe/publications?week={week}&wwident=461921&feature=download'
  payload = c.text(viewer)
  link = re.search(r'"downloadPdfUrl"\s*:\s*"([^"]+)"', payload)
  valid = re.search(r'(\d{1,2})\. Woche (20\d{2})\. Gültig ab (\d{2})\.(\d{2})\.(20\d{2})',html.unescape(payload))
  if not link or not valid or '461921' not in link[1]:raise ValueError('REWE Alling edition metadata missing')
  start=date(int(valid[5]),int(valid[4]),int(valid[3]))
  if start!=date.fromisocalendar(int(valid[2]),int(valid[1]),1):raise ValueError('REWE week mismatch')
  # Current weekly publication, conservatively bounded by Saturday, not extended indefinitely.
  return current(c.Source(market,location,unescape(link[1]),entry,start,start+timedelta(days=5)),today)
 page = c.text(entry)
 if market == 'ALDI SÜD':
  match = re.search(r'Prospekt der aktuellen Woche[^<]*</[^>]+>[\s\S]{0,600}?href=["\']([^"\']+)', page, re.I)
  if not match:raise ValueError('Current ALDI viewer missing')
  viewer = urljoin(entry, unescape(match[1])); payload = c.text(viewer)
  link = re.search(r'"downloadPdfUrl"\s*:\s*"([^"]+)"', payload)
  description = re.search(r'<meta\s+name="description"\s+content="([^"]+)', payload)
  dates = re.findall(r'(\d{2})\.(\d{2})\.(20\d{2})', description[1] if description else '')
  dates = sorted({date(int(y), int(m), int(d)) for d,m,y in dates})
  if not link or len(dates)<2 or (dates[-1]-dates[0]).days>6:raise ValueError('ALDI dates or PDF missing')
  return current(c.Source(market,location,unescape(link[1]),viewer,dates[0],dates[-1]),today)
 if market == 'AEZ':
  selection=re.search(r'href=["\']([^"\']+)["\'][^>]*aria-label=["\']FFB-City Point["\']',page,re.I)
  if not selection:raise ValueError('AEZ City Point selection missing')
  viewer=urljoin(entry,unescape(selection[1]));payload=c.text(viewer)
  link=re.search(r'href=["\']([^"\']*AEZ_KW(\d{1,2})_(\d{2})\.pdf)["\']',payload,re.I)
  if not link:raise ValueError('AEZ PDF edition missing')
  start=date.fromisocalendar(2000+int(link[3]),int(link[2]),1)
  return current(c.Source(market,location,urljoin(viewer,unescape(link[1])),viewer,start,start+timedelta(days=5)),today)
 if market == 'MÜLLER':
  links=list(dict.fromkeys(re.findall(r'https://dam\.prod\.ecom\.mueller\.de/[^"<>\s\\]+\.pdf',page)))
  links=[u for u in links if 'drogerie' in u.lower()]
  if len(links)!=1:raise ValueError('Unambiguous Müller drugstore PDF missing')
  # Full validity must also be confirmed on the downloaded PDF cover.
  ranges=[range_in(t,today.year) for t in re.findall(r'Unsere aktuellen Angebote vom ([^<]+)',page)]
  ranges=list(dict.fromkeys(r for r in ranges if r and r[0]<=today<=r[1]))
  if len(ranges)!=1:raise ValueError('Müller validity missing or ambiguous')
  return c.Source(market,location,links[0],entry,*ranges[0])
 raise ValueError('Unsupported market')


def clean(value):
 return re.sub(r'\s+',' ',value.replace('\u00ad','').replace('\u200d','').replace('\u2009',' ')).strip()


def canonical_caption(raw):
 raw=product_types.caption(raw)
 raw=re.sub(r'(?<=[A-Za-zäöüÄÖÜ])-\n(?=[a-zäöü])', '', raw)
 s=clean(raw)
 # Omit substitute products, prepared foods and special pasta instead of suggesting them as normal staples.
 if c.category_of(raw) not in pantry.CATEGORIES and re.search(r'meersalz|gesalzen|protein|mischstreich|rama\b|frische? pasta|pastagericht|butter des waldes|zur pasta|sosse|sauc',c.normalized(s)):return None
 amounts=re.findall(r'(?<![\d.,/])(\d{1,4}(?:\.\d{3})?)\s*[- ]?g\b',s,re.I)
 # Printed final total after a multiplication (e.g. 20 x 7 g = 140-g-Packung).
 product=re.search(r'(\d+)\s*x\s*(\d+)\s*g\s*=\s*(\d+)\s*-?g',s,re.I)
 if product:
  if int(product[1])*int(product[2])!=int(product[3]):return None
  amounts=[product[3]]
 if len(amounts)!=1:return None
 grams=int(amounts[0].replace('.',''))
 units=re.findall(r'(?:1\s*kg\s*=|kg[- ]Preis)\s*(\d{1,3}[.,]\d{2})(?![\d.,/])',s,re.I)
 if not units:units=re.findall(r'€\s*(\d{1,3}[.,]\d{2})\s*/\s*1\s*kg',s,re.I)
 if not units:units=re.findall(r'(\d{1,3}[.,]\d{2})\s*/\s*kg\b',s,re.I)
 if len(units)!=1 or re.search(r'\d[.,]\d{2}\s*(?:/|bzw\.|-)\s*\d',s):return None
 unit=c.cents(units[0])
 price=int((Decimal(unit)*grams/1000).quantize(Decimal(1),rounding=ROUND_HALF_UP))
 if not 50<=grams<=2500 or not 10<=price<=5000:return None
 if abs(round(price*1000/grams)-unit)>1:return None
 # Keep product wording, replace only pack/unit section by a canonical equivalent for the shared checker.
 lines=raw.splitlines()
 label=[]
 for line in lines:
  if re.search(r'\d\s*[- ]?(?:g|kg)\b|\bje\s*\d|kg[- ]Preis',clean(line),re.I):break
  label.append(clean(line))
 if not label or c.normalized(label[0]) in {'pasta','butter','kaffee','nudeln'}:return None
 canonical='\n'.join(label)+f'\nje {grams} g (1 kg = {unit/100:.2f})'
 return canonical,price,grams


def price_lines(page):
 result=[]
 for block in page.get_text('dict')['blocks']:
  for line in block.get('lines',[]):
   spans=line['spans']; value=clean(''.join(s['text'] for s in spans))
   if max((s['size'] for s in spans),default=0)<18:continue
   match=re.fullmatch(r'(?:je\s*)?(\d{1,3}[.,]\d{2})\s*[*€]?',value,re.I)
   if match:result.append(c.Word(match[1],*line['bbox'],max(s['size'] for s in spans)))
 return result


def kilogram_offer(raw, panel, price, source, bounds, page, sha):
 # For an explicitly labelled 1 kg package, the large package price is the kg price.
 # No fictional independently printed unit price is recorded for this case.
 caption=clean(raw)
 quantities=re.findall(r'(?<![\d.,/])(\d{1,4}(?:\.\d{3})?)\s*(kg|g)\b',caption,re.I)
 if len(quantities)!=1:return None
 number,unit=quantities[0]
 grams=int(number.replace('.',''))*(1000 if unit.lower()=='kg' else 1)
 if grams!=1000:return None
 if re.search(r'\bapp\b|coupon|normalpreis|treuepunkte|ihr\s*preis|mit\s*der|kundenkarte',c.normalized(' '.join(w.value for w in panel))):return None
 category=c.category_of(raw)
 if category!='coffee':return None
 price_cents=c.cents(price.value)
 if not 10<=price_cents<=5000:return None
 title=[]
 for line in raw.splitlines():
  if re.search(r'\d\s*(?:kg|g)\b',clean(line),re.I):break
  title.append(clean(line))
 if not title:return None
 brand=title[0];title=' '.join(title)
 body=c.normalized(raw)
 variants=[]
 if re.search(r'\bbohnen\b|kaffeebohnen',body):variants.append('beans')
 if 'gemahlen' in body:variants.append('ground')
 if 'espresso' in body:variants.append('espresso')
 start,end=bounds
 identity=f'{source.market}|{c.normalized(title)}|1000|{start}|{price_cents}'
 return {'id':hashlib.sha256(identity.encode()).hexdigest()[:24], 'market':source.market,
  'location':source.location,'title':title,'brand':brand,'category':category,'variants':variants,
  'attributes':[],'priceCents':price_cents,'quantityGrams':1000,'validFrom':start.isoformat(),
  'validTo':end.isoformat(),'pdfPage':page,'pdfUrl':source.pdf_url,'sourceUrl':source.source_url,
  'verified':True,'verificationMethod':'pdf_1kg_price',
  'evidence':{'pdfSha256':sha,'caption':caption,'printedQuantity':number+' '+unit,'priceLine':price.value},
  'note':'Automatisch aus dem offiziellen Prospekt erfasst. Ausgewiesene 1-kg-Packung: Packungspreis entspricht dem Kilopreis. Sorte, Vorrat und Filialverfügbarkeit im Prospekt prüfen.'}


def counter_offer(raw, panel, price, source, bounds, page, sha):
 raw=product_types.caption(raw)
 if c.category_of(raw) not in {'beef','sausage','cheese','poultry','pork'}:return None
 quantities=re.findall(r'(?<![\d.,/])(\d+)\s*g\b',clean(raw),re.I)
 if quantities!=['100']:return None
 if re.search(r'\bapp\b|coupon|normalpreis|treuepunkte|ihr\s*preis|mit\s*der|kundenkarte',c.normalized(' '.join(w.value for w in panel))):return None
 price_cents=c.cents(price.value)
 if not 10<=price_cents<=5000:return None
 label=[]
 for line in raw.splitlines():
  if re.search(r'\d\s*g\b',clean(line),re.I):break
  label.append(clean(line))
 if not label:return None
 title=' '.join(label);start,end=bounds
 category=c.category_of(raw)
 variants,attributes=(product_types.tags(raw,'beef') if category=='beef' else (staples.tags(raw,category) if category in staples.CATEGORIES else pantry.tags(raw,category)))
 if re.search(r'\bbio\b',c.normalized(raw)):attributes.append('bio')
 identity=f'{source.market}|{c.normalized(title)}|100|{start}|{price_cents}'
 return {'id':hashlib.sha256(identity.encode()).hexdigest()[:24],'market':source.market,
  'location':source.location,'title':title,'brand':product_types.brand(raw,category),
  'category':category,'variants':variants,'attributes':attributes,'priceCents':price_cents,
  'quantityGrams':100,'validFrom':start.isoformat(),'validTo':end.isoformat(),'pdfPage':page,
  'pdfUrl':source.pdf_url,'sourceUrl':source.source_url,'verified':True,'verificationMethod':'pdf_100g_price',
  'evidence':{'pdfSha256':sha,'caption':clean(raw),'printedQuantity':'100 g','priceLine':price.value},
  'note':'Automatisch aus dem offiziellen Prospekt erfasst. Preis je 100 g, kein fester Packungspreis. Produktart, Sorte, Bedingungen und Filialverfügbarkeit im Prospekt prüfen.'}


def penny_cover_banana(blocks, words, prices, source, bounds, page, sha, width, height):
 """Known PENNY cover grid: captions below pictures, prices above them.

 Confirm all three neighbouring anchors before associating the detached fruit
 price. No relaxation of the general nearest-caption rule and no fixed price.
 """
 if source.market!='PENNY' or page!=1 or not 450<=width<=500 or not 810<=height<=870:return None
 def unique(predicate):
  found=[b for b in blocks if predicate(b)]
  return found[0] if len(found)==1 else None
 banana=unique(lambda b: re.fullmatch(r'chiquita\s+bananen[*®]?\s+je\s+kg',c.normalized(b['text']).strip()) is not None)
 coffee=unique(lambda b:'dallmayr' in c.normalized(b['text']) and 'prodomo' in c.normalized(b['text']))
 chicken=unique(lambda b:'muhlenhof' in c.normalized(b['text']) and re.search(r'frische\s+hahnchen[- ]schenkel',c.normalized(b['text'])) is not None)
 if not banana or not coffee or not chicken:return None
 bx,by,bx1,by1=banana['bbox'];cx,cy,cx1,cy1=coffee['bbox'];hx,hy,hx1,hy1=chicken['bbox']
 if not (.56<=bx/width<=.66 and .34<=cx/width<=.40 and .73<=hx/width<=.80 and
         .57<=by/height<=.63 and abs(by1-cy1)<3 and abs(by1-hy1)<3):return None
 def one_price(xmin,xmax,ymin,ymax):
  found=[p for p in prices if xmin<=p.x0/width<=xmax and ymin<=p.y0/height<=ymax]
  return found[0] if len(found)==1 else None
 fruit_price=one_price(.82,.89,.17,.24)
 coffee_price=one_price(.56,.67,.17,.24)
 chicken_price=one_price(.82,.89,.49,.56)
 if not fruit_price or not coffee_price or not chicken_price:return None
 if abs(fruit_price.y0-coffee_price.y0)>4 or abs(fruit_price.x0-chicken_price.x0)>4:return None
 # Unit-price anchors establish this specific grid instead of guessing across columns.
 coffee_mass=staple_fields.mass_details(coffee['text']);chicken_mass=staple_fields.mass_details(chicken['text'])
 for item,price in [(coffee_mass,coffee_price),(chicken_mass,chicken_price)]:
  if not item or item[1] is None:return None
  if abs(round(c.cents(price.value)*1000/item[0])-item[1])>1:return None
 panel=' '.join(w.value for w in words if fruit_price.x0-20<=w.x0<=fruit_price.x1+20 and
                fruit_price.y0-40<=w.y0<=fruit_price.y1+15)
 if re.search(r'\bapp\b|coupon|kundenkarte|normalpreis|treuepunkte|mit\s*der|nur\s+(?:am|mit)',c.normalized(panel)):return None
 price=c.cents(fruit_price.value)
 if not 10<=price<=5000:return None
 raw=banana['text'];title='CHIQUITA Bananen';start,end=bounds
 variants,attrs=staples.tags(raw,'fruit')
 return {'id':hashlib.sha256(f'{source.market}|{staples.text(title)}|1000|mass|{start}|{price}'.encode()).hexdigest()[:24],
  'market':source.market,'location':source.location,'title':title,'brand':'Chiquita','category':'fruit',
  'variants':variants,'attributes':attrs,'priceCents':price,'quantityGrams':1000,
  'validFrom':start.isoformat(),'validTo':end.isoformat(),'pdfPage':page,'pdfUrl':source.pdf_url,
  'sourceUrl':source.source_url,'verified':True,'verificationMethod':'pdf_1kg_price',
  'evidence':{'pdfSha256':sha,'caption':clean(raw),'printedQuantity':'1000 g','priceLine':fruit_price.value,
              'layout':'penny-cover-three-caption-grid'},
  'note':'Automatisch aus dem offiziellen Prospekt erfasst. Preis je 1 kg loser Ware, kein fester Packungspreis. Zeitraum und Filialverfügbarkeit prüfen.'}


def native_collect(pdf:Path, source:c.Source, pages=None):
 sha=hashlib.sha256(pdf.read_bytes()).hexdigest();offers=[]
 with fitz.open(pdf) as document:
  if not 1<=len(document)<=150:raise ValueError('Unexpected page count')
  cover=document[0].get_text()
  bounds=range_in(cover,source.end.year)
  if source.market=='REWE':
   # The PDF is labelled with the same ISO week and Monday as its official local viewer.
   expected=f'{source.start.day:02d}.{source.start.month:02d}.{source.start.year}'
   if expected not in cover:raise ValueError('REWE PDF validity mismatch')
   bounds=(source.start,source.end)
  if not bounds:raise ValueError('PDF cover validity not explicit')
  if bounds[0]<source.start or bounds[1]>source.end:raise ValueError('PDF and source dates disagree')
  for number,page in enumerate(document,1):
   if pages and number not in pages:continue
   blocks,words=c.native_page(page); prices=price_lines(page)
   header=' '.join(b['text'] for b in blocks if b['bbox'][1]<55)
   if source.market=='REWE':
    # The already validated publication Monday is not a later-day product restriction.
    printed=source.start.strftime('%d.%m.%Y')
    header=re.sub(r'G(?:ü|ue|u)ltig\s+ab\s+'+re.escape(printed), '', header, flags=re.I)
   if source.market in {'Lidl','Netto'}:
    # Lidl prints the complete period in a page header/footer.
    # Pages without it (editorial, online specials) do not inherit a guessed week.
    footer=' '.join(b['text'] for b in blocks if b['bbox'][1]<55 or b['bbox'][1]>page.rect.height-115)
    periods=page_ranges(footer,source.end.year)
    if len(periods)!=1:continue
    page_bounds=periods.pop()
   else:page_bounds=c.page_dates(header,source) or bounds
   if page_bounds[0]<bounds[0] or page_bounds[1]>bounds[1]:continue
   starts=re.findall(r'\bab\s+(?:Mo|Di|Mi|Do|Fr|Sa|So)\.\s*(\d{1,2})\.(\d{1,2})\.',header,re.I)
   if starts:
    if len(set(starts))!=1:continue
    d,m=starts[0]
    start=date(source.start.year,int(m),int(d))
    if not bounds[0]<=start<=bounds[1]:continue
    page_bounds=(start,bounds[1])
   elif source.market=='ALDI SÜD' and not c.page_dates(header,source):continue
   elif re.search(r'\bab\b.{0,25}\d{1,2}\.\d{1,2}\.',header,re.I):continue
   if re.search(r'\bnur\s+(?:am|mit|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)|coupon|treuepunkte',header,re.I):continue
   cover_produce=penny_cover_banana(blocks,words,prices,source,page_bounds,number,sha,page.rect.width,page.rect.height)
   if cover_produce:offers.append(cover_produce)
   for block in blocks:
    raw=block['text']
    if source.market in {'Lidl','Netto'} and re.search(r'stollen|kasespatzle|paniert|roulade|\boder\b',c.normalized(raw)):
     continue  # Prepared/alternative product groups are not a generic grocery match.
    if source.market=='EDEKA' and c.category_of(raw) in {'beef','sausage','cheese','poultry','pork'} and '*' in raw:
     if 'nicht in allen markten' in c.normalized(clean(page.get_text())):
      continue  # Local butcher-counter applicability is not established by this regional flyer.
    if len(raw)>800 or c.category_of(raw) is None:continue
    if c.category_of(raw) in staples.CATEGORIES:
     found=staple_fields.offer(raw,words+prices,source,page_bounds,number,sha,block['bbox'],prices)
     if found:
      offers.append(found)
      continue
    if c.category_of(raw) in pantry.CATEGORIES:
     found=pantry_fields.offer(raw, words+prices, source, page_bounds, number, sha, box=block['bbox'],price_words=prices)
     if found:
      offers.append(found)
      continue
    parsed=canonical_caption(raw)
    if parsed:
     caption,expected,_=parsed
    else:
     caption,expected=None,None
    x0,y0,x1,y1=block['bbox']
    candidates=[p for p in prices if (expected is None or c.cents(p.value)==expected)
                and x0-25<=p.x0<=x1+75
                and (y0-(100 if source.market=='MÜLLER' else 15)<=p.y0<=y1+115
                     or y0-20<=p.y1<=y0+10)
                and (source.market!='MÜLLER' or p.y0<y0)]
    if len(candidates)!=1:continue
    price=candidates[0]
    # Conditions must be in the same product area; neighboring columns aren't product conditions.
    rect=(min(x0,price.x0)-12,min(y0,price.y0)-35,max(x1,price.x1)+12,max(y1,price.y1)+12)
    panel=[w for w in words if c.in_rect(w,rect)]+[price]
    offer=(c.offer_from(caption,panel,source,page_bounds,number,sha,'pdf_text_crosscheck') if parsed
           else (kilogram_offer(raw,panel,price,source,page_bounds,number,sha)
                 or counter_offer(raw,panel,price,source,page_bounds,number,sha)))
    if offer:
     offer['evidence']['caption']=clean(raw)[:600]
     if offer['category'] in (pantry.CATEGORIES | staples.CATEGORIES):
      classifier=staples if offer['category'] in staples.CATEGORIES else pantry
      offer['variants'],offer['attributes']=classifier.tags(offer['evidence']['caption'],offer['category'])
     offers.append(offer)
 return offers
