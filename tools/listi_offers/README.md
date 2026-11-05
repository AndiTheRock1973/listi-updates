# Listi: tägliche Angebotsauswahl, ab 1.8.0 fünf Produktgruppen

Sieben eingerichtete Quellen, täglich wie bisher. Neu: Toastbrot und reines Rindfleisch.
`product_types.py` trennt Brot von Toastschinken/Toastern und Rindfleisch von gemischtem
Hack, Schweinefleisch, Wurst und fertigen Gerichten. Erfasste Schnittarten werden in
`variants` gespeichert. Zusätzlich zur bestehenden Gramm-/Grundpreisprüfung gibt es
`pdf_100g_price` für ausdrücklich ausgewiesene Fleischpreise je 100 g. Das ist eine
Preisbezugsmenge, kein behaupteter fester Packungspreis.

Preis und Produktfeld müssen räumlich eindeutig zusammenpassen. App-Bedingungen,
variable Beispielgewichte und unklare Felder werden ausgelassen. Das Verfahren hat
bewusst Lücken und ersetzt keine Kontrolle von Produkt, Preis und Filialverfügbarkeit.

Ausgabe:
- `wochenangebote-v3.json`: fünf Produktgruppen, für App 1.8.0.
- `wochenangebote-v2.json`: kompatible drei Produktgruppen für App 1.7.0.
- `wochenangebote.json`: kompatible Lidl/PENNY-Auswahl für App 1.6.0.

Die Quelldateien liegen im Repository unter data/. Der Workflow liegt dort unter
.github/workflows/listi-offers.yml; im Update-Paket sichtbar unter Zeitplan/listi-offers.yml.
`publish.py` filtert ältere Formate und korrigiert deren Markt-Zähler entsprechend.
Unveränderte Einkaufsbegriffe werden ausschließlich auf dem Handy abgeglichen.
Keine neuen APIs, Händlerkonten, Firebase-Zugangsdaten oder KI-Dienste.

Prüfungen (Python 3.12+, PyMuPDF aus requirements.txt, Tesseract und deutsches Sprachpaket):

```sh
python -m unittest discover -s tools/listi_offers -p 'test_*.py'
python tools/listi_offers/collect.py --previous data/wochenangebote-v3.json --output /tmp/listi-new.json
```

Bei vollständigem Quellenausfall bleibt die veröffentlichte Datei bestehen. Bei Teilausfällen
werden nur noch gültige frühere Einträge übernommen, ohne verlängerte Gültigkeit.
`verified` bedeutet bei automatischen Einträgen technische Prüfungen, keine menschliche
Einzelfreigabe. `verificationMethod` und `evidence` benennen die jeweilige Prüfung.
