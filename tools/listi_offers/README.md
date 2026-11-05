# Listi: tägliche Angebotsauswahl aus sieben Quellen

Quellen: ALDI SÜD, Lidl DE02081 Maisach, EDEKA Südbayern/Neukauf Süd (regionaler Prospekt
für den Eichenauer Markt), PENNY 562302 Eichenau, REWE 461921 Alling, AEZ City Point und
Müller Drogerie. Nationale/regionale Prospekte garantieren keinen einzelnen Filialbestand.

Produktgruppen: Pasta, Butter, Kaffee. Keine vollständige Sortiments- oder Angebotserfassung.
Verschiedene Packungsgrößen, App-Bedingungen und uneindeutige Zuordnungen werden ausgelassen.
Native Textfelder werden mit großen Preiszeilen abgeglichen; bei Lidl kommt OCR hinzu.
Bei vorhandenen Grundpreisen muss die Rechnung passen. Ausdrücklich ausgewiesene 1-kg-
Kaffeepackungen dürfen einen klar zugeordneten nativen Packungspreis ohne separaten Grundpreis
verwenden; dafür existiert die eigene Methode `pdf_1kg_price`, kein erfundener Grundpreisbeleg.

Workflow im Repository: `.github/workflows/listi-offers.yml`, täglich 05:23 UTC, manuell startbar.
Im Update-ZIP liegt die Datei zum Kopieren sichtbar unter `Zeitplan/listi-offers.yml`.

Datenausgabe:
- `data/wochenangebote-v2.json`: alle sieben Quellen, für Listi ab 1.7.0.
- `data/wochenangebote.json`: kompatible Auswahl für bereits installierte Listi 1.6.0.

`more_markets.py` kapselt die fünf zusätzlichen Quellen und die native PDF-Erkennung.
`collect.py` löst jeweils aktuelle Metadaten auf. Keine Kalenderwoche ist fest eingebaut.
`publish.py` schreibt auf `main` über die GitHub Contents API mit dem Workflow-Token.
Es wird ausschließlich ins bekannte eigene Repository geschrieben. Kein persönlicher Token nötig.
Die tatsächliche tägliche Prüfung wird als `lastCheckedOn` protokolliert.

Bei Teilausfällen bleiben nur noch gültige veröffentlichte Angebote des betroffenen Marktes erhalten,
ohne Datumsverlängerung. Bei vollständigem Ausfall wird nicht publiziert. Zeitpläne können verzögert
werden; Ablaufdaten werden unabhängig davon auf dem Handy geprüft. Änderungen an Händlerlayouts
können Wartung erfordern. Automatische mathematische Prüfungen ersetzen keine menschliche Kontrolle.

Lokale Prüfungen (Python 3.12+, Tesseract Deutsch):

```sh
python -m venv .venv
.venv/bin/pip install -r tools/listi_offers/requirements.txt
.venv/bin/python -m unittest discover -s tools/listi_offers -p 'test_*.py'
.venv/bin/python tools/listi_offers/collect.py --previous data/wochenangebote-v2.json --output /tmp/listi-new.json
```

Temporäre PDFs werden nicht committed. Keine Einkaufsbegriffe und keine Firebase-Zugänge werden
an die Erfassung übertragen. Die `verified`-Markierung bezeichnet bei automatischen Einträgen
technische Prüfungen, keine menschliche Einzelfreigabe. Die Methode steht in `verificationMethod`.
`reviewedOn` ist aus Schema-Kompatibilität der Erfassungsstand, keine menschliche Freigabe.
