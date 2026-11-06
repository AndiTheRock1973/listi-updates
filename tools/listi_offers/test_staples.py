import copy
from datetime import date
import unittest
import collect as c
import staples as s
import staple_fields as f
from publish import compatible
SRC=c.Source('PENNY','Eichenau','https://penny-publish.blaetterkatalog.de/test.pdf','https://penny-publish.blaetterkatalog.de/test',date(2026,11,2),date(2026,11,7))
def make(raw,price):
 w=c.Word(price,20,60,60,90,30)
 return f.offer(raw,[w],SRC,(SRC.start,SRC.end),1,'a'*64,(10,10,100,50),[w])
class StapleTests(unittest.TestCase):
 def test_all_new_groups(self):
  for raw,cat in [('Roggenbrot','bread'),('Freiland Eier','eggs'),('Naturjoghurt','yogurt'),('Magerquark','quark'),('Schlagsahne','cream'),('Hähnchenbrustfilet','poultry'),('Schweinenackensteak','pork'),('Äpfel','fruit'),('Speisekartoffeln','vegetables'),('Basmati Reis','rice'),('Dinkelmehl Type 630','flour')]:
   self.assertEqual(c.category_of(raw),cat,raw)
 def test_ingredients_nonfoods_and_cooked_products_are_not_staples(self):
  for raw in ['Amarylliszwiebel','GARDENLINE Amaryllis Zwiebelgröße 26/28','OMNIVIT Heiße Zitrone','Brausetabletten Zitronengeschmack','Franzbrötchen Style Creme','Nudel- oder Pellkartoffelsalat','passierte Tomaten','Tomaten- mark','Reisdrink','Reiswaffeln','Rind und Schwein Hackfleisch gemischt','Hähnchen Nuggets','Weizen Backmischung','Eierlikör','Gekochte Eier']:
   self.assertNotIn(c.category_of(raw),s.CATEGORIES,raw)
  self.assertEqual(c.category_of('Geflügel-Mortadella'),'sausage')
  self.assertNotEqual(c.category_of('Sauerrahmbutter'),'cream')
 def test_meat_and_cheese_not_ingredient_substitutions(self):
  self.assertEqual(c.category_of('Hähnchenbrust natur frisch'),'poultry')
  self.assertIsNone(c.category_of('Pulled Pork Schweinefleisch gegart'))
 def test_flour_and_rice_types(self):
  self.assertEqual(s.tags('Dinkelmehl Type 630','flour')[0],['spelt','type630'])
  self.assertIn('basmati',s.tags('Basmati Reis','rice')[0])
 def test_egg_pack_is_count_not_weight(self):
  o=make('Freiland Eier\n10 Stück (1 Stück = 0.20)','1.99');c.validate_offer(o)
  self.assertEqual(o['quantityCount'],10)
  self.assertNotIn('quantityGrams',o)
  self.assertIsNone(make('Freiland Eier\n10 Stück','1.99'))
  self.assertIsNone(make('Freiland Eier\n10 Stück (1 Stück = 0.20)','2.99'))
 def test_piece_produce_price(self):
  o=make('Gurke\nje Stück','0.77');c.validate_offer(o)
  self.assertEqual(o['quantityCount'],1)
  self.assertEqual(o['verificationMethod'],'pdf_piece_price')
 def test_loose_produce_price_basis_not_fake_pack(self):
  o=make('Bananen\nje kg','1.11');c.validate_offer(o)
  self.assertEqual(o['quantityGrams'],1000)
  self.assertIn('kein fester Packungspreis',o['note'])
 def test_kg_bags_and_unit_prices(self):
  o=make('Speisekartoffeln\n2 kg (1 kg = 1.00)','1.99');c.validate_offer(o)
  self.assertEqual(o['quantityGrams'],2000)
  self.assertIsNone(make('Speisekartoffeln\n2 kg (1 kg = 1.00)','2.99'))
 def test_cream_volume(self):
  o=make('Schlagsahne\n200 ml (1 l = 4.95)','0.99');c.validate_offer(o)
  self.assertEqual(o['quantityMl'],200)
  self.assertEqual(o['category'],'cream')
 def test_app_proof_and_count_corruption(self):
  self.assertIsNone(make('Freiland Eier nur mit App\n10 Stück (1 Stück = 0.20)','1.99'))
  o=make('Freiland Eier\n10 Stück (1 Stück = 0.20)','1.99')
  for change in [{'quantityGrams':500},{'quantityCount':6},{'variants':[]},{'verificationMethod':'pdf_text_crosscheck'}]:
   wrong=copy.deepcopy(o);wrong.update(change)
   with self.assertRaises(ValueError):c.validate_offer(wrong)
 def test_older_feeds_do_not_receive_new_units_or_categories(self):
  old={'market':'PENNY','category':'cola','verificationMethod':'pdf_volume_crosscheck'}
  data={'schemaVersion':3,'offers':[old,make('Gurke\nje Stück','0.77'),make('Bananen\nje kg','1.11')],'sources':[{'market':'PENNY','state':'ok','count':3}]}
  v4=compatible(data,{'PENNY'},pantry_groups=True)
  self.assertEqual(v4['schemaVersion'],2)
  self.assertEqual(v4['offers'],[old])
if __name__=='__main__':unittest.main()
