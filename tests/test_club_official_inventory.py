import unittest
from datetime import datetime
from unittest.mock import Mock

import club_official_inventory as source
from stvv_post import JST

NOW = datetime(2026, 10, 28, 14, tzinfo=JST)
URL = 'https://stvv.com/nl/nieuws/artikel/de-week-van-de-waarheid'
INDEX = f'<a href="/nl/nieuws/artikel/de-week-van-de-waarheid">De week van de waarheid</a>'
BODY = ('<main><h1>De week van de waarheid</h1><div>27 oktober 2026</div><p>'
        + 'Drie thuiswedstrijden en Japan Day. ' * 12
        + 'Zondag 1 november, 16u00.</p></main>')


def session(page=BODY):
    obj = Mock()
    obj.get.side_effect = [Mock(url=source.LISTING, text=INDEX),
                           Mock(url=URL, text=page)]
    return obj


class BelgianOfficialTests(unittest.TestCase):
    def test_read_only_candidate_and_kickoff_conflict_flag(self):
        result = source.build_inventory({}, {'cards': []}, NOW, session())
        self.assertEqual(result['status'], 'candidates_need_review')
        candidate = result['candidates'][0]
        self.assertEqual(candidate['status'], 'needs_editorial_review')
        self.assertTrue(candidate['kickoff_time_requires_cross_source_check'])
        self.assertFalse(candidate['can_publish'])
        self.assertFalse(result['publication_performed'])
        self.assertEqual(len(candidate['body_sha256']), 64)

    def test_redirected_listing_or_article_never_approved(self):
        bad = session()
        bad.get.side_effect = [Mock(url='https://example.com', text=INDEX)]
        self.assertEqual(source.build_inventory({}, {}, NOW, bad)['status'], 'source_scan_failed')
        bad = session()
        bad.get.side_effect = [Mock(url=source.LISTING, text=INDEX),
                               Mock(url='https://evil.test/', text=BODY)]
        self.assertEqual(source.build_inventory({}, {}, NOW, bad)['candidates'][0]['status'], 'source_unavailable')

    def test_deduplicates_reserved_sources_without_article_request(self):
        history = {'reserved_posts': {'a': {'source': URL}}}
        client = session()
        result = source.build_inventory(history, {}, NOW, client)
        self.assertEqual(result['candidates'], [])
        self.assertEqual(client.get.call_count, 1)

    def test_old_articles_are_not_new(self):
        result = source.build_inventory({}, {}, NOW, session(BODY.replace('27 oktober', '10 oktober')))
        self.assertEqual(result['status'], 'no_new_club_articles')

    def test_no_article_body_fails_closed(self):
        result = source.build_inventory({}, {}, NOW, session('<h1>De week van de waarheid</h1>'))
        self.assertEqual(result['candidates'][0]['status'], 'source_unavailable')

    def test_filters_promotions_external_links_and_query_strings(self):
        html = (INDEX
                + '<a href="https://evil.test/nl/nieuws/artikel/bad">bad</a>'
                + '<a href="/nl/nieuws/artikel/ticketinfo-conference-league">Ticketinfo Conference League</a>'
                + '<a href="/nl/nieuws/artikel/de-week-van-de-waarheid?x=1">dup</a>')
        self.assertEqual(source.listing_links(html), [(URL, 'De week van de waarheid')])


if __name__ == '__main__':
    unittest.main()
