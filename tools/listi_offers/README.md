# Listi: automatische Angebotsauswahl

Öffentliche Prospektquellen: Lidl-Filiale DE02081 (Maisach), PENNY-Markt 562302 (Eichenau).
Der Import findet die aktuelle Ausgabe anhand ihrer Metadaten. Wochen-URLs sind nicht fest eingebaut.
Erfasst werden nur eindeutig erkannte Pasta-, Butter- und Kaffee-Felder mit grammbezogenem Grundpreis.
Bilder werden mit Tesseract ausgewertet, native PDF-Texte direkt gelesen. Ein mathematischer
Abgleich ersetzt keine menschliche Prüfung; Erkennungsfehler und Lücken bleiben möglich.

Workflow: `.github/workflows/listi-offers.yml`, montags und donnerstags, manuell startbar.
Datenausgabe: `data/wochenangebote.json`, Commit auf `main` bei tatsächlicher Änderung.
Keine PDF-Dateien, Einkaufsdaten, Zugangsschlüssel oder personenbezogenen Daten werden committed.
Keine kostenpflichtige KI-API. Standard-GitHub-Runner im öffentlichen Repository.

Lokal (Python 3.12+, Tesseract mit deutschem Sprachpaket):

```sh
python -m venv .venv
.venv/bin/pip install -r tools/listi_offers/requirements.txt
.venv/bin/python -m unittest discover -s tools/listi_offers -p 'test_*.py'
.venv/bin/python tools/listi_offers/collect.py --previous data/wochenangebote.json --output /tmp/listi-new.json
```

`publish.py` ist nur für den Workflow vorgesehen. Es nimmt keine fremden Repository-Namen an,
veröffentlicht über die GitHub Contents API und enthält keine fest eingetragenen Zugangsdaten.
Ein vollständig fehlgeschlagener Import überschreibt keine Daten. Bei Teilausfällen werden nur
noch gültige veröffentlichte Angebote des ausgefallenen Markts ohne Datumsverlängerung übernommen.
Die App blendet abgelaufene Einträge unabhängig vom Workflow aus.

Die mitgelieferte `data/wochenangebote.json` wurde im vollständigen Probelauf am 05.11.2026
automatisch aus den aktuellen offiziellen PDFs gewonnen. Sie enthält drei erkannte Angebote.
Künftige Ausgaben werden erst nach Einrichtung des Workflows automatisch erfasst.
`reviewedOn` bezeichnet bei automatischen Daten aus Schema-Kompatibilitätsgründen den Erfassungsstand,
nicht eine menschliche Freigabe; `verificationMethod` und `evidence` bezeichnen die technische Prüfung.
