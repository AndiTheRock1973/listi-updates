# Listi 1.10: 21 supported grocery groups

Add bread, eggs, yogurt, quark, cream, poultry, pork, fruit, vegetables, rice,
flour to the existing ten groups. `staples.py` defines conservative categories
and explicit product variants. `staple_fields.py` validates counts, produce
price bases and gram quantities. `pantry_fields.py` also handles cream in ml.

Unknown/ambiguous categories or prices are omitted. No synthetic offers enter
published feeds. Nonfood plant bulbs, vitamin tablets, fruit flavours, prepared
meals, tomato puree, mixed meat and unclear product/price associations must not
be treated as fresh groceries. Source changes can still produce omissions.
This is a partial technical extraction, not complete market coverage.

Piece amounts use quantityUnit=piece and quantityCount; never quantityGrams.
Methods pdf_count_crosscheck (pack and printed piece price) and pdf_piece_price
(explicit single item) have separate validation. Mass/volume proof stays separate.
Per-kg/100g loose prices identify price bases, not fixed packages.

Feed v5 schema 3 is for app 1.10. v4 schema 2 is filtered to the former ten
groups and no counts. v3/v2/v1 retain earlier formats. Publication recalculates
per-source counts. Full source failure never overwrites published data. Partial
failure keeps only still-valid old records, with original expiry dates.

Workflow remains daily 05:23 UTC, tesseract-ocr plus tesseract-ocr-deu,
Python 3.12+, pinned PyMuPDF. No changes to Firebase or credentials.

```sh
python -m unittest discover -s tools/listi_offers -p 'test_*.py'
python tools/listi_offers/collect.py --previous data/wochenangebote-v5.json --output /tmp/listi-new.json
```

Action's full online viewer remains separate from this seven-market extractor.
Shopping text stays on the device; no text is sent to merchants or AI services.
