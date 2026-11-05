"""Publish only the validated catalog; no retailer process receives this token."""
import base64
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = 'AndiTheRock1973/listi-updates'
ENDPOINT = f'https://api.github.com/repos/{REPOSITORY}/contents/data/wochenangebote.json'


def semantic(data):
    # A timestamp alone is not a reason to commit an unchanged catalog.
    return {k: v for k, v in data.items() if k not in {'generatedAt', 'reviewedOn', 'catalogVersion'}}


def main():
    from collect import validate_offer
    proposed = Path(sys.argv[1]).read_bytes()
    data = json.loads(proposed)
    if data.get('schemaVersion') != 1 or not isinstance(data.get('offers'), list):
        raise ValueError('Invalid catalog')
    if not any(s.get('state') == 'ok' for s in data.get('sources', [])):
        raise ValueError('No successful source; refusing publication')
    for offer in data['offers']:
        # Retained old manually reviewed data is permitted only when unchanged.
        if offer.get('verificationMethod'):
            validate_offer(offer)
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ValueError('Unexpected repository')
    token = os.environ['GH_TOKEN']
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Listi-Offers-Publisher'}
    try:
        with urlopen(Request(ENDPOINT + '?ref=main', headers=headers), timeout=30) as response:
            current = json.load(response)
        previous = json.loads(base64.b64decode(current['content']))
        if semantic(previous) == semantic(data):
            print('Angebotsdaten unverändert; kein Commit nötig.')
            return
    except HTTPError as error:
        if error.code != 404:
            raise
        current = None
        previous = {'offers': []}
    old_manual = {o['id']: o for o in previous.get('offers', []) if not o.get('verificationMethod')}
    for offer in data['offers']:
        if not offer.get('verificationMethod') and old_manual.get(offer['id']) != offer:
            raise ValueError('Unvalidated manual addition')
    payload = {'message': 'Wochenangebote automatisch aktualisiert', 'branch': 'main',
               'content': base64.b64encode(proposed).decode()}
    if current:
        payload['sha'] = current['sha']
    with urlopen(Request(ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method='PUT'), timeout=30) as response:
        if response.status != 200 and response.status != 201:
            raise RuntimeError('Publication failed')
    print(f"Veröffentlicht: {len(data['offers'])} Angebote.")


if __name__ == '__main__':
    main()
