import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import collect as c
from publish import semantic

SOURCE = c.Source('PENNY', 'Eichenau',
                  'https://penny-publish.blaetterkatalog.de/complete.pdf',
                  'https://penny-publish.blaetterkatalog.de/viewer',
                  date(2026, 11, 2), date(2026, 11, 7))
CAPTION = 'MELITTA\nKaffeepads Barista Crema, je 107 g (1 kg = 18.60)'
PRICE = c.Word('1.99', 100, 100, 130, 130, 30)


class ExtractionTests(unittest.TestCase):
    def test_unit_price_rounding(self):
        self.assertEqual(c.checked_price(CAPTION, [PRICE]), (199, 107, 1860))
        self.assertEqual(c.checked_price('BARILLA\nPasta Je500g 1kg=1.98',
                         [c.Word('099*', 1, 1, 20, 40, 39, 95)]), (99, 500, 198))

    def test_wrong_or_ambiguous_price_omitted(self):
        self.assertIsNone(c.checked_price(CAPTION, [c.Word('2.99', 1, 1, 20, 40, 39)]))
        self.assertIsNone(c.checked_price(CAPTION + ' je 112 g (1 kg = 17.77)', [PRICE]))
        self.assertIsNone(c.checked_price(CAPTION, [c.Word('1.99', 1, 1, 20, 40, 39, 60)]))

    def test_thursday_dates_not_monday(self):
        self.assertEqual(c.page_dates('Do 5.11. bis Sa 7.11.', SOURCE),
                         (date(2026, 11, 5), date(2026, 11, 7)))
        self.assertIsNone(c.page_dates('Mo 5.11. bis Sa 7.11.', SOURCE))
        self.assertIsNone(c.page_dates('Mo 9.11. bis Sa 14.11.', SOURCE))
        self.assertIsNone(c.page_dates('Top Angebote', SOURCE))

    def test_calendar_year_change(self):
        source = c.Source('Lidl', '', '', '', date(2026, 12, 28), date(2027, 1, 2))
        self.assertEqual(c.page_dates('Mo 28.12. bis Sa 2.1.', source),
                         (date(2026, 12, 28), date(2027, 1, 2)))

    def test_not_related_food(self):
        for item in ['Butterkekse', 'Buttermilch', 'Pasta Sauce', 'Pasta-Soße', 'Kaffeemaschine', 'Tortellini Pasta', 'Pesto', 'Vegane Butter', 'Margarine Butter', 'Kaffee Cappuccino']:
            if item in {'Pasta Sauce','Pasta-Soße','Pesto'}:
                self.assertEqual(c.category_of(item),'pasta_sauce',item)
            else:
                self.assertIsNone(c.category_of(item), item)

    def test_app_condition_excluded(self):
        app = c.Word('PENNY App', 1, 1, 20, 10, 9)
        self.assertIsNone(c.offer_from(CAPTION, [PRICE, app], SOURCE,
                          (SOURCE.start, SOURCE.end), 50, 'a'*64, 'pdf_text_crosscheck'))

    def test_evidence_and_forms(self):
        offer = c.offer_from(CAPTION, [PRICE], SOURCE,
                             (date(2026, 11, 5), SOURCE.end), 50, 'a'*64, 'pdf_text_crosscheck')
        c.validate_offer(offer)
        self.assertEqual(offer['variants'], ['pads'])
        self.assertEqual(offer['validFrom'], '2026-11-05')
        wrong = copy.deepcopy(offer)
        wrong['priceCents'] = 299
        with self.assertRaises(ValueError):
            c.validate_offer(wrong)
        wrong = copy.deepcopy(offer)
        wrong['pdfUrl'] = 'http://localhost/secret.pdf'
        with self.assertRaises(ValueError):
            c.validate_offer(wrong)

    def test_unsafe_url_rejected_before_request(self):
        with patch.object(c, 'urlopen') as request:
            for url in ['http://www.penny.de/a', 'https://localhost/a', 'https://example.com/a']:
                with self.assertRaises(ValueError):
                    c.fetch(url)
            request.assert_not_called()

    def test_dynamic_penny_week_and_store(self):
        market = {'wwIdent': '562302', 'city': 'Eichenau',
                  'flippingBookURL': 'https://penny-publish.blaetterkatalog.de/viewer'}
        viewer = '''<meta http-equiv="expires" content="Sat, 14 Nov 2026 23:59:59 CET">
        PENNY-HZ-KW46-15A saveCompleteUrl: '/complete.pdf' '''
        with patch.object(c, 'text', side_effect=[json.dumps(market), viewer]):
            source = c.penny_source(date(2026, 11, 10))
        self.assertEqual(source.start, date(2026, 11, 9))
        self.assertEqual(source.end, date(2026, 11, 14))
        self.assertEqual(source.pdf_url, 'https://penny-publish.blaetterkatalog.de/complete.pdf')

    def test_partial_failure_retains_only_unexpired_without_extending(self):
        previous = {'offers': [{'id': 'old', 'title': 'Old', 'market': 'Lidl', 'validFrom': '2026-11-02', 'validTo': '2026-11-07'},
                               {'id': 'expired', 'title': 'Expired', 'market': 'Lidl', 'validFrom': '2026-10-26', 'validTo': '2026-10-31'}]}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(c, 'penny_source', return_value=SOURCE), \
             patch.object(c, 'lidl_source', side_effect=ValueError('changed source')), \
             patch.object(c, 'fetch', return_value=b'%PDF-test'), \
             patch.object(c, 'collect_penny', return_value=[]):
            result = c.collect(date(2026, 11, 5), Path(tmp), previous, include_all=False)
        self.assertEqual(result['offers'], [previous['offers'][0]])
        self.assertEqual(result['offers'][0]['validTo'], '2026-11-07')
        self.assertEqual(result['sources'][1]['state'], 'failed')

    def test_total_failure_never_publishes_empty_catalog(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(c, 'penny_source', side_effect=ValueError('source down')), \
             patch.object(c, 'lidl_source', side_effect=ValueError('source down')):
            with self.assertRaises(RuntimeError):
                c.collect(date(2026, 11, 5), Path(tmp), include_all=False)

    def test_timestamp_alone_does_not_cause_commit(self):
        self.assertEqual(semantic({'offers': [], 'generatedAt': 'one', 'reviewedOn': 'one'}),
                         semantic({'offers': [], 'generatedAt': 'two', 'reviewedOn': 'two'}))


if __name__ == '__main__':
    unittest.main()
