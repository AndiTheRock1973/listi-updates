"""Unit-aware litre prices. Millilitres are never encoded as grams."""
from decimal import Decimal,ROUND_HALF_UP
import hashlib,re
import pantry
from product_types import normal,caption,brand

def details(raw):
 t=normal(raw).replace('\u2009',' ').replace('\u200d','')
 units=re.findall(r'(?:1\s*l\s*=|l[- ]preis)\s*(\d{1,3}[.,]\d{2})',t)
 units+=re.findall(r'€\s*(\d{1,3}[.,]\d{2})\s*/\s*1\s*l\b',t)
 stripped=re.sub(r'\(?1\s*l\s*=\s*\d{1,3}[.,]\d{2}\)?|l[- ]preis\s*\d{1,3}[.,]\d{2}|€\s*\d{1,3}[.,]\d{2}\s*/\s*1\s*l\b',' ',t)
 pattern=r'(\d{1,5}(?:[.,]\d{1,3})?)\s*[- ]?(ml|l)\b'
 pack=re.search(r'(\d{1,2})\s*[x×]\s*'+pattern,stripped)
 quantities=re.findall(pattern,stripped)
 if len(quantities)!=1:return None
 number,unit=quantities[0]
 if unit=='ml' and re.fullmatch(r'\d{1,2}\.\d{3}',number):number=number.replace('.','')
 size=Decimal(number.replace(',','.'))*(1000 if unit=='l' else 1)
 if pack:size*=int(pack[1])
 if size!=int(size) or not 100<=size<=30000:return None
 if len(units)>1:return None
 return int(size),int(Decimal(units[0].replace(',','.'))*100) if units else None, bool(pack)

def money(word,ocr=False):
 if word.size<18 or word.confidence<70 or '%' in word.value:return None
 v=re.sub(r'[^0-9.,]','',word.value)
 if re.fullmatch(r'\d{1,3}[.,]\d{2}',v):return int(Decimal(v.replace(',','.'))*100)
 if ocr and re.fullmatch(r'\d{2,4}',v):return int(v)
 return None

def offer(raw,words,source,bounds,page,sha,box=None,ocr=False,price_words=None):
 import collect as c
 raw=re.sub(r'(?<=[A-Za-zäöüÄÖÜ])-\n(?=[a-zäöü])','',caption(raw));cat=c.category_of(raw)
 if cat not in {'milk','cola','pasta_sauce'}:return None
 parsed=details(raw)
 if parsed is None:return None
 ml,unit,pack=parsed
 # With no separate unit price, only a single explicitly labelled 1 l pack is supported.
 if unit is None and (ml!=1000 or pack or ocr):return None
 candidates=[]
 for w in (price_words if price_words is not None else words):
  p=money(w,ocr)
  if p is None or not 10<=p<=10000:continue
  if box:
   x,y,x1,y1=box
   if not x-25<=w.x0<=x1+75:continue
   if not (y-15<=w.y0<=y1+115 or y-20<=w.y1<=y+10 or(source.market=='MÜLLER' and y-100<=w.y0<y)):continue
  if unit is not None:
   calculated=int((Decimal(p)*1000/ml).quantize(Decimal(1),rounding=ROUND_HALF_UP))
   if abs(calculated-unit)>1:continue
  key=(p,round(w.x0),round(w.y0))
  if not any(v[0]==key for v in candidates):candidates.append((key,w,p))
 if len(candidates)!=1:return None
 _,price_word,price=candidates[0]
 if box:
  x,y,x1,y1=box
  area=(min(x,price_word.x0)-12,min(y,price_word.y0)-35,max(x1,price_word.x1)+12,max(y1,price_word.y1)+12)
  panel=[w for w in words if c.in_rect(w,area)]
 else:panel=words
 if re.search(r'\bapp\b|coupon|normalpreis|bonus|punkte|gutschein|cashback|\bplus\b|ihr\s*preis|mit\s*der|kundenkarte',normal(raw+' '+' '.join(w.value for w in panel))):return None
 label=[]
 for line in raw.splitlines():
  if re.search(r'\d\s*[- ]?(?:ml|l)\b',line,re.I):break
  label.append(line.strip())
 if not label:return None
 title=' '.join(label).strip(' *.,');variants,attributes=pantry.tags(raw,cat);start,end=bounds
 identity=f'{source.market}|{normal(title)}|{ml}ml|{start}|{price}'
 evidence={'pdfSha256':sha,'caption':re.sub(r'\s+',' ',raw)[:800]}
 if unit is not None:evidence['printedUnitPriceCents']=unit
 else:evidence.update({'printedQuantity':'1 l','priceLine':f'{price/100:.2f}'})
 result={'id':hashlib.sha256(identity.encode()).hexdigest()[:24],'market':source.market,'location':source.location,
  'title':title,'brand':brand(raw,cat),'category':cat,'variants':variants,'attributes':attributes,
  'priceCents':price,'quantityUnit':'ml','quantityMl':ml,'validFrom':start.isoformat(),'validTo':end.isoformat(),
  'pdfPage':page,'pdfUrl':source.pdf_url,'sourceUrl':source.source_url,'verified':True,
  'verificationMethod':('ocr_volume_crosscheck' if ocr else 'pdf_volume_crosscheck') if unit is not None else 'pdf_1l_price',
  'evidence':evidence,'note':'Automatisch aus dem offiziellen Prospekt erfasst. Sorte, Inhalt, Gültigkeit und Filialverfügbarkeit prüfen.'}
 if 'pfand' in normal(raw) and 'pfandfrei' not in normal(raw):
  result['depositNote']='zzgl. Pfand; Höhe im Prospekt prüfen.'
  match=re.search(r'(?:zzgl\.?\s*|\+\s*)(\d{1,3}[.,]\d{2})\s*(?:€\s*)?pfand',normal(raw))
  if match:result['depositCents']=int(Decimal(match[1].replace(',','.'))*100)
 return result

def validate_volume(offer):
 from collect import cents
 if 'quantityGrams' in offer or offer['category'] not in {'milk','cola','pasta_sauce'}:raise ValueError('Volume/mass confusion')
 ml=offer.get('quantityMl');e=offer['evidence'];p=offer['priceCents']
 if type(ml) is not int or not 100<=ml<=30000:raise ValueError('Invalid volume')
 parsed=details(e['caption'])
 if parsed is None or parsed[0]!=ml:raise ValueError('Printed volume differs')
 if offer['verificationMethod']=='pdf_1l_price':
  if ml!=1000 or parsed[2] or e.get('printedQuantity')!='1 l' or cents(e.get('priceLine','0'))!=p:raise ValueError('1 l proof missing')
 elif offer['verificationMethod'] in {'pdf_volume_crosscheck','ocr_volume_crosscheck'}:
  expected=int((Decimal(p)*1000/ml).quantize(Decimal(1),rounding=ROUND_HALF_UP))
  if type(e.get('printedUnitPriceCents')) is not int or abs(expected-e['printedUnitPriceCents'])>1:raise ValueError('Litre price mismatch')
 else:raise ValueError('Incorrect volume method')
