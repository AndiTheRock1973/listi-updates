# Listi: tägliche Angebotsauswahl, ab 1.9.0 zehn Produktgruppen

Sieben bestehende Quellen, täglicher Lauf. Neu: Milch, Nudelsauce, Cola, Wurst und
Käse. Vorhanden bleiben Pasta, Butter, Kaffee, Toast und reines Rindfleisch.
Keine vollständige Erfassung. Händlerlayouts und OCR können Treffer übersehen.

`pantry.py` klassifiziert die neuen Produktgruppen und ausdrücklich belegte
Eigenschaften. `pantry_fields.py` prüft Mengen in ml, Liter-Grundpreise und Pfand.
Zero wird nicht aus „verschiedene Sorten“ abgeleitet. Wurst und Käse sowie
Kuhmilch und Pflanzenprodukte werden getrennt. Nicht belegte Kombinationen von
Eigenschaften unterschiedlicher Milchsorten werden vom App-Matcher ausgelassen.
`product_types.py` behandelt Toast und reines Rindfleisch. Preise je 100 g sind
Preisbezugsmengen und keine festen Packungen.

Preis und Produktfeld müssen räumlich und rechnerisch zusammenpassen. Unklare
Zuordnung, App-Sonderpreise, variable Beispielgewichte und eingeschränkt regionale
EDEKA-Thekenangebote werden ausgelassen. `verified` heißt technische Prüfungen,
keine menschliche Einzelbestätigung. Produkt und Filialverfügbarkeit prüfen.

Ausgaben (alle unter data/):
- v4: zehn Gruppen, schemaVersion 2, für App 1.9.0.
- v3: fünf Gruppen, schemaVersion 1, für App 1.8.0.
- v2: drei Gruppen, schemaVersion 1, für App 1.7.0.
- ohne Versionssuffix: drei Gruppen, Lidl/PENNY, für App 1.6.0.

`publish.py` filtert alte Formate und berechnet deren Markt-Zähler neu.
`lastCheckedOn` bezeichnet den Auswertungstag; individuelle Angebotsgültigkeit
wird nie verlängert. Quellenausfall behält nur gültige alte Treffer, vollständiger
Ausfall veröffentlicht nichts. Unveränderter Inhalt erzeugt keinen neuen Commit.

Workflow: .github/workflows/listi-offers.yml (im Paket unter Zeitplan/).
Python 3.12+, PyMuPDF aus requirements.txt, Tesseract UND deutsches Sprachpaket:

```sh
python -m unittest discover -s tools/listi_offers -p 'test_*.py'
python tools/listi_offers/collect.py --previous data/wochenangebote-v4.json --output /tmp/listi-new.json
```

Einkaufsbegriffe werden nur lokal auf dem Handy abgeglichen. Keine neuen APIs,
Händlerkonten, Firebase-Zugangsdaten oder KI-Dienste. Die App braucht v4 für die
neuen Produktgruppen; ältere Versionen erhalten ihre kompatiblen Dateien weiter.
