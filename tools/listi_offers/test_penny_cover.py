import copy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import unittest
import collect as c
import more_markets as m

class PennyCoverTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads((Path(__file__).parent/'penny_cover_banana_2026w46.json').read_text())
  self.words=[c.Word(**w) for w in self.data['words']]
  self.prices=[c.Word(**w) for w in self.data['prices']]
  self.source=c.Source('PENNY','Eichenau','https://penny-publish.blaetterkatalog.de/test.pdf','https://penny-publish.blaetterkatalog.de/test',date(2026,11,9),date(2026,11,14))
 def offer(self,**kw):
  args=dict(blocks=self.data['blocks'],words=self.words,prices=self.prices,source=self.source,
            bounds=(self.source.start,self.source.end),page=1,sha='a'*64,width=self.data['width'],height=self.data['height'])
  args.update(kw)
  return m.penny_cover_banana(**args)
 def test_actual_cover_fields(self):
  o=self.offer();c.validate_offer(o)
  self.assertEqual((o['title'],o['category'],o['variants'],o['priceCents'],o['quantityGrams']),('CHIQUITA Bananen','fruit',['banana'],199,1000))
  self.assertEqual(o['validFrom'],'2026-11-09')
  self.assertEqual(o['validTo'],'2026-11-14')
  self.assertEqual(o['verificationMethod'],'pdf_1kg_price')
 def test_price_is_read_not_fixed(self):
  prices=[replace(w,value='2.29') if w.x0>390 and w.y0<200 else w for w in self.prices]
  self.assertEqual(self.offer(prices=prices)['priceCents'],229)
 def test_requires_all_neighbour_anchors(self):
  for i in range(3):
   blocks=copy.deepcopy(self.data['blocks']);blocks.pop(i)
   self.assertIsNone(self.offer(blocks=blocks))
 def test_wrong_price_geometry_is_rejected(self):
  prices=[replace(w,y0=300,y1=330) if w.x0>390 and w.y0<200 else w for w in self.prices]
  self.assertIsNone(self.offer(prices=prices))
 def test_ambiguous_price_is_rejected(self):
  self.assertIsNone(self.offer(prices=self.prices+[next(w for w in self.prices if w.x0>390 and w.y0<200)]))
 def test_wrong_unit_price_anchor_is_rejected(self):
  prices=[replace(w,value='4.99') if w.x0<330 else w for w in self.prices]
  self.assertIsNone(self.offer(prices=prices))
 def test_app_condition_is_rejected(self):
  self.assertIsNone(self.offer(words=self.words+[c.Word('Nur mit App',401,140,445,154,10)]))
 def test_other_market_page_and_quantity_are_rejected(self):
  self.assertIsNone(self.offer(source=replace(self.source,market='REWE')))
  self.assertIsNone(self.offer(page=2))
  blocks=copy.deepcopy(self.data['blocks'])
  for b in blocks:b['text']=b['text'].replace('je kg','je Stück')
  self.assertIsNone(self.offer(blocks=blocks))

class CatalogVersionTests(unittest.TestCase):
 def test_same_day_changed_content_gets_new_version(self):
  today=date(2026,11,9)
  first=[{'id':'one','priceCents':199}]
  self.assertNotEqual(c.catalog_version(today,first),c.catalog_version(today,[*first,{'id':'two','priceCents':99}]))
  self.assertNotEqual(c.catalog_version(today,first),c.catalog_version(today,[{'id':'one','priceCents':229}]))
 def test_identical_content_keeps_version_regardless_of_order(self):
  rows=[{'id':'one','priceCents':199},{'id':'two','priceCents':99}]
  self.assertEqual(c.catalog_version(date(2026,11,9),rows),c.catalog_version(date(2026,11,9),list(reversed(rows))))

if __name__=='__main__':unittest.main()
