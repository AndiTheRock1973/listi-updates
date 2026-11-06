from datetime import date
from pathlib import Path
import tempfile
import unittest
import fitz
import collect as c
import more_markets as m
import product_types as t
from publish import compatible,legacy

class ProductTypeTests(unittest.TestCase):
 def test_bread_categories(self):
  for text in ['Harry\nButtertoast\nje 500 g (1 kg = 2.58)', 'Golden Toast\nVollkorntoast\n500 g',
               'Golden Toast\nAmerican Sandwich\n750 g','Weizentoast\n500 g']:
   self.assertEqual(c.category_of(text),'toast',text)
 def test_non_bread_never_matches_toast(self):
  for text in ['Toastschinken\n155 g','Toaster\nStueck','Golden Toast\nHamburger Buns\n500 g',
               'Nutella Creme\nLecker auf Toast\n500 g','Rinderburger Toast\n500 g']:
   self.assertIsNone(c.category_of(text),text)
 def test_beef_species_and_preparation(self):
  for text in ['Rinder-Hackfleisch\n500 g','Muehlenhof\nRindergulasch\n500 g',
               'Jungbullen-Steaks\n100 g','Rinderbraten\n500 g','Rinderfilet\n500 g']:
   self.assertEqual(c.category_of(text),'beef',text)
  for text in ['Hackfleisch gemischt vom Rind und Schwein\n100 g','Schweine-Rueckensteaks\n240 g',
               'Pulled Beef Rinderbrust schonend gegart\n320 g','Lasagne mit 100% Rindfleisch\n400 g',
               'Rindfleischsalami\n100 g','Rindergulasch in der Dose\n500 g','Rinderburger mit Ketchup\n320 g',
               'Suppe mit Rind\n750 ml','Entrecote Merlot Cabernet\n0,75 l Flasche',
               'Filetsteak vom Rind versch. Gewichte z. B. 259 g']:
   if 'salami' in text.lower():self.assertEqual(c.category_of(text),'sausage')
   elif text.startswith('Schweine-'):self.assertEqual(c.category_of(text),'pork')
   else:self.assertIsNone(c.category_of(text),text)
 def test_exact_food_types(self):
  self.assertEqual(t.tags('Rinder-Hackfleisch 5% Fett, zum Braten','beef')[0],['mince'])
  self.assertEqual(t.tags('Rinder-Gulasch','beef')[0],['stew'])
  self.assertEqual(t.tags('Rumpsteak vom Rind','beef')[0],['steak','rump'])
  self.assertEqual(t.tags('Jungbullen-Steaks','beef')[0],['steak','youngbull'])
  self.assertEqual(t.tags('Buttertoast','toast')[0],['butter'])
  self.assertEqual(t.tags('Vollkorntoast','toast')[0],['wholegrain'])
 def test_leading_price_is_not_a_brand(self):
  text='6.99\nMUEHLENHOF\nFrisches Rinder-Gulasch\nje 500-g-Packung\n(1 kg = 13.98)'
  self.assertEqual(t.brand(t.caption(text),'beef'),'MUEHLENHOF')
  self.assertEqual(c.checked_price(t.caption(text),[c.Word('6.99',1,1,30,40,30)]),(699,500,1398))
 def test_counter_evidence_and_not_fake_package(self):
  source=c.Source('REWE','Alling','https://view.publitas.com/89773/test.pdf','https://www.rewe.de/',date(2026,11,2),date(2026,11,7))
  price=c.Word('2.49',1,1,30,40,30)
  offer=m.counter_offer('Irische\nRinder-Hueftsteaks\nje 100 g',[price],price,source,(source.start,source.end),10,'a'*64)
  # ASCII ue isn't the normal PDF spelling: use the German source spelling.
  offer=m.counter_offer('Irische\nRinder-Hüftsteaks\nje 100 g',[price],price,source,(source.start,source.end),10,'a'*64)
  c.validate_offer(offer)
  self.assertEqual(offer['quantityGrams'],100)
  self.assertIn('kein fester Packungspreis',offer['note'])
  self.assertNotIn('printedUnitPriceCents',offer['evidence'])
  self.assertIsNone(m.counter_offer('Hackfleisch gemischt Rind und Schwein\n100 g',[price],price,source,(source.start,source.end),10,'a'*64))
  offer['quantityGrams']=500
  with self.assertRaises(ValueError):c.validate_offer(offer)
 def test_toast_pack_price_and_type(self):
  source=c.Source('AEZ','City Point','https://aez.de/test.pdf','https://aez.de/',date(2026,11,2),date(2026,11,7))
  parsed=m.canonical_caption('Harry\nVollkorntoast\n500 g Packung\n(1 kg = 2.58)')
  offer=c.offer_from(parsed[0],[c.Word('1.29',1,1,30,40,30)],source,(source.start,source.end),4,'a'*64,'pdf_text_crosscheck')
  c.validate_offer(offer)
  self.assertEqual(offer['variants'],['wholegrain'])
  self.assertIn('wholegrain',offer['attributes'])
 def test_older_feeds_never_receive_new_categories(self):
  data={'offers':[{'market':'PENNY','category':'beef','verificationMethod':'pdf_text_crosscheck'},
                  {'market':'AEZ','category':'toast','verificationMethod':'pdf_text_crosscheck'},
                  {'market':'Lidl','category':'pasta','verificationMethod':'ocr_unitprice_crosscheck'}],
        'sources':[{'market':name,'state':'ok','count':99} for name in c.MARKET_PDF_HOSTS]}
  for result in [legacy(data),compatible(data,set(c.MARKET_PDF_HOSTS))]:
   self.assertEqual([o['category'] for o in result['offers']],['pasta'])
   self.assertEqual(next(s for s in result['sources'] if s['market']=='PENNY')['count'],0)
 def test_regionally_restricted_beef_is_not_asserted_for_local_edeka(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'regional.pdf';doc=fitz.open();page=doc.new_page(width=500,height=650)
   page.insert_text((20,25),'Gueltig vom 02.11. - 07.11.2026',fontsize=10)
   page.insert_textbox(fitz.Rect(30,150,170,225),'Jungbullen-Steaks*\naus der Keule\n100 g',fontsize=10)
   page.insert_text((80,255),'2.19',fontsize=35)
   page.insert_text((20,620),'* Nicht in allen Märkten erhältlich.',fontsize=8)
   doc.save(path);doc.close()
   src=c.Source('EDEKA','Eichenau','https://blaetterkatalog.edeka.de/test.pdf','https://blaetterkatalog.edeka.de/',date(2026,11,2),date(2026,11,7))
   self.assertEqual(m.native_collect(path,src),[])

 def test_price_above_label_belongs_to_same_field(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'steak.pdf';doc=fitz.open();page=doc.new_page(width=500,height=650)
   page.insert_text((20,25),'45. Woche 2026. Gueltig ab 02.11.2026',fontsize=10)
   page.insert_text((80,120),'2.49',fontsize=40)
   page.insert_textbox(fitz.Rect(60,135,170,220),'Rinder-Steaks\nje 100 g',fontsize=10)
   doc.save(path);doc.close()
   src=c.Source('REWE','Alling','https://view.publitas.com/89773/test.pdf','https://www.rewe.de/',date(2026,11,2),date(2026,11,7))
   offers=m.native_collect(path,src)
   self.assertEqual(len(offers),1)
   self.assertEqual(offers[0]['priceCents'],249)

if __name__=='__main__':unittest.main()
