"""Synthetic product panels; no test records enter published offer data."""
import copy
import unittest
from datetime import date
import collect as c
import pantry as p
import pantry_fields as f
from publish import compatible

SRC=c.Source('PENNY','Eichenau','https://penny-publish.blaetterkatalog.de/test.pdf','https://penny-publish.blaetterkatalog.de/test',date(2026,11,2),date(2026,11,7))

def make(raw,price):
 return f.offer(raw,[c.Word(price,10,10,40,45,30)],SRC,(SRC.start,SRC.end),1,'a'*64)

class PantryTests(unittest.TestCase):
 def test_distinct_grocery_categories(self):
  for raw,cat in [('H-Milch','milk'),('Nudel Sauce','pasta_sauce'),('Pesto','pasta_sauce'),('Coca-Cola','cola'),('Käse-Bockwurst','sausage'),('Leberkäse','sausage'),('Gouda','cheese')]:
   self.assertEqual(c.category_of(raw),cat,raw)
 def test_no_nonfood_or_prepared_false_positives(self):
  for raw in ['Rucola','Chocolate Eis','Milchaufschäumer','Milch Aufschäumer','Käsereibe','Hafermilch','Milchbrötchen','Milch Mäuse','Käsekuchen','Pizza Vier Käse','Wiener Art Schnitzel','Frankfurter Kranz']:
   self.assertIsNone(c.category_of(raw),raw)
 def test_zero_not_inferred_from_various_sorts(self):
  self.assertNotIn('zero',p.tags('Cola verschiedene Sorten','cola')[0])
  self.assertNotIn('zero',p.tags('Cola light','cola')[0])
  self.assertIn('zero',p.tags('Cola Zero Zucker','cola')[0])
  self.assertIn('zero',p.tags('Cola ohne Zucker','cola')[0])
 def test_milk_fat_and_lactose(self):
  v,a=p.tags('H-Milch 1,5/3,5 % auch laktosefrei','milk')
  self.assertTrue({'fat15','fat35','lactose_option','shelf'}<=set(v))
  self.assertIn('lactosefree',a)
 def test_line_breaks_do_not_change_qualifiers(self):
  raw='Bärenmarke\nFrische oder\nHaltbare Milch\n3,8%/3,5% Fett'
  self.assertEqual(p.tags(raw,'milk'),p.tags(raw.replace('\n',' '),'milk'))
 def test_volume_multipack_arithmetic_and_deposit(self):
  o=make('Coca-Cola Zero\n12 x 1 l (1 l = 1.00)\nzzgl. 3,30 Pfand','11.99')
  c.validate_offer(o)
  self.assertEqual(o['quantityMl'],12000)
  self.assertNotIn('quantityGrams',o)
  self.assertEqual(o['depositCents'],330)
  self.assertEqual(o['priceCents'],1199)
 def test_fractional_litres_and_rounded_unit_price(self):
  o=make('Pepsi\n1,75 l (1 l = 0.68)','1.19');c.validate_offer(o)
  self.assertEqual(o['quantityMl'],1750)
  self.assertIsNone(make('Pepsi\n1,75 l (1 l = 0.68)','1.29'))
 def test_single_litre_without_unit_price(self):
  o=make('Bärenmarke\nH-Milch 3,5%\nje 1-l-Packung','0.99');c.validate_offer(o)
  self.assertEqual(o['verificationMethod'],'pdf_1l_price')
  self.assertIsNone(make('Milch\n1 l','30'))
  self.assertIsNone(make('Milch\n500 ml','0.99'))
 def test_app_and_ambiguous_prices_excluded(self):
  self.assertIsNone(make('Milch\n1 l\nnur mit App','0.99'))
  self.assertIsNone(make('Milch\n1 l und 500 ml','0.99'))
 def test_proof_and_units_cannot_be_relabelled(self):
  o=make('Cola Zero\n2 l (1 l = 0.75)','1.49')
  for change in [{'quantityGrams':2000},{'variants':[]},{'category':'milk'},{'depositCents':-25},{'quantityMl':1000}]:
   wrong=copy.deepcopy(o);wrong.update(change)
   with self.assertRaises(ValueError):c.validate_offer(wrong)
 def test_old_apps_receive_only_supported_groups(self):
  data={'schemaVersion':2,'offers':[make('Cola Zero\n2 l (1 l = 0.75)','1.49'),{'market':'PENNY','category':'beef','verificationMethod':'pdf_100g_price'}],'sources':[{'market':'PENNY','state':'ok','count':2}]}
  old=compatible(data,{'PENNY'},extended=True)
  self.assertEqual(old['schemaVersion'],1)
  self.assertEqual([o['category'] for o in old['offers']],['beef'])
  self.assertEqual(old['sources'][0]['count'],1)

if __name__=='__main__':unittest.main()
