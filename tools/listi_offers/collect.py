"""Conservative official-prospect importer for Listi's seven configured markets.
No AI API, credentials, browser fingerprint spoofing or retailer account access.
Uncertain prices/conditions are omitted; the result is not an exhaustive catalog.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
from urllib.parse import urljoin, urlparse, urlencode
from urllib.request import Request, urlopen
import fitz
import product_types

ALLOWED_HOSTS = {
    'www.lidl.de', 'endpoints.leaflets.schwarz', 'assets.leaflets.schwarz',
    'www.penny.de', 'penny-publish.blaetterkatalog.de',
    'www.aldi-sued.de', 'prospekt.aldi-sued.de', 'view.publitas.com',
    'www.rewe.de', 'services.publitas.com', 'blaetterkatalog.edeka.de',
    'aez.de', 'www.mueller.de', 'dam.prod.ecom.mueller.de',
}
MAX_BYTES = 200_000_000
MARKET_PDF_HOSTS = {
    'Lidl': 'assets.leaflets.schwarz',
    'PENNY': 'penny-publish.blaetterkatalog.de',
    'ALDI SÜD': 'view.publitas.com',
    'REWE': 'view.publitas.com',
    'EDEKA': 'blaetterkatalog.edeka.de',
    'AEZ': 'aez.de',
    'MÜLLER': 'dam.prod.ecom.mueller.de',
}
LOCAL_NAMES = {'ALDI SÜD': 'aldi', 'MÜLLER': 'mueller'}


def normalized(text: str) -> str:
    text = text.replace('\u00ad', '').replace('ß', 'ss')
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


def fetch(url: str, limit: int = MAX_BYTES) -> bytes:
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError('Non-public or unexpected source host')
    request = Request(url, headers={'User-Agent': 'Listi-Offers/1.0 (+https://github.com/AndiTheRock1973/listi-updates)'})
    with urlopen(request, timeout=35) as response:
        if urlparse(response.geturl()).hostname not in ALLOWED_HOSTS:
            raise ValueError('Unexpected redirect host')
        result = bytearray()
        while chunk := response.read(1024 * 256):
            result.extend(chunk)
            if len(result) > limit:
                raise ValueError('Source exceeds download limit')
        return bytes(result)


def text(url: str, limit: int = 4_000_000) -> str:
    return fetch(url, limit).decode('utf-8')


@dataclass(frozen=True)
class Source:
    market: str
    location: str
    pdf_url: str
    source_url: str
    start: date
    end: date


def lidl_source(today: date) -> Source:
    page = text('https://www.lidl.de/c/online-prospekte/s10005610/')
    pattern = r'https://www\.lidl\.de/l/prospekte/(aktionsprospekt-(\d{2})-(\d{2})-(\d{4})-(\d{2})-(\d{2})-(\d{4})-[^/"<>\s]+)/ar/'
    identifiers = []
    for m in re.finditer(pattern, page):
        start = date(int(m[4]), int(m[3]), int(m[2]))
        end = date(int(m[7]), int(m[6]), int(m[5]))
        if start <= today <= end:
            identifiers.append(m[1])
    if not identifiers:
        raise ValueError('No current Lidl edition found')
    payload = json.loads(text('https://www.lidl.de/s/de-DE/filialen/maisach/maisacher-str-61/_payload.json'))
    if not isinstance(payload, list) or 'DE02081' not in payload:
        raise ValueError('Maisach store mapping missing')
    regions = [payload[d['offerRegion']] for d in payload
               if isinstance(d, dict) and type(d.get('offerRegion')) is int]
    if not regions or type(regions[0]) is not int:
        raise ValueError('Maisach offer region missing')
    params = {'flyer_identifier': identifiers[0], 'region_id': regions[0],
              'region_code': regions[0], 'store_id': 2081}
    data = json.loads(text('https://endpoints.leaflets.schwarz/v4/flyer?' + urlencode(params)))
    if data.get('success') is not True:
        raise ValueError('Lidl flyer query failed')
    flyer = data['flyer']
    start = date.fromisoformat(flyer['offerStartDate'])
    end = date.fromisoformat(flyer['offerEndDate'])
    if not start <= today <= end:
        raise ValueError('Lidl edition is not current')
    return Source('Lidl', 'Maisach · Maisacher Straße 61', flyer['pdfUrl'],
                  flyer['flyerUrlAbsolute'], start, end)


def penny_source(today: date) -> Source:
    data = json.loads(text('https://www.penny.de/.rest/market/markets/market_562302'))
    if data.get('wwIdent') != '562302' or normalized(data.get('city', '')) != 'eichenau':
        raise ValueError('PENNY Eichenau mapping missing')
    viewer = data['flippingBookURL']
    page = text(viewer)
    expires = re.search(r'<meta\s+http-equiv=["\']expires["\']\s+content=["\']([^"\']+)', page, re.I)
    week = re.search(r'PENNY-HZ-KW(\d{1,2})-', page)
    link = re.search(r"saveCompleteUrl:\s*'([^']+)'", page)
    if not expires or not week or not link:
        raise ValueError('PENNY edition metadata incomplete')
    end = parsedate_to_datetime(expires[1]).date()
    start = date.fromisocalendar(end.isocalendar().year, int(week[1]), 1)
    if not start <= today <= end or not 0 <= (end - start).days <= 6:
        raise ValueError('PENNY edition is not current')
    return Source('PENNY', 'Eichenau · Hauptstraße 17–19',
                  urljoin(viewer, link[1].replace('\\/', '/')), viewer, start, end)


@dataclass(frozen=True)
class Word:
    value: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    confidence: float = 100.0


def native_page(page) -> tuple[list[dict], list[Word]]:
    blocks, words = [], []
    for block in page.get_text('dict')['blocks']:
        if 'lines' not in block:
            continue
        lines = [' '.join(span['text'] for span in line['spans']) for line in block['lines']]
        blocks.append({'text': '\n'.join(lines), 'bbox': block['bbox']})
        for line in block['lines']:
            for span in line['spans']:
                words.append(Word(span['text'], *span['bbox'], span['size']))
    return blocks, words


def ocr(page, scale: float, directory: Path, name: str) -> list[Word]:
    image = directory / (name + '.png')
    page.get_pixmap(matrix=fitz.Matrix(scale, scale)).save(image)
    command = ['tesseract', str(image), 'stdout', '-l', os.getenv('LISTI_OCR_LANG', 'deu'), '--psm', '11', 'tsv']
    if os.getenv('TESSDATA_PREFIX'):
        command[1:1] = ['--tessdata-dir', os.environ['TESSDATA_PREFIX']]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=True)
    image.unlink(missing_ok=True)
    words = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter='\t'):
        value = row['text'].strip()
        if not value:
            continue
        x, y, w, h = [float(row[key]) / scale for key in ['left', 'top', 'width', 'height']]
        words.append(Word(value, x, y, x+w, y+h, h, float(row['conf'])))
    return words


def confirm_price_words(page, words: list[Word], directory: Path) -> list[Word]:
    """Re-read uncertain large price glyphs separately; never upgrade by assumption."""
    result = []
    for index, word in enumerate(words):
        digits = re.sub(r'[^0-9]', '', word.value)
        if word.size < 20 or not 2 <= len(digits) <= 5 or not 55 <= word.confidence < 70:
            result.append(word)
            continue
        image = directory / f'price-{index}.png'
        clip = fitz.Rect(word.x0 - 2, word.y0 - 2, word.x1 + 2, word.y1 + 2) & page.rect
        page.get_pixmap(matrix=fitz.Matrix(5, 5), clip=clip).save(image)
        command = ['tesseract', str(image), 'stdout', '-l', os.getenv('LISTI_OCR_LANG', 'deu'),
                   '--psm', '6', 'tsv']
        if os.getenv('TESSDATA_PREFIX'):
            command[1:1] = ['--tessdata-dir', os.environ['TESSDATA_PREFIX']]
        output = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True).stdout
        image.unlink(missing_ok=True)
        confirmed = [r for r in csv.DictReader(io.StringIO(output), delimiter='\t')
                     if re.sub(r'[^0-9]', '', r['text']) == digits and float(r['conf']) >= 70]
        result.append(Word(word.value, word.x0, word.y0, word.x1, word.y1, word.size,
                           float(confirmed[0]['conf'])) if confirmed else word)
    return result


def lines_from_words(words: list[Word]) -> list[dict]:
    # Geometric rows, then separate the three Lidl columns before joining text.
    lines = []
    for w in sorted(words, key=lambda w: (w.y0, w.x0)):
        found = None
        for line in reversed(lines[-20:]):
            if abs(line['y'] - w.y0) < 3 and abs(line['x1'] - w.x0) < 18:
                found = line
                break
        if found is None:
            lines.append({'y': w.y0, 'x0': w.x0, 'x1': w.x1, 'words': [w]})
        else:
            found['words'].append(w)
            found['x1'] = max(found['x1'], w.x1)
    for line in lines:
        line['words'].sort(key=lambda w: w.x0)
        line['text'] = ' '.join(w.value for w in line['words'])
    return lines


def category_of(value: str) -> str | None:
    extra = product_types.category_extra(value)
    if extra is not None:
        return extra if extra != 'reject' else None
    t = normalized(value)
    if re.search(r'buttermilch|croissant|keks|waffel|murb|geback|sauce|sosse|cappuccino|latte|margarine|streichfett|pflanzliche? butter|vegane? butter|gericht|suppe|salat|bolognese|gefull|tortell|ravioli|pesto|maschine|vollautomat|becher|fertig|gek[üu]hlt.*pasta', t):
        return None
    if re.search(r'\bbutter\b', t):
        return 'butter'
    if re.search(r'\b(pasta|nudeln|spaghetti|fusilli|penne)\b', t):
        if 'gekuhlt' in t:
            return None
        return 'pasta'
    if re.search(r'\b(kaffee|kaffeepads|kaffeebohnen)\b', t) or ('lavazza' in t and re.search(r'\b(caffe|espresso)\b', t)) or ('movenpick' in t and 'himmlische' in t and 'gemahlen' in t):
        return 'coffee'
    return None


def cents(value: str) -> int:
    return int((Decimal(value.replace(',', '.')) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def checked_price(caption: str, words: list[Word], minimum_size: float = 12) -> tuple[int, int, int] | None:
    t = normalized(caption)
    amounts = re.findall(r'\bje\s*(\d{1,5}(?:\.\d{3})?)\s*-?g\b', t)
    units = re.findall(r'\b1\s*kg\s*=\s*(\d{1,3}[.,]\d{2})\b', t)
    if len(amounts) != 1 or len(units) != 1:
        return None
    grams = int(amounts[0].replace('.', ''))
    if not 50 <= grams <= 2500:
        return None
    unit_cents = cents(units[0])
    price = int((Decimal(unit_cents) * grams / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if not 10 <= price <= 5000:
        return None
    candidates = []
    for word in words:
        if word.size < minimum_size or word.confidence < 70 or '%' in word.value or word.value.strip().startswith('-'):
            continue
        clean = re.sub(r'[^0-9.,]', '', word.value)
        if re.fullmatch(r'\d{1,3}[.,]\d{2}', clean):
            number = cents(clean)
        elif re.fullmatch(r'\d{2,5}', clean):
            number = int(clean)
        else:
            continue
        if number == price:
            candidates.append(word)
    # Unit-price rounding is at most half a cent/kg; don't accept loose price matches.
    expected_unit = int((Decimal(price) * 1000 / grams).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if not candidates or abs(expected_unit - unit_cents) > 1:
        return None
    return price, grams, unit_cents


def in_rect(w: Word, rect) -> bool:
    x0, y0, x1, y1 = rect
    return w.x0 >= x0 and w.x1 <= x1 and w.y0 >= y0 and w.y1 <= y1


def page_dates(header: str, source: Source) -> tuple[date, date] | None:
    # Require explicit day/month bounds in the top strip of the same PDF page.
    found = re.findall(r'(?<!\d)(\d{1,2})\s*\.\s*(\d{1,2})\s*\.', header)
    if len(found) < 2:
        return None
    a, b = found[:2]
    def pick(pair):
        choices = []
        for year in {source.start.year, source.end.year}:
            try:
                d = date(year, int(pair[1]), int(pair[0]))
                if source.start <= d <= source.end:
                    choices.append(d)
            except ValueError:
                pass
        return choices[0] if len(choices) == 1 else None
    start, end = pick(a), pick(b)
    if not start or not end or end < start:
        return None
    # Check any printed German weekday against the full source year.
    days = {'mo': 0, 'di': 1, 'mi': 2, 'do': 3, 'fr': 4, 'sa': 5, 'so': 6}
    weekday = re.search(r'\b(Mo|Di|Mi|Do|Fr|Sa|So)\b', header, re.I)
    if weekday and days[weekday[1].lower()] != start.weekday():
        return None
    return start, end


def offer_from(caption: str, panel: list[Word], source: Source, bounds: tuple[date, date],
               page_number: int, sha: str, method: str) -> dict | None:
    caption = product_types.caption(caption)
    cat = category_of(caption)
    if not cat:
        return None
    body = normalized(caption)
    panel_text = normalized(' '.join(w.value for w in panel))
    # Conditions may be graphic text outside the caption. Exclude such panels.
    if re.search(r'\bapp\b|lidl|\bplus\b|coupon|normalpreis|ohne penny|ihr\s*preis|mit\s*der|kundenkarte', panel_text):
        return None
    check = checked_price(caption, panel)
    if check is None:
        return None
    price, grams, unit = check
    clean_caption = re.sub(r'[\x00-\x1f*]+', ' ', caption.replace('\u00ad', ''))
    title = re.split(r'\bje\b|Versch\.?\s*Sorten', clean_caption, maxsplit=1, flags=re.I)[0].strip(' .,\n')
    title = re.sub(r'\s+', ' ', title)
    first_line = caption.splitlines()[0].strip('* .')
    if not first_line or len(first_line) > 45:
        return None
    brand = product_types.brand(caption, cat)
    variants = []
    if cat == 'coffee':
        if re.search(r'\bpads\b|kaffeepads', body):
            variants.append('pads')
        elif re.search(r'\bbohnen\b|kaffeebohnen', body):
            variants.append('beans')
        elif 'gemahlen' in body:
            variants.append('ground')
    if cat == 'pasta':
        variants = [shape for shape in ['spaghetti', 'fusilli', 'penne', 'rigatoni']
                    if re.search(r'\b' + shape + r'\b', panel_text)]
    attributes = [tag for tag, keyword in [('bio', 'bio'), ('wholegrain', 'vollkorn'),
                  ('glutenfree', 'glutenfrei'), ('lactosefree', 'laktosefrei')]
                  if re.search(r'\b' + keyword + r'\b', body)]
    if cat in {'toast', 'beef'}:
        variants, extra_attributes = product_types.tags(caption, cat)
        attributes = sorted(set(attributes + extra_attributes))
    start, end = bounds
    identity = f'{source.market}|{normalized(title)}|{grams}|{start}|{price}'
    return {'id': hashlib.sha256(identity.encode()).hexdigest()[:24], 'market': source.market,
            'location': source.location, 'title': title, 'brand': brand,
            'category': cat, 'variants': variants, 'attributes': attributes,
            'priceCents': price, 'quantityGrams': grams, 'validFrom': start.isoformat(),
            'validTo': end.isoformat(), 'pdfPage': page_number, 'pdfUrl': source.pdf_url,
            'sourceUrl': source.source_url, 'verified': True, 'verificationMethod': method,
            'evidence': {'pdfSha256': sha, 'printedUnitPriceCents': unit,
                         'caption': clean_caption[:600]},
            'note': 'Automatisch aus dem offiziellen Prospekt erfasst. Sorte, Packung, Vorrat und Filialverfügbarkeit im Prospekt prüfen.'}


def collect_penny(pdf: Path, source: Source) -> list[dict]:
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    offers = []
    with fitz.open(pdf) as document:
        if not 1 <= len(document) <= 150:
            raise ValueError('Unexpected PENNY page count')
        for n, page in enumerate(document, 1):
            blocks, words = native_page(page)
            header = ' '.join(b['text'] for b in blocks if b['bbox'][1] < 45)
            bounds = page_dates(header, source)
            if not bounds:
                continue
            for block in blocks:
                if category_of(block['text']) is None:
                    continue
                x0, y0, x1, y1 = block['bbox']
                half = page.rect.width / 2
                left = int(x0 // half) * half
                rect = (left, max(45, y0 - 85), left + half, min(page.rect.height - 45, y1 + 20))
                panel = [w for w in words if in_rect(w, rect)]
                offer = offer_from(block['text'], panel, source, bounds, n, sha, 'pdf_text_crosscheck')
                if offer:
                    offers.append(offer)
    return offers


def collect_lidl(pdf: Path, source: Source, directory: Path, pages: list[int] | None = None) -> list[dict]:
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    offers = []
    with fitz.open(pdf) as document:
        if not 1 <= len(document) <= 150:
            raise ValueError('Unexpected Lidl page count')
        for n, page in enumerate(document, 1):
            if pages and n not in pages:
                continue
            preview = ocr(page, 1.5, directory, f'lidl-preview-{n}')
            preview_text = ' '.join(w.value for w in preview)
            if not re.search(r'pasta|spaghetti|fusilli|nudeln|butter|kaffee|movenpick|melitta|barilla|toast|sandwich|rind|jungbullen|entrecote|rumpsteak', normalized(preview_text)):
                continue
            words = confirm_price_words(page, ocr(page, 3, directory, f'lidl-detail-{n}'), directory)
            header = ' '.join(w.value for w in sorted(words, key=lambda w: w.x0) if w.y0 < 45)
            bounds = page_dates(header, source)
            if not bounds:
                continue
            lines = lines_from_words(words)
            third = page.rect.width / 3
            for line in lines:
                if not 45 < line['y'] < page.rect.height - 70:
                    continue
                raw = line['text']
                letters = [c for c in raw if c.isalpha()]
                if len(letters) < 3 or sum(c.isupper() for c in letters) / len(letters) < 0.85:
                    continue
                if min(w.confidence for w in line['words']) < 80:
                    continue
                left = int(line['x0'] // third) * third
                if line['x0'] > left + third * .32:
                    continue
                caption_lines = [row for row in lines if line['y'] - 1 <= row['y'] <= line['y'] + 65
                                 and abs(row['x0'] - line['x0']) < 5
                                 and all(w.size < 18 for w in row['words'])]
                caption = '\n'.join(row['text'] for row in sorted(caption_lines, key=lambda row: row['y']))
                if category_of(caption) is None:
                    continue
                panel_rect = (left, max(45, line['y'] - 125), left + third, min(page.rect.height - 35, line['y'] + 70))
                panel = [w for w in words if in_rect(w, panel_rect)]
                offer = offer_from(caption, panel, source, bounds, n, sha, 'ocr_unitprice_crosscheck')
                if offer:
                    offers.append(offer)
            print(f'Lidl PDF page {n}: {len(offers)} accepted offers so far', flush=True)
    return offers


def validate_offer(offer: dict) -> None:
    if offer['market'] not in MARKET_PDF_HOSTS or offer['category'] not in {'pasta', 'coffee', 'butter', 'toast', 'beef'}:
        raise ValueError('Unexpected product mapping')
    if offer.get('verificationMethod') not in {'pdf_text_crosscheck', 'ocr_unitprice_crosscheck', 'pdf_1kg_price', 'pdf_100g_price'}:
        raise ValueError('Missing machine validation evidence')
    evidence = offer['evidence']
    if offer['category'] in {'toast', 'beef'}:
        if product_types.category_extra(evidence.get('caption', '')) != offer['category']:
            raise ValueError('Product type is not supported by the printed caption')
        expected_variants, _ = product_types.tags(evidence['caption'], offer['category'])
        if set(offer['variants']) != set(expected_variants):
            raise ValueError('Product variants disagree with printed caption')
    if not re.fullmatch(r'[0-9a-f]{64}', evidence.get('pdfSha256', '')):
        raise ValueError('PDF fingerprint missing')
    for key in ['pdfUrl', 'sourceUrl']:
        if urlparse(offer[key]).scheme != 'https' or urlparse(offer[key]).hostname not in ALLOWED_HOSTS:
            raise ValueError('Unexpected evidence URL')
    if offer['verificationMethod'] in {'pdf_1kg_price', 'pdf_100g_price'}:
        counter = offer['verificationMethod'] == 'pdf_100g_price'
        if counter and (offer['category'] != 'beef' or offer['quantityGrams'] != 100 or not re.fullmatch(r'100\s*g', evidence.get('printedQuantity', ''), re.I)):
            raise ValueError('Explicit beef price per 100 g missing')
        if not counter and (offer['quantityGrams'] != 1000 or not re.fullmatch(r'(?:1\s*kg|1[.]?000\s*g)', evidence.get('printedQuantity', ''), re.I)):
            raise ValueError('Explicit 1 kg pack missing')
        if not re.fullmatch(r'\d{1,3}[.,]\d{2}', evidence.get('priceLine', '')) or cents(evidence['priceLine']) != offer['priceCents']:
            raise ValueError('Native package price mismatch')
    else:
        expected = round(offer['priceCents'] * 1000 / offer['quantityGrams'])
        if abs(expected - evidence['printedUnitPriceCents']) > 1:
            raise ValueError('Unit-price mismatch')
    start, end = date.fromisoformat(offer['validFrom']), date.fromisoformat(offer['validTo'])
    if not 0 <= (end - start).days <= 6:
        raise ValueError('Invalid validity range')
    if not 1 <= offer['pdfPage'] <= 150 or not 50 <= offer['quantityGrams'] <= 2500 or not 10 <= offer['priceCents'] <= 5000:
        raise ValueError('Invalid price, size or page')
    expected_host = MARKET_PDF_HOSTS[offer['market']]
    if (urlparse(offer['pdfUrl']).hostname != expected_host
        or (offer['market'] == 'ALDI SÜD' and not urlparse(offer['pdfUrl']).path.startswith('/73714/'))
        or (offer['market'] == 'REWE' and not urlparse(offer['pdfUrl']).path.startswith('/89773/'))):
        raise ValueError('Retailer and PDF host disagree')
    if not evidence.get('caption') or not offer.get('title') or not offer.get('brand'):
        raise ValueError('Missing product evidence')


def collect(today: date, directory: Path, previous: dict | None = None,
            local: Path | None = None, lidl_pages: list[int] | None = None, include_all: bool = True) -> dict:
    offers, statuses = [], []
    jobs = [('PENNY', penny_source, collect_penny), ('Lidl', lidl_source, collect_lidl)]
    if include_all:
        import more_markets
        jobs.extend((market, lambda day, m=market: more_markets.resolve(m, day), more_markets.native_collect)
                    for market in more_markets.ENTRY)
    for market, resolver, importer in jobs:
        try:
            source = resolver(today)
            pdf = directory / f'{LOCAL_NAMES.get(market, market.lower())}.pdf'
            if local and (local / pdf.name).exists():
                pdf = local / pdf.name
            else:
                data = fetch(source.pdf_url)
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Source did not deliver PDF')
                pdf.write_bytes(data)
            result = importer(pdf, source, directory, lidl_pages) if market == 'Lidl' else importer(pdf, source)
            for offer in result:
                validate_offer(offer)
            offers.extend(result)
            statuses.append({'market': market, 'state': 'ok', 'count': len(result),
                             'validFrom': source.start.isoformat(), 'validTo': source.end.isoformat()})
        except Exception as error:
            print(f'{market}: source unavailable or incompatible: {type(error).__name__}: {error}', flush=True)
            kept = [o for o in (previous or {}).get('offers', []) if o.get('market') == market
                    and o.get('validFrom', 'z') <= today.isoformat() <= o.get('validTo', '')]
            # Keep only already published entries, without prolonging any date.
            offers.extend(kept)
            statuses.append({'market': market, 'state': 'failed', 'retained': len(kept), 'reason': str(error)[:250]})
    if not any(s['state'] == 'ok' for s in statuses):
        raise RuntimeError('All retailer imports failed; published data stays unchanged')
    unique = {offer['id']: offer for offer in offers}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {'schemaVersion': 1, 'catalogVersion': f'{today.isoformat()}-automatic',
            'reviewedOn': today.isoformat(), 'lastCheckedOn': today.isoformat(), 'generatedAt': now,
            'coverage': 'Automatische Auswahl aus den sieben eingerichteten Märkten: Pasta, Butter, Kaffee, Toastbrot und Rindfleisch. Unklare und App-Sonderangebote werden ausgelassen. Kein vollständiger Marktvergleich.',
            'sources': statuses, 'offers': sorted(unique.values(), key=lambda o: (o['market'], o['title'], o['id']))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('data/wochenangebote-v3.json'))
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--local-pdfs', type=Path)
    parser.add_argument('--lidl-pages', help='Only for targeted local verification, e.g. 12,13')
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous and args.previous.exists() else None
    pages = [int(v) for v in args.lidl_pages.split(',')] if args.lidl_pages else None
    with tempfile.TemporaryDirectory(prefix='listi-offers-') as temporary:
        result = collect(date.today(), Path(temporary), previous, args.local_pdfs, pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    staging = args.output.with_suffix('.tmp')
    staging.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    staging.replace(args.output)
    print(json.dumps({'offers': len(result['offers']), 'sources': result['sources']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
