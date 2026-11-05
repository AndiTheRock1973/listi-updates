from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fitz
import collect as c
import more_markets as m
from publish import legacy


class MoreMarketTests(unittest.TestCase):
    def test_printed_ranges_and_new_year(self):
        self.assertEqual(m.range_in('Gültig vom 02.11. - 07.11.2026', 2026), (date(2026,11,2), date(2026,11,7)))
        self.assertEqual(m.range_in('Mo. 28.12. – Sa. 2.1.2027', 2027), (date(2026,12,28), date(2027,1,2)))
        self.assertIsNone(m.range_in('02.11. - 28.11.2026', 2026))

    def test_multipack_is_checked_not_guessed(self):
        raw='BARISSIMO\nKaffee-Pads\nVersch. Sorten\nje 20 x 7 g =\n140-g-Packung;\nkg-Preis 13.50'
        parsed=m.canonical_caption(raw)
        self.assertEqual(parsed[1:], (189, 140))
        self.assertIsNone(m.canonical_caption(raw.replace('140-g','150-g')))

    def test_alternatives_and_prepared_food_excluded(self):
        for text in ['MIRÁCOLI\nPasta-Soße\nje 675-g-Glas; kg-Preis 3.69',
                     'Jacobs\nKaffee\nje 200- bzw. 225-g-Packung; kg-Preis 22.45 bzw. 19.96',
                     'De Cecco\nProtein Pasta\n400 g Packung\n1 kg = 4.98',
                     'Président\nMeersalz Butter\n250-g-Packung; kg-Preis 9.96',
                     'Pasta\nje 500g Beutel\n1kg=3.38']:
            self.assertIsNone(m.canonical_caption(text),text)

    def source(self,market='AEZ'):
        host=c.MARKET_PDF_HOSTS[market]
        return c.Source(market,'Local market',f'https://{host}/complete.pdf',m.ENTRY[market][1],
                        date(2026,11,2),date(2026,11,7))

    def create_pdf(self,path,price='5.99',app=False,small_price=False,kilogram=False):
        doc=fitz.open();page=doc.new_page(width=500,height=650)
        page.insert_text((20,25),'Gueltig vom 02.11. - 07.11.2026',fontsize=10)
        if kilogram:
            page.insert_text((30,165),price,fontsize=30)
            page.insert_textbox(fitz.Rect(30,200,150,300),'KAEFER\nKaffee Bohnen\n1 kg\nversch. Sorten',fontsize=10)
        else:
            page.insert_textbox(fitz.Rect(30,150,160,270),'Jacobs\nKaffee Kroenung\n500 g Packung\n(1 kg = 11.98)',fontsize=10)
            page.insert_text((130,240),price,fontsize=9 if small_price else 30)
            if app:page.insert_text((130,205),'APP PREIS',fontsize=10)
        doc.save(path);doc.close()

    def test_native_price_pack_and_app_conditions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'offer.pdf'
            self.create_pdf(path)
            offers=m.native_collect(path,self.source())
            self.assertEqual(len(offers),1)
            self.assertEqual(offers[0]['priceCents'],599)
            c.validate_offer(offers[0])
            for options in [{'price':'6.99'},{'app':True},{'small_price':True}]:
                path.unlink();self.create_pdf(path,**options)
                self.assertEqual(m.native_collect(path,self.source()),[],options)

    def test_later_day_never_inherits_monday(self):
        for header, expected in [('ab Fr. 6.11.', '2026-11-06'), ('ab Freitag 6.11.', None)]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'offer.pdf';self.create_pdf(path)
                document=fitz.open(path)
                document[0].insert_text((20,45),header,fontsize=10)
                temporary=Path(tmp)/'dated.pdf';document.save(temporary);document.close()
                result=m.native_collect(temporary,self.source())
                if expected:self.assertEqual(result[0]['validFrom'],expected)
                else:self.assertEqual(result,[])

    def test_explicit_kg_pack_price_and_wrong_pack_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'offer.pdf';self.create_pdf(path,price='10.99',kilogram=True)
            offer=m.native_collect(path,self.source('MÜLLER'))[0]
            self.assertEqual(offer['verificationMethod'],'pdf_1kg_price')
            self.assertNotIn('printedUnitPriceCents',offer['evidence'])
            c.validate_offer(offer)
            offer['quantityGrams']=500
            with self.assertRaises(ValueError):c.validate_offer(offer)

    def test_previous_app_feed_never_contains_new_markets_or_methods(self):
        data={'offers':[{'market':'Lidl','verificationMethod':'ocr_unitprice_crosscheck'},
                        {'market':'MÜLLER','verificationMethod':'pdf_1kg_price'},
                        {'market':'PENNY','verificationMethod':'pdf_1kg_price'},
                        {'market':'AEZ','verificationMethod':'pdf_text_crosscheck'}],
              'sources':[{'market':name} for name in c.MARKET_PDF_HOSTS]}
        old=legacy(data)
        self.assertEqual([o['market'] for o in old['offers']],['Lidl'])
        self.assertEqual({s['market'] for s in old['sources']},{'Lidl','PENNY'})

    def test_rewe_uses_official_public_viewer_without_retail_landing_page(self):
        payload = '<meta name="description" content="45. Woche 2026. Gültig ab 02.11.2026">' + '\n' + '\"downloadPdfUrl\": \"https://view.publitas.com/89773/example.pdf?filename=rewe_2026_wk45_461921.pdf\"'
        with patch.object(c, 'text', return_value=payload) as fetch:
            result=m.resolve('REWE',date(2026,11,5))
        fetch.assert_called_once_with('https://services.publitas.com/rewe/publications?week=45&wwident=461921&feature=download')
        self.assertEqual(result.start,date(2026,11,2))
        self.assertEqual(result.end,date(2026,11,7))
        with patch.object(c, 'text', return_value=payload.replace('461921','999999')):
            with self.assertRaises(ValueError):m.resolve('REWE',date(2026,11,5))

    def test_permanent_edeka_entry_is_not_a_fixed_week_link(self):
        xml='<from>2026-11-08</from><to>2026-11-14</to>'
        with patch.object(c,'text',return_value=xml):
            source=m.resolve('EDEKA',date(2026,11,10))
        self.assertEqual(source.end,date(2026,11,14))
        self.assertTrue(source.pdf_url.endswith('/blaetterkatalog/pdf/complete.pdf'))


if __name__=='__main__':unittest.main()
