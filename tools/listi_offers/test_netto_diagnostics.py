from datetime import date
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
import netto_source as n
import test_lidl_netto_native as native_tests

class NettoDiagnosticsTests(TestCase):
 def test_each_http_failure_names_its_stage(self):
  base=native_tests.NettoResolverTests()
  for stage,hit in [('Filialseite',lambda u:u==n.BRANCH),('Wochenprospekt',lambda u:'hz46_ehos/?' in u),('Regionalzuordnung',lambda u:u.endswith('hz46.json')),('Optionale Filialausgabe',lambda u:'_sid8342/' in u)]:
   def read(url):
    if hit(url):raise HTTPError(url,403,'Forbidden',{},None)
    return base.respond(url)
   with self.subTest(stage=stage),patch('collect.text',side_effect=read),patch('netto_browser.read_branch',side_effect=RuntimeError('Browser nicht freigegeben')):
    with self.assertRaises((n.NettoHTTPError,RuntimeError)) as caught:n.resolve_netto(date(2026,11,10))
    self.assertIn(stage,str(caught.exception));self.assertIn('HTTP 403',str(caught.exception))
    self.assertNotIn('?',str(caught.exception))
 def test_optional_404_keeps_official_branch_link(self):
  base=native_tests.NettoResolverTests()
  with patch('collect.text',side_effect=base.respond):
   self.assertEqual(n.resolve_netto(date(2026,11,10)).source_url,'https://wochenprospekt.netto-online.de/hz46_ehos/?storeid=8342')
