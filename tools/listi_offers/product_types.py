"""High precision product categories. Rejected near-matches must not fall through."""
import re
import unicodedata


def normal(text):
 text=text.replace('\u00ad','').replace('ß','ss')
 return ''.join(ch for ch in unicodedata.normalize('NFKD',text) if not unicodedata.combining(ch)).lower()


def category_extra(raw):
 text=normal(raw)
 if re.search(r'toast|american\s+sandwich|vollkorn\s+sandwich',text):
  if re.search(r'toaster|toastschinken|sandwichmaker|schinken|salami|kaese|kase|pizza|aufstrich|creme|nutella|zwieback|broetchen|brotchen|buns|burger|hamburger|hotdog|knackebrot|gefullt|belegt|sandwich.*(?:chicken|hahnchen)',text):return 'reject'
  lines=text.splitlines()
  if len(lines)>1 and re.fullmatch(r'\s*golden\s*toast\s*',lines[0]):text='\n'.join(lines[1:])
  if re.search(r'\b(?:(?:butter|vollkorn|weizen|sandwich|korner)\s*[- ]?)?toast(?:brot)?\b|\bamerican\s+sandwich\b|\bvollkorn\s+sandwich\b',text):return 'toast'
  return 'reject'
 if re.search(r'rind|jungbullen|roastbeef|rumpsteak|entrecote',text):
  if re.search(r'schwein|gemischt|halb\s+und\s+halb|wurst|salami|aufschnitt|schinken|suppe|sauce|sosse|salat|lasagne|bolognese|burger|cevapcici|frikadell|hacksteak|pulled|gegart|gebraten|fertig|eintopf|konserve|\bdose\b|im\s+glas|erhitzen|mikrowelle|gewurz|gewuerz|spiess|nudeln|pasta|huhn|hahnchen|geflugel|lamm|wild|wein|rebsorte|flasche|versch\.?\s*gewichte|z\.?\s*b\.?\s*\d',text):return 'reject'
  if re.search(r'\brinder?\b|\brinder[-\s]*(?:hack(?:fleisch)?|gulasch|steaks?|huftsteaks?|braten|rouladen|filet)\b|\brindfleisch\b|\bjungbullen[-\s]*steaks?\b|\b(?:rumpsteak|roastbeef|entrecote)\b',text):return 'beef'
  return 'reject'
 return None


def tags(raw, category):
 text=normal(raw);variants=[];attributes=[]
 if category=='toast':
  if re.search(r'butter[-\s]*toast',text):variants.append('butter')
  if re.search(r'vollkorn',text):variants.append('wholegrain');attributes.append('wholegrain')
  if re.search(r'weizen[-\s]*toast|weiss(?:brot|toast)',text):variants.append('white')
 if category=='beef':
  if re.search(r'hack(?:fleisch)?',text):variants.append('mince')
  elif re.search(r'gulasch',text):variants.append('stew')
  elif re.search(r'rouladen',text):variants.append('roulade')
  else:
   if re.search(r'steak|entrecote',text):variants.append('steak')
   if re.search(r'filet',text):variants.append('fillet')
   if 'rumpsteak' in text:variants.append('rump')
   if 'entrecote' in text:variants.append('entrecote')
   if 'huftsteak' in text:variants.append('hip')
   if 'jungbullen' in text:variants.append('youngbull')
   if 'roastbeef' in text:variants.append('roastbeef')
   if re.search(r'rinder[-\s]*braten|roastbeef',text):variants.append('roast')
  if 'fettreduziert' in text or re.search(r'\bmager',text):attributes.append('lean')
 return variants, attributes


def caption(raw):
 lines=raw.splitlines()
 while lines and (not lines[0].strip() or re.fullmatch(r'\s*\d{1,3}[.,]\d{2}\s*[*€]?\s*',lines[0])):lines.pop(0)
 return '\n'.join(lines)


def brand(raw, category):
 first=caption(raw).splitlines()[0].strip('* .')
 if category in {'toast','beef'} and (category_extra(first) in {'toast','beef','reject'} or re.fullmatch(r'frisch(?:e[rsn]?)?|irische|deutsche',normal(first))):
  return 'Ohne Markenangabe'
 return first
