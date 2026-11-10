"""Normal, isolated browser read of the one configured public reference branch.
No login, challenge interaction, consent clicks, stealth options or proxying.
"""
from urllib.parse import urlparse

HOST='www.netto-online.de'
PATH='/filialen/puchheim/benzstr-38/8342'

def allowed_branch(url):
 u=urlparse(url)
 return (u.scheme=='https' and u.hostname==HOST and not u.username
         and not u.password and u.port in (None,443)
         and u.path.rstrip('/').lower()==PATH and not u.query and not u.fragment)

def read_branch(url, factory=None):
 if not allowed_branch(url):raise ValueError('Nicht bestätigte Netto-Filialadresse')
 if factory is None:
  from playwright.sync_api import sync_playwright
  factory=sync_playwright
 with factory() as runtime:
  browser=runtime.chromium.launch(headless=True)
  try:
   context=browser.new_context(accept_downloads=False)
   page=context.new_page()
   response=page.goto(url,wait_until='domcontentloaded',timeout=25000)
   if response is None or response.status!=200:
    raise ValueError(f'Filialseite HTTP {response.status if response else "ohne Antwort"}')
   if not allowed_branch(page.url):raise ValueError('Unerwartete Filialweiterleitung')
   page.wait_for_selector('script[type="application/ld+json"]',state='attached',timeout=8000)
   # No controls are clicked. A blocked/challenge response cannot supply a
   # successful result unless the existing resolver verifies address, geo and
   # the explicit store-specific publication link in the normal document.
   html=page.content()
   if not allowed_branch(page.url) or len(html.encode('utf-8'))>4000000:
    raise ValueError('Filialseite ungültig oder zu groß')
   return html
  finally:browser.close()
