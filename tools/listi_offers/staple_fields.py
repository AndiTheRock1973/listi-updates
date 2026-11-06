"""Additional units: explicit counts and kg/100g price bases, no invented packs."""
import hashlib,re
from decimal import Decimal,ROUND_HALF_UP
import staples
import pantry_fields
from product_types import brand,caption

def count_details(raw):
 t=staples.text(raw)
 units=re.findall(r'(?:1\s*(?:stuck|st\.)\s*=|stuck[- ]?preis)\s*(\d{1,3}[.,]\d{2})',t)
 t=re.sub(r'1\s*(?:stuck|st\.)\s*=\s*\d{1,3}[.,]\d{2}',' ',t)
 qty=re.findall(r'(?<!\d)(\d{1,2})\s*[- ]?(?:stuck|st\.|eier\b|er[- ]?(?:pack|schachtel))',t)
 if len(set(qty))==1:count=int(qty[0])
 elif not qty and re.search(r'\bje\s*stuck\b|\bpro\s*stuck\b',t):count=1
 else:return None
 if not 1<=count<=60 or len(units)>1:return None
 return count,int(Decimal(units[0].replace(',','.'))*100) if units else None

def mass_details(raw):
 t=staples.text(raw)
 unit=re.findall(r'(?:1\s*kg\s*=|kg[- ]preis)\s*(\d{1,3}[.,]\d{2})',t)
 if not unit:unit=re.findall(r'€\s*(\d{1,3}[.,]\d{2})\s*/\s*1\s*kg',t)
 t=re.sub(r'1\s*kg\s*=\s*\d{1,3}[.,]\d{2}|€\s*\d{1,3}[.,]\d{2}\s*/\s*1\s*kg',' ',t)
 vals=re.findall(r'(?<![\d.,])(\d{1,4}(?:[.,]\d{1,3})?)\s*[- ]?(kg|g)\b',t)
 # Loose produce/meat may explicitly say "je kg".
 if not vals and re.search(r'\bje\s*kg\b|\bpro\s*kg\b',t):return 1000,None,True
 if len(vals)!=1 or len(unit)>1:return None
 n,u=vals[0];n=n.replace('.','') if re.fullmatch(r'\d\.\d{3}',n) and u=='g' else n.replace(',','.')
 grams=Decimal(n)*(1000 if u=='kg' else 1)
 if grams!=int(grams) or not 50<=grams<=5000:return None
 return int(grams),int(Decimal(unit[0].replace(',','.'))*100) if unit else None,False

def offer(raw,words,source,bounds,page,sha,box,prices):
 import collect as c
 cat=staples.category(raw)
 if re.search(r'\bz\.\s*b\.|beispielgewicht',staples.text(raw)):return None
 if cat not in staples.CATEGORIES:return None
 # Cream may be sold by volume; delegate to the litre-aware verifier.
 if cat=='cream':
  v=pantry_fields.offer(raw,words,source,bounds,page,sha,box=box,price_words=prices)
  if v:return v
 counted=count_details(raw) if cat in {'eggs','bread','fruit','vegetables'} else None
 mass=mass_details(raw) if cat!='eggs' else None
 if counted and mass:return None
 if counted:
  qty,unit=counted;kind='count'
  if qty!=1 and unit is None:return None
 elif mass:
  qty,unit,loose=mass;kind='mass'
  if unit is None and qty not in {100,1000}:return None
  if qty==100 and unit is None and cat not in {'poultry','pork'}:return None
 else:return None
 x,y,x1,y1=box;candidates=[]
 for w in prices:
  p=pantry_fields.money(w)
  if p is None or not 10<=p<=5000:continue
  if not(x-25<=w.x0<=x1+75 and(y-15<=w.y0<=y1+115 or y-20<=w.y1<=y+10)):continue
  factor=1 if kind=='count' else 1000
  base=int((Decimal(p)*factor/qty).quantize(Decimal(1),rounding=ROUND_HALF_UP))
  if unit is not None and abs(base-unit)>1:continue
  candidates.append((w,p))
 if len(candidates)!=1:return None
 w,price=candidates[0]
 panel=[z for z in words if c.in_rect(z,(min(x,w.x0)-12,min(y,w.y0)-35,max(x1,w.x1)+12,max(y1,w.y1)+12))]
 if re.search(r'\bapp\b|coupon|normalpreis|treuepunkte|\bplus\b|kundenkarte|ihr\s*preis|mit\s*der',staples.text(raw+' '+' '.join(z.value for z in panel))):return None
 label=[]
 for line in raw.splitlines():
  if re.search(r'\d\s*[- ]?(?:g|kg|stuck|st\.)\b|\bje\s*kg\b',staples.text(line)):break
  label.append(line.strip())
 title=re.sub(r'\s+',' ',caption('\n'.join(label))).strip(' *.,')
 if not title:return None
 variants,attrs=staples.tags(raw,cat);start,end=bounds
 method=('pdf_count_crosscheck' if unit is not None else 'pdf_piece_price') if kind=='count' else ('pdf_text_crosscheck' if unit is not None else ('pdf_100g_price' if qty==100 else 'pdf_1kg_price'))
 evidence={'caption':re.sub(r'\s+',' ',raw)[:800],'pdfSha256':sha}
 if unit is not None:evidence['printedUnitPriceCents']=unit
 else:evidence.update(printedQuantity=(f'{qty} Stück' if kind=='count' else f'{qty} g'),priceLine=f'{price/100:.2f}')
 result={'id':hashlib.sha256(f'{source.market}|{staples.text(title)}|{qty}|{kind}|{start}|{price}'.encode()).hexdigest()[:24],
  'market':source.market,'location':source.location,'title':title,'brand':brand(raw,cat),'category':cat,'variants':variants,'attributes':attrs,'priceCents':price,
  'validFrom':start.isoformat(),'validTo':end.isoformat(),'pdfPage':page,'pdfUrl':source.pdf_url,'sourceUrl':source.source_url,'verified':True,'verificationMethod':method,'evidence':evidence,
  'note':'Automatisch aus dem offiziellen Prospekt erfasst. Sorte, Menge, Zeitraum und Filialverfügbarkeit prüfen.'}
 if kind=='count':result.update(quantityUnit='piece',quantityCount=qty)
 else:result['quantityGrams']=qty
 if kind=='mass' and unit is None:
  result['note']+=' Preisbezug je '+('100 g' if qty==100 else '1 kg')+'; bei loser Ware kein fester Packungspreis.'
 return result

def validate_count(o):
 parsed=count_details(o['evidence']['caption']);qty=o.get('quantityCount');e=o['evidence']
 if 'quantityGrams' in o or 'quantityMl' in o or o['category'] not in {'eggs','bread','fruit','vegetables'} or type(qty) is not int or parsed is None or parsed[0]!=qty:raise ValueError('Count evidence mismatch')
 if o['verificationMethod']=='pdf_piece_price':
  if qty!=1 or e.get('printedQuantity')!='1 Stück' or int(Decimal(e.get('priceLine','0'))*100)!=o['priceCents']:raise ValueError('Piece price evidence missing')
 elif o['verificationMethod']=='pdf_count_crosscheck':
  unit=e.get('printedUnitPriceCents');base=int((Decimal(o['priceCents'])/qty).quantize(Decimal(1),rounding=ROUND_HALF_UP))
  if type(unit) is not int or parsed[1]!=unit or abs(unit-base)>1:raise ValueError('Piece unit price mismatch')
 else:raise ValueError('Count method mismatch')
