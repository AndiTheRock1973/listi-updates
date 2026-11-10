from datetime import date
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
from urllib.error import HTTPError
import fitz
import collect as c
import more_markets as m
import netto_source as n
from publish import compatible

class NativeRetailerTests(unittest.TestCase):
 def source(self,market='Lidl'):
  host='assets.leaflets.schwarz' if market=='Lidl' else 'view.publitas.com'
  path='/100989/1/pdfs/12345678-1234-1234-1234-123456789abc.pdf' if market=='Netto' else '/example.pdf'
  return c.Source(market,'Referenzfiliale','https://'+host+path,'https://www.lidl.de/' if market=='Lidl' else n.BRANCH,date(2026,11,9),date(2026,11,14))
 def pdf(self,path,price='1.99',period='Ab Mo. 9.11. bis Sa. 14.11.',app=False,netto=False):
  doc=fitz.open();page=doc.new_page(width=500,height=700)
  page.insert_text((20,25),period,fontsize=10)
  # Text-rich pages must use native extraction, not OCR. Put filler far away.
  page.insert_textbox(fitz.Rect(300,50,490,600),'Hinweis zur Filiale. '*90,fontsize=7)
  caption='MILBONA\nEdamer\nIn Scheiben.\nJe 400 g\n1 kg = 4.98' if not netto else 'GOUDA\nKaesescheiben\ngekuehlt\n400 g\n(4.98 / kg)'
  page.insert_textbox(fitz.Rect(30,150,150,290),caption,fontsize=10)
  page.insert_text((120,255),price,fontsize=30)
  if app:page.insert_text((120,230),'APP',fontsize=10)
  doc.save(path);doc.close()
 def test_lidl_native_dispatch_avoids_ocr(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'lidl.pdf';self.pdf(p)
   with patch('collect.ocr',side_effect=AssertionError('Native PDF sent to OCR')):
    offers=c.collect_lidl(p,self.source(),Path(t))
   self.assertEqual(len(offers),1);self.assertEqual(offers[0]['priceCents'],199)
   c.validate_offer(offers[0])
 def test_netto_printed_per_kg_is_crosschecked(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'netto.pdf';self.pdf(p,netto=True)
   offers=m.native_collect(p,self.source('Netto'))
   self.assertEqual(len(offers),1);self.assertEqual(offers[0]['category'],'cheese');c.validate_offer(offers[0])
 def test_wrong_price_app_and_absent_period_rejected(self):
  for params in [dict(price='1.89'),dict(app=True),dict(period='Informationen zur Filiale')]:
   with self.subTest(params=params),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'test.pdf';self.pdf(p,**params)
    if 'period' in params:
     with self.assertRaises(ValueError):m.native_collect(p,self.source())
    else:self.assertEqual(m.native_collect(p,self.source()),[])
 def test_future_page_keeps_its_start(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'test.pdf';self.pdf(p)
   d=fitz.open(p);d[0].insert_text((20,680),'Ab Do. 12.11. bis Sa. 14.11.',fontsize=10)
   q=Path(t)/'ambiguous.pdf';d.save(q);d.close()
   # The page now has conflicting complete periods. It must be skipped.
   self.assertEqual(m.native_collect(q,self.source()),[])
 def test_explicit_weekday_and_two_digit_year(self):
  self.assertEqual(m.range_in('Montag 09.11. – Samstag 14.11.26',2026),(date(2026,11,9),date(2026,11,14)))
  self.assertEqual(m.range_in('Montag 09.11. – Samstag 14.11.25',2026),(date(2025,11,9),date(2025,11,14)))
 def test_prepared_cheese_not_plain_cheese(self):
  import pantry
  self.assertEqual(pantry.category('DELUXE Käsespätzle'),'reject')
 def test_netto_not_in_older_compatibility_feed(self):
  self.assertEqual(compatible({'offers':[{'market':'Netto'}],'sources':[]}, {'Lidl','PENNY'})['offers'],[])

class NettoResolverTests(unittest.TestCase):
 def branch(self,street='Benzstr. 38'):
  return '<script type="application/ld+json">'+json.dumps({'address':{'postalCode':'82178','streetAddress':street},'geo':{'latitude':48.173901,'longitude':11.367066}})+'</script><a href="https://wochenprospekt.netto-online.de/hz46_ehos/?storeid=8342">Prospekt</a>'
 def respond(self,url,wrong=False,publisher='100989',status=404):
  if url==n.BRANCH:return self.branch('Andere Straße 1' if wrong else 'Benzstr. 38')
  if url.endswith('hz46.json'):return '{}'
  if '_sid8342/' in url:raise HTTPError(url,status,'test',{},None)
  if 'wochenprospekt.netto-online.de' in url:return 'routingBaseUrl: \'https://scripts.publitas.com/netto-online/custom-routing\' name="asset-root" 09.11. – Samstag 14.11.26 "downloadPdfUrl":"https://view.publitas.com/'+publisher+'/1/pdfs/12345678-1234-1234-1234-123456789abc.pdf"'
  raise AssertionError(url)
 def test_official_branch_and_read_only_routing(self):
  with patch('collect.text',side_effect=self.respond) as fetch:
   s=n.resolve_netto(date(2026,11,10));self.assertEqual(s.market,'Netto');self.assertEqual(s.start,date(2026,11,9))
  self.assertFalse(any('AddStoreID' in call.args[0] for call in fetch.call_args_list))
 def test_wrong_address_publisher_expiry_and_server_error(self):
  for opts,today in [({'wrong':True},date(2026,11,10)),({'publisher':'999'},date(2026,11,10)),({},date(2026,11,15)),({'status':503},date(2026,11,10))]:
   with self.subTest(opts=opts,today=today),patch('collect.text',side_effect=lambda url:self.respond(url,**opts)):
    with self.assertRaises((ValueError,HTTPError)):n.resolve_netto(today)

if __name__=='__main__':unittest.main()
