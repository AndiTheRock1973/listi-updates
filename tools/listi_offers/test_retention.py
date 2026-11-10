from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import collect as c

class RetentionTests(TestCase):
 def previous(self):
  return {'offers':[
   {'id':'current','title':'current','market':'Lidl','validFrom':'2026-11-09','validTo':'2026-11-14'},
   {'id':'thursday','title':'thursday','market':'Lidl','validFrom':'2026-11-12','validTo':'2026-11-14'},
   {'id':'expired','title':'expired','market':'Lidl','validFrom':'2026-11-02','validTo':'2026-11-07'},
   {'id':'distant','title':'distant','market':'Lidl','validFrom':'2026-12-01','validTo':'2026-12-05'}]}
 def collect(self,today):
  source=c.Source('PENNY','Eichenau','https://penny-publish.blaetterkatalog.de/complete.pdf','https://penny-publish.blaetterkatalog.de/viewer',date(2026,11,9),date(2026,11,14))
  with TemporaryDirectory() as tmp,patch('collect.penny_source',return_value=source),patch('collect.collect_penny',return_value=[]),patch('collect.lidl_source',side_effect=ValueError('blocked')),patch('collect.fetch',return_value=b'%PDF-test'):
   return c.collect(today,Path(tmp),self.previous(),include_all=False)
 def test_current_and_thursday_kept_with_original_dates(self):
  result=self.collect(date(2026,11,10))
  self.assertEqual({o['id'] for o in result['offers']},{'current','thursday'})
  self.assertEqual(next(o for o in result['offers'] if o['id']=='thursday')['validFrom'],'2026-11-12')
  self.assertTrue(all(o['validTo']=='2026-11-14' for o in result['offers']))
 def test_expiry_never_extended(self):
  self.assertEqual(self.collect(date(2026,11,15))['offers'],[])
