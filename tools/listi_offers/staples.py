"""Everyday groceries: explicit types, no guessed ingredients or mixed meat."""
import re
from product_types import normal
CATEGORIES={'bread','eggs','yogurt','quark','cream','poultry','pork','fruit','vegetables','rice','flour'}
FRUIT={'apple':r'\bapfel\b|\bapfel[n]?\b|tafelapfel','banana':r'banane','orange':r'\borange[n]?\b|apfelsine','pear':r'\bbirne[n]?\b','grape':r'\btrauben|weintrauben','kiwi':r'\bkiwi','lemon':r'\bzitrone','mandarin':r'mandarine|clementine','strawberry':r'erdbeer','blueberry':r'heidelbeer|blaubeer','raspberry':r'himbeer','mango':r'\bmango','pineapple':r'\bananas\b','avocado':r'avocado'}
VEG={'potato':r'kartoffel','tomato':r'tomaten|\btomate\b','cucumber':r'gurke','pepper':r'\bpaprika\b','carrot':r'karotte|mohre|bundmohren','onion':r'zwiebel','garlic':r'knoblauch','zucchini':r'zucchini','broccoli':r'brokkoli|broccoli','cauliflower':r'blumenkohl','mushroom':r'champignon|pilze','lettuce':r'kopfsalat|eisbergsalat|romanasalat|salatherzen|feldsalat','spinach':r'spinat','leek':r'\blauch\b|porree','cabbage':r'weisskohl|rotkohl|wirsing|spitzkohl'}

def text(raw):return re.sub(r'\s+',' ',normal(raw))
def kinds(raw,mapping):return [k for k,regex in mapping.items() if re.search(regex,text(raw))]
def category(raw):
 t=text(raw)
 if re.search(r'amaryllis|zwiebelgrosse|gartenpflanze|blumenzwiebel|brausetablette|vitamin|nahrungserganz|omni[vw]it|schussel|backform|schneider|reibe|messer|maschine|spielzeug|futter|shampoo|dusch|body|gesichts|handcreme|haar|kerze|duft|seife',t):return None
 ready=r'pizza|lasagne|fertig|suppe|eintopf|salatdressing|gefullt|tortellini|ravioli|burger|nuggets|cordon|schnitzel.*paniert|geg[aä]rt|gegart|verzehrfertig'
 if re.search(ready,t):return None
 if re.search(r'\b(?:huhner|freiland|bodenhaltungs|bio[- ]?)?eier\b',t) and not re.search(r'eierlikor|eiernudeln|schoko|ostereier|gefarbt|gekocht',t):return 'eggs'
 if re.search(r'joghurt|jogurt|yoghurt',t) and not re.search(r'sosse|sauce|dressing|butter|eis\b|riegel|kuchen',t):return 'yogurt'
 if re.search(r'\bquark\b|magerquark|speisequark|fruchtequark',t) and not re.search(r'kuchen|tasche|ballchen|brotchen|dessert',t):return 'quark'
 if re.search(r'\bsahne\b|schlagsahne|kochsahne|sauerrahm|schmand|creme\s+fraiche',t) and not re.search(r'kase|butter|hering|pudding|dessert|kuchen|sauce|sosse|rahmspinat|bonbon|eis\b|milchreis|joghurt|quark',t):return 'cream'
 if re.search(r'hahnchen|huhner|pute[n]?|truthahn|geflugel',t) and not re.search(r'schwein|\brind|gemischt|wurst|salami|aufschnitt|mortadella|lyoner|cabanossi|schinken|gerauchert|nuggets|streifen.*gebraten',t):return 'poultry'
 if re.search(r'schwein|schweine|schweins',t) and not re.search(r'\brind|lamm|gemischt|wurst|salami|schinken|aufschnitt|sulze|leberkase|kasseler|leberwurst|gerauchert|pulled',t):return 'pork'
 if re.search(r'\breis\b|basmatireis|jasminreis|langkornreis|naturreis|risottoreis',t) and not re.search(r'express|mikrowelle|vorgegart|kochfertig|milchreis|reiswaffel|reisdrink|reisnudel|reisgericht|sushi|gewurz|kochbeutel.*sauce',t):return 'rice'
 if re.search(r'\bmehl\b|weizenmehl|dinkelmehl|roggenmehl',t) and not re.search(r'panier|backmischung|kokos|mandel|teig',t):return 'flour'
 if re.search(r'\bbrot\b|roggenbrot|mischbrot|vollkornbrot|bauernbrot|brotchen|semmel|baguette|ciabatta|dinkelbrot',t) and not re.search(r'creme|aufstrich|franzbrotchen style|toast|kuchen|schoko|knoblauch|kase|croissant|hotdog|hamburger|suss|rosinen|panier|backmisch',t):return 'bread'
 # Fruit/vegetables only as standalone fresh produce, never flavour/ingredient.
 if re.search(r'tomaten[- ]*mark|passata|passiert|kartoffelsalat|nudelsalat|obstsalat|fruchtsalat|geschnitten|sauer eingelegt|saft|nektar|drink|smoothie|schokolade|riegel|keks|marmelade|konfiture|fruchtaufstrich|eis\b|joghurt|quark|butter|kase|sauce|sosse|pesto|chips|pommes|purree|puree|konserve|dose|glas|getrocknet|tiefgefroren|tiefkuhl|gewurz|marinade|brot|kuchen|salami|wurst|fleisch|fisch|hering|braten|bolognese|auflauf|salatmix|salatmischung|eingelegt',t):return None
 f=kinds(t,FRUIT);v=kinds(t,VEG)
 if len(f)==1 and not v:return 'fruit'
 if len(v)==1 and not f:return 'vegetables'
 return None

def tags(raw,cat):
 t=text(raw);v=[];a=[]
 for tag,regex in [('bio',r'\bbio\b'),('vegan',r'\bvegan|pflanzlich'),('lactosefree',r'laktosefrei|lactosefrei'),('glutenfree',r'glutenfrei'),('wholegrain',r'vollkorn')]:
  if re.search(regex,t):a.append(tag)
 mappings={
 'bread':{'roll':r'brotchen|semmel','loaf':r'\bbrot\b|roggenbrot|mischbrot|vollkornbrot|bauernbrot|dinkelbrot','baguette':r'baguette','ciabatta':r'ciabatta','rye':r'roggen','spelt':r'dinkel','wheat':r'weizen'},
 'eggs':{'free_range':r'freiland','barn':r'bodenhaltung','size_s':r'klasse\s*s\b|grosse\s*s\b','size_m':r'klasse\s*m\b|grosse\s*m\b','size_l':r'klasse\s*l\b|grosse\s*l\b'},
 'yogurt':{'plain':r'naturjoghurt|natur[- ]joghurt|joghurt\s+natur','greek':r'griech','fruit':r'frucht|erdbeer|himbeer|pfirsich','vanilla':r'vanille'},
 'quark':{'plain':r'\bquark\b|speisequark|magerquark','lowfat':r'mager','fruit':r'frucht|erdbeer|himbeer'},
 'cream':{'whipping':r'schlagsahne|susse\s+sahne','cooking':r'kochsahne','sour':r'saure\s+sahne|sauerrahm','schmand':r'schmand','fraiche':r'creme\s+fraiche'},
 'poultry':{'chicken':r'hahnchen|huhner','turkey':r'pute[n]?|truthahn','breast':r'brust','schnitzel':r'schnitzel','fillet':r'filet','leg':r'keule|schenkel','wing':r'flugel','whole':r'ganzes|grillhahnchen'},
 'pork':{'mince':r'hackfleisch|hackepeter','steak':r'steak','schnitzel':r'schnitzel','fillet':r'filet','roast':r'braten','neck':r'nacken|kamm','loin':r'rucken|lachs','goulash':r'gulasch'},
 'rice':{'basmati':r'basmati','jasmine':r'jasmin','longgrain':r'langkorn','brown':r'naturreis|vollkorn','risotto':r'risotto'},
 'flour':{'wheat':r'weizen','spelt':r'dinkel','rye':r'roggen'},'fruit':FRUIT,'vegetables':VEG}
 v=kinds(t,mappings.get(cat,{}))
 if cat=='quark' and 'fruit' in v:v=[x for x in v if x!='plain']
 if cat in {'poultry','pork'}:
  if re.search(r'tiefgefroren|tiefkuhl',t):v.append('frozen')
  else:v.append('fresh') if re.search(r'frisch|gekuhlt',t) else None
  if re.search(r'mariniert|gewurzt',t):v.append('marinated')
  elif re.search(r'natur\b',t):v.append('plain')
 if cat in {'yogurt','quark','cream'}:
  for fat in ([] if re.search(r'\d[.,]?\d*\s*[-–]\s*\d[.,]?\d*\s*%',t) else re.findall(r'(?<!\d)(\d{1,2}(?:[.,]\d)?)\s*%\s*(?:fett)?',t)):v.append('fat'+str(round(float(fat.replace(',','.'))*10)))
 if cat=='flour':
  v += ['type'+n for n in re.findall(r'\b(?:type|typ)\s*(405|550|630|812|997|1050|1150|1370)\b',t)]
 return sorted(set(v)),sorted(set(a))
