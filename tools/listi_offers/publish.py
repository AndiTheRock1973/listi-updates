"""Publish v2 and a compatible two-market feed for the already installed Listi 1.6."""
import base64
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = 'AndiTheRock1973/listi-updates'


def semantic(data):
    return {k: v for k, v in data.items() if k not in {'generatedAt', 'reviewedOn', 'catalogVersion'}}


def legacy(data):
    result = dict(data)
    result['offers'] = [o for o in data['offers'] if o['market'] in {'Lidl', 'PENNY'}
                        and o.get('verificationMethod', 'manual') in {'manual', 'pdf_text_crosscheck', 'ocr_unitprice_crosscheck'}]
    result['sources'] = [s for s in data['sources'] if s['market'] in {'Lidl', 'PENNY'}]
    result['coverage'] = 'Automatische Auswahl aus Lidl Maisach und PENNY Eichenau: Pasta, Butter und Kaffee. Kein vollständiger Marktvergleich.'
    return result


def publish(data, path, headers):
    endpoint = f'https://api.github.com/repos/{REPOSITORY}/contents/{path}'
    try:
        with urlopen(Request(endpoint + '?ref=main', headers=headers), timeout=30) as response:
            current = json.load(response)
        previous = json.loads(base64.b64decode(current['content']))
        if semantic(previous) == semantic(data):
            print(f'{path}: unverändert; kein Commit nötig.')
            return
    except HTTPError as error:
        if error.code != 404:raise
        current, previous = None, {'offers': []}
    old_manual = {o['id']: o for o in previous.get('offers', []) if not o.get('verificationMethod')}
    for offer in data['offers']:
        if not offer.get('verificationMethod') and old_manual.get(offer['id']) != offer:
            raise ValueError('Unvalidated manual addition')
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    payload = {'message': 'Wochenangebote automatisch aktualisiert', 'branch': 'main',
               'content': base64.b64encode(encoded.encode()).decode()}
    if current:payload['sha'] = current['sha']
    with urlopen(Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method='PUT'), timeout=30) as response:
        if response.status not in {200, 201}:raise RuntimeError('Publication failed')
    print(f"{path}: {len(data['offers'])} Angebote veröffentlicht.")


def main():
    from collect import validate_offer
    data = json.loads(Path(sys.argv[1]).read_bytes())
    if data.get('schemaVersion') != 1 or not isinstance(data.get('offers'), list) or len(data['offers']) > 500:
        raise ValueError('Invalid catalog')
    if not any(s.get('state') == 'ok' for s in data.get('sources', [])):
        raise ValueError('No successful source; refusing publication')
    for offer in data['offers']:
        if offer.get('verificationMethod'):validate_offer(offer)
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:raise ValueError('Unexpected repository')
    token = os.environ['GH_TOKEN']
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Listi-Offers-Publisher'}
    publish(data, 'data/wochenangebote-v2.json', headers)
    publish(legacy(data), 'data/wochenangebote.json', headers)


if __name__ == '__main__':main()
