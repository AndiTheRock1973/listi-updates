from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import pantry
import collect as c

class ColaAlcoholTests(TestCase):
 def test_alcohol_mix_is_not_cola(self):
  for name in ['BULLEIT Whiskey & Cola Alkohol- und koffeinhaltiges Mischgetränk', 'Jack Daniels Whisky Cola', 'Bourbon & Cola', 'Rum-Cola', 'Vodka Cola', 'Wodka-Cola', 'Gin und Cola', 'Cola Cocktail', 'Cola Likör', 'Cola alkoholhaltig']:
   with self.subTest(name=name):self.assertEqual(pantry.category(name),'reject')
 def test_soft_drink_assortment_stays(self):
  for name in ['Coca-Cola, Fanta, Sprite oder Mezzo Mix verschiedene Sorten', 'COCA-COLA Friendspack versch. Sorten', 'Pepsi verschiedene Sorten', 'Coca-Cola Original Taste', 'Cola Zero Zucker', 'Cola ohne Zucker', 'Cola alkoholfrei']:
   with self.subTest(name=name):self.assertEqual(pantry.category(name),'cola')
 def test_unknown_zero_is_not_guessed(self):
  self.assertNotIn('zero',pantry.tags('Coca-Cola Fanta Sprite verschiedene Sorten','cola')[0])
  self.assertIn('zero',pantry.tags('Cola Zero','cola')[0])
 def test_bad_previous_cola_does_not_survive_source_failure(self):
  def old(id,title,caption):
   return {'id':id,'title':title,'market':'Lidl','category':'cola','brand':title,
    'validFrom':'2026-11-09','validTo':'2026-11-14','evidence':{'caption':caption}}
  previous={'offers':[old('bad','Whiskey & Cola','Whiskey & Cola'),old('caption','Cola','alkoholhaltig'),old('good','Coca-Cola Fanta Sprite','Coca-Cola Fanta Sprite verschiedene Sorten')]}
  source=c.Source('PENNY','Eichenau','https://penny-publish.blaetterkatalog.de/complete.pdf','https://penny-publish.blaetterkatalog.de/viewer',date(2026,11,9),date(2026,11,14))
  with TemporaryDirectory() as tmp,patch('collect.penny_source',return_value=source),patch('collect.collect_penny',return_value=[]),patch('collect.lidl_source',side_effect=ValueError('blocked')),patch('collect.fetch',return_value=b'%PDF-test'):
   result=c.collect(date(2026,11,10),Path(tmp),previous,include_all=False)
  self.assertEqual([o['id'] for o in result['offers']],['good'])
