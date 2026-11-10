from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock,patch
from urllib.error import HTTPError
import netto_browser as b
import netto_source as n
import test_lidl_netto_native as native_tests

class NettoBrowserTests(TestCase):
 def runtime(self,status=200,url=n.BRANCH,html='normal branch'):
  manager=MagicMock();runtime=manager.__enter__.return_value
  browser=runtime.chromium.launch.return_value
  page=browser.new_context.return_value.new_page.return_value
  page.goto.return_value=SimpleNamespace(status=status)
  page.url=url;page.content.return_value=html
  return manager,browser,page
 def test_only_exact_reference_branch_allowed(self):
  self.assertTrue(b.allowed_branch(n.BRANCH))
  for u in ['http://www.netto-online.de'+b.PATH,'https://other.example'+b.PATH,'https://user@www.netto-online.de'+b.PATH,'https://www.netto-online.de:444'+b.PATH,n.BRANCH+'?storeid=1',n.BRANCH+'/different','https://www.netto-online.de/filialen/other/1']:
   with self.subTest(url=u):self.assertFalse(b.allowed_branch(u))
 def test_normal_document_read_and_browser_closed(self):
  manager,browser,page=self.runtime()
  self.assertEqual(b.read_branch(n.BRANCH,lambda:manager),'normal branch')
  browser.close.assert_called_once()
  page.click.assert_not_called()
  page.goto.assert_called_once_with(n.BRANCH,wait_until='domcontentloaded',timeout=25000)
 def test_block_redirect_and_oversize_fail_closed(self):
  for args in [{'status':403},{'url':'https://example.com/branch'},{'html':'x'*4000001}]:
   manager,browser,page=self.runtime(**args)
   with self.subTest(args=list(args)),self.assertRaises(ValueError):b.read_branch(n.BRANCH,lambda:manager)
   browser.close.assert_called_once();page.click.assert_not_called()
 def test_browser_payload_still_passes_original_branch_validation(self):
  base=native_tests.NettoResolverTests()
  def read(url):
   if url==n.BRANCH:raise HTTPError(url,403,'Forbidden',{},None)
   return base.respond(url)
  with patch('collect.text',side_effect=read),patch('netto_browser.read_branch',return_value=base.branch()) as browser:
   edition=n.resolve_netto(date(2026,11,10))
   self.assertEqual(edition.market,'Netto');browser.assert_called_once_with(n.BRANCH)
  for html in [base.branch('Andere Straße 1'),'<html>Verify you are human</html>']:
   with patch('collect.text',side_effect=read),patch('netto_browser.read_branch',return_value=html),self.assertRaises(ValueError):n.resolve_netto(date(2026,11,10))
 def test_no_browser_for_service_errors(self):
  with patch('collect.text',side_effect=HTTPError(n.BRANCH,503,'Unavailable',{},None)),patch('netto_browser.read_branch') as browser:
   with self.assertRaises(n.NettoHTTPError):n.resolve_netto(date(2026,11,10))
   browser.assert_not_called()
