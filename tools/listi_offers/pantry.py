"""Additional grocery groups; no guessed sugar, species, form or milk fat."""
import re
from decimal import Decimal
from product_types import normal
CATEGORIES={'milk','pasta_sauce','cola','sausage','cheese'}

def category(raw):
 t=re.sub(r'\s+',' ',normal(raw))
 if re.search(r'reibe|schneider|aufschaumer|aufshaumer|milchkanne|milchtopf',t):return 'reject'
 ready=r'fertiggericht|pastagericht|nudelgericht|lasagne|pizza|burger|cordon|pfannengericht|gefullt|fullung|tortellini|ravioli|suppe|eintopf'
 sauce=bool(re.search(r'pasta[-\s]*sau|pasta[-\s]*so|nudel[-\s]*sau|nudel[-\s]*so|tomatensau|tomatenso|sauce\s+bolognese|bolognese[-\s]*sauce',t))
 if sauce:return 'reject' if re.search(ready,t) else 'pasta_sauce'
 if re.search(r'leberkase|fleischkase|kase[-\s]*(?:bockwurst|wiener)|kaswurst|kasewurst',t):return 'reject' if re.search(ready,t) else 'sausage'
 if re.search(r'kase|gouda|edamer|emmentaler|mozzarella|parmesan|parmigiano|grana\s+padano|feta|camembert|maasdamer|gorgonzola|burrata|pecorino',t):
  return 'reject' if re.search(ready+r'|kasekuchen|cheesecake|kasecracker|kasechips|tiefgefroren|ofenfrische|back[-\s]*camembert|ofenkase|kasewurst|kaswurst|kasesauce|kasesosse|cheeseburger|kasegeb[aä]ck|kasebr[oö]tchen',t) else 'cheese'
 if re.search(r'wurst|wurstchen|salami|lyoner|mortadella|cabanossi|salsiccia|bockwurst|weisswurst|\bwiener\b|\bfrankfurter\b|aufschnitt',t):
  return 'reject' if re.search(ready+r'|kaffee|caffe|melange|kranz|kuchen|schokolade|sauce|sosse|wurstbrot|schnitzel|wiener\s+art|wurstsalat|toastschinken',t) else 'sausage'
 if re.search(r'\bpesto\b',t):return 'reject' if re.search(ready,t) else 'pasta_sauce'
 if re.search(r'\b(?:coca[-\s]*)?cola\b|\bpepsi\b',t):
  return 'reject' if re.search(r'kaugummi|fruchtgummi|bonbon|sirup|likor|rum|vodka|whisky|cocktail',t) else 'cola'
 if 'milch' in t:
  if re.search(r'milch[-\s]*(?:brot|brotchen|mause|mousse|creme)|hafer|soja|mandel|kokos|pflanz|buttermilch|kaffee|caffe|kakao|schoko|milchreis|milchriegel|kondens|muttermilch|sauglings|milchpulver|milchdrink|milchgetrank|pudding|dessert|joghurt|quark|latte',t):return 'reject'
  if re.search(r'\bmilch\b|h[-\s]*milch|frischmilch|vollmilch|magermilch',t):return 'milk'
 return None

def tags(raw,cat):
 t=re.sub(r'\s+',' ',normal(raw));v=[];a=[]
 if re.search(r'\bbio\b',t):a.append('bio')
 if 'laktosefrei' in t or 'lactosefrei' in t:a.append('lactosefree')
 if 'glutenfrei' in t:a.append('glutenfree')
 if re.search(r'\bvegan|pflanzlich',t):a.append('vegan')
 if cat=='milk':
  if re.search(r'auch\s+laktosefrei|auch\s+lactosefrei',t):v.append('lactose_option')
  if re.search(r'h[-\s]*milch|haltbar',t):v.append('shelf')
  if re.search(r'frischmilch|frische.*milch|langer.*frisch',t):v.append('fresh')
  fats=re.findall(r'(?<!\d)([0-9](?:[.,][0-9])?)\s*%',t)
  # Explicit alternatives, e.g. 1,5/3,5 %.
  fats+=re.findall(r'([0-9][.,][0-9])\s*(?=/)',t)
  for f in set(fats):v.append('fat'+str(int(Decimal(f.replace(',','.'))*10)))
  if 'vollmilch' in t or any(x in v for x in ['fat35','fat38']):v.append('whole')
  if 'fettarm' in t or 'fat15' in v:v.append('lowfat')
  if 'magermilch' in t or 'fat1' in v:v.append('skim')
  if ('fresh' in v and 'shelf' in v):v.append('variety_options')
 if cat=='cola':
  if re.search(r'\bzero(?:sugar)?\b|zuckerfrei|ohne\s+zucker',t):v.append('zero')
  if re.search(r'\blight\b',t):v.append('light')
  if 'koffeinfrei' in t:v.append('caffeinefree')
 if cat=='pasta_sauce':
  for tag,regex in [('tomato',r'tomaten|tomato|napoli|arrabbiata'),('bolognese',r'bolognese'),('pesto',r'\bpesto\b'),('cream',r'sahne|carbonara')]:
   if re.search(regex,t):v.append(tag)
 if cat=='sausage':
  for tag,regex in [('salami',r'salami'),('bratwurst',r'bratwurst|salsiccia'),('leberwurst',r'leberwurst'),('wiener',r'wiener|frankfurter'),('weisswurst',r'weisswurst'),('mortadella',r'mortadella'),('lyoner',r'lyoner|fleischwurst'),('poultry',r'geflugel|pute|hahnchen'),('beef',r'rind'),('pork',r'schwein')]:
   if re.search(regex,t):v.append(tag)
 if cat=='cheese':
  for tag,regex in [('gouda',r'gouda'),('edamer',r'edamer'),('emmental',r'emmentaler'),('mozzarella',r'mozzarella'),('parmesan',r'parmesan|parmigiano'),('grana',r'grana\s+padano'),('feta',r'\bfeta\b'),('cream',r'frischkase'),('processed',r'schmelzkase'),('soft',r'camembert|brie|weichkase'),('slices',r'scheiben'),('grated',r'gerieben|reibekase'),('piece',r'\bam\s+stuck|vom\s+stuck')]:
   if re.search(regex,t):v.append(tag)
 return sorted(set(v)),sorted(set(a))
