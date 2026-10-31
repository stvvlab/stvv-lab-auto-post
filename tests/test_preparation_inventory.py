import copy
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import requests
import preparation_inventory as inventory
import stvv_post as posting

NOW = datetime(2026, 10, 25, 19, tzinfo=posting.JST)
URL = 'https://stvv.jp/news/team/20261025_1/'
TITLE = '日本人選手の新しい試合出場について'
LINK = f'<a href="{URL}"><h3>{TITLE}</h3></a>'


class InventoryTests(unittest.TestCase):
    def test_uefa_list_survives_general_list_failure_and_deduplicates(self):
        session = Mock()
        session.get.side_effect = [requests.Timeout('timeout'), Mock(text=LINK), Mock(text=LINK), Mock(text=LINK), Mock(text=LINK)]
        found, checks = posting.scan_articles(NOW, session)
        self.assertEqual(len(found), 1)
        self.assertEqual([c['status'] for c in checks], ['error', 'ok', 'ok', 'ok'])
        self.assertIn('/team/2026/', session.get.call_args_list[2].args[0])
        self.assertIn('/uefa-news/2026/', session.get.call_args_list[-2].args[0])
        self.assertIn('/event/2026/', session.get.call_args_list[-1].args[0])

    def test_team_only_update_is_discovered_without_relying_on_general_list(self):
        session = Mock()
        stale = '<a href="/news/game/20261001_1/"><h3>選手の試合出場について</h3></a>'
        session.get.side_effect = [Mock(text=stale), Mock(text=stale),
                                   Mock(text=LINK), Mock(text=stale), Mock(text=stale)]
        found, checks = posting.scan_articles(NOW, session)
        self.assertEqual(found, [(URL, (NOW.date(), TITLE))])
        self.assertEqual(len(checks), 5)
        self.assertEqual(checks[2]['url'], 'https://stvv.jp/news/team/2026/')
        self.assertEqual(checks[2]['eligible_items'], 1)

    def test_empty_challenge_page_and_external_redirect_are_errors(self):
        session = Mock()
        session.get.side_effect = [Mock(text='verification required'),
                                  Mock(text=LINK, url='https://example.com/'),
                                  requests.Timeout(), requests.Timeout(), requests.Timeout()]
        found, checks = posting.scan_articles(NOW, session)
        self.assertEqual(found, [])
        self.assertTrue(all(c['status'] == 'error' for c in checks))

    def test_new_official_watch_party_is_discovered_despite_prize_draw_excerpt(self):
        now = datetime(2026, 10, 31, 17, tzinfo=posting.JST)
        html = (
            '<a href="/news/event/20261030_2/">'
            '<h3>11月29日ゲンク戦の観戦会開催が決定</h3>'
            '<p>サイン入りグッズが当たる抽選会を実施</p></a>'
            '<a href="/news/event/20261030_3/">'
            '<h3>11月29日ゲンク戦の観戦会グッズ販売</h3></a>'
            '<a href="/news/event/20261030_4/">'
            '<h3>スポンサーキャンペーンの抽選開催</h3></a>'
            '<a href="/news/event/20261001_1/">'
            '<h3>9月のゲンク戦観戦会開催</h3></a>'
        )
        parsed = posting.parse_articles(html, now)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0][0], 'https://stvv.jp/news/event/20261030_2/')
        self.assertIn('観戦会', parsed[0][1][1])

    def build(self, history=None, manifest=None, checks=None, body='公式本文。' * 40):
        history = history or {'news': [], 'publication_log': [], 'pending_posts': {}}
        original = copy.deepcopy(history)
        session = Mock()
        session.get.return_value = Mock(url=URL, text=f'<div class="article_content">{body}</div>')
        with patch.object(inventory, 'scan_articles', return_value=(
                [(URL, (NOW.date(), TITLE))], checks or [{'status': 'ok'}])):
            result = inventory.build_inventory(history, manifest or {'cards': []}, NOW, session)
        self.assertEqual(history, original)
        return result, session

    def test_candidate_contains_body_evidence_never_ready_or_caption(self):
        result, _ = self.build()
        item = result['candidates'][0]
        self.assertEqual(item['status'], 'needs_editorial_review')
        self.assertFalse(item['reviewed'])
        self.assertEqual(len(item['body_sha256']), 64)
        self.assertNotIn('text', item)
        self.assertNotIn('asset_path', item)
        self.assertFalse(result['publication_performed'])
        self.assertFalse(result['image_generation_performed'])

    def test_published_pending_and_registered_sources_never_fetch_body(self):
        for history, manifest in [
            ({'news': [URL]}, {}),
            ({'publication_log': [{'source': URL + '?utm_source=x'}]}, {}),
            ({'pending_posts': {'p': {'source': URL}}}, {}),
            ({}, {'cards': [{'source_url': URL, 'status': 'ready'}]})]:
            result, session = self.build(history, manifest)
            self.assertEqual(result['candidates'], [])
            session.get.assert_not_called()

    def test_missing_body_is_unavailable_not_a_reviewed_candidate(self):
        result, _ = self.build(body='短い本文')
        self.assertEqual(result['candidates'][0]['status'], 'source_unavailable')

    def test_failed_and_partial_scans_are_not_no_news(self):
        for checks, expected in [([{'status': 'error'}], 'source_scan_failed'),
                                  ([{'status': 'error'}, {'status': 'ok'}], 'no_candidate_partial_scan')]:
            result, _ = self.build(history={'news': [URL]}, checks=checks)
            self.assertEqual(result['status'], expected)

    def test_article_external_redirect_is_rejected(self):
        session = Mock()
        session.get.return_value = Mock(url='https://example.com/', text='<div class="article_content">' + '長い本文' * 40 + '</div>')
        with self.assertRaises(ValueError):
            inventory.read_body(session, URL)


if __name__ == '__main__':
    unittest.main()
