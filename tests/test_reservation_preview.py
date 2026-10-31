import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import prepared_media
from reservation_preview import future_slots, plan


class ReservationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest = Path(self.tmp.name) / 'cards.json'
        self.patch = patch.object(prepared_media, 'MANIFEST', self.manifest)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
        self.card = {'source_url': 'https://stvv.jp/news/team/20261026_2/',
                     'date_jst': '2026-10-26',
                     'text': '公式発表を確認。https://stvv.jp/news/team/20261026_2/',
                     'slots': ['player', 'news'], 'reviewed': True, 'status': 'ready',
                     'asset_path': 'generated/example.jpg', 'sha256': 'a' * 64}
        self.write_card()

    def write_card(self):
        self.manifest.write_text(json.dumps({'enabled': True, 'cards': [self.card]}))

    def test_reduced_three_slots_and_utc_conversion(self):
        now = datetime.fromisoformat('2026-10-26T23:20:00+09:00')
        slots = future_slots(now)
        self.assertEqual(len(slots), 4)
        self.assertEqual([s for _, s in slots],
                         ['player', 'news', 'recap', 'player'])
        result = plan(self.history, now)
        self.assertEqual(result['proposals'][0]['due_utc'], '2026-10-26T23:00:00Z')
        self.assertEqual(result['proposals'][0]['due_jst'], '2026-10-27T08:00:00+09:00')
        self.assertFalse(result['can_publish'])

    def test_36_hour_horizon_includes_next_day_without_changing_slot_times(self):
        now = datetime.fromisoformat('2026-10-27T07:00:00+09:00')
        slots = future_slots(now)
        self.assertIn((datetime.fromisoformat('2026-10-28T18:00:00+09:00'), 'news'), slots)
        self.assertNotIn((datetime.fromisoformat('2026-10-28T21:00:00+09:00'), 'vote'), slots)
        self.assertTrue(all(due > now for due, _ in slots))
        with self.assertRaises(ValueError):
            future_slots(now, horizon_hours=37)

    def test_minimum_lead_and_invalid_time(self):
        slots = future_slots(datetime.fromisoformat('2026-10-27T07:31:00+09:00'))
        self.assertEqual(slots[0][1], 'news')
        with self.assertRaises(ValueError):
            future_slots(datetime(2026, 10, 27))
        with self.assertRaises(ValueError):
            future_slots(datetime.fromisoformat('2026-10-27T07:00:00+09:00'), lead_minutes=0)

    def test_occupied_and_pending_slots_are_not_proposed(self):
        self.history['pending_posts']['daily_2026-10-27_player'] = {}
        result = plan(self.history, datetime.fromisoformat('2026-10-27T00:00:00+09:00'))
        self.assertEqual(result['proposals'][0]['slot'], 'news')
        self.assertEqual(result['blocked'][0]['reason'], 'processed_or_pending')

    def test_pending_source_or_published_caption_cannot_repeat(self):
        for field, value in [('publication_log', [{'text': self.card['text'],
                                                   'source': self.card['source_url']}]),
                             ('pending_posts', {'old': {'text': self.card['text'],
                                                       'source': self.card['source_url']}})]:
            with self.subTest(field=field):
                history = copy.deepcopy(self.history)
                history[field] = value
                self.assertEqual(plan(history, datetime.fromisoformat(
                    '2026-10-27T00:00:00+09:00'))['proposals'], [])

    def test_freshness_is_checked_on_due_date(self):
        self.card['date_jst'] = '2026-10-19'
        self.write_card()
        result = plan(self.history, datetime.fromisoformat('2026-10-26T23:00:00+09:00'))
        self.assertEqual(result['proposals'], [])

    def test_a_future_article_is_not_approved_just_because_publication_is_tomorrow(self):
        self.card['date_jst'] = '2026-10-27'
        self.write_card()
        result = plan(self.history, datetime.fromisoformat('2026-10-26T23:00:00+09:00'))
        self.assertEqual(result['proposals'], [])
        self.assertEqual(result['blocked'][0]['reason'], 'future_article_date')

    def test_no_network_no_state_mutation_max_one(self):
        before = copy.deepcopy(self.history)
        original = self.manifest.read_bytes()
        with patch('requests.sessions.Session.request', side_effect=AssertionError('network')):
            result = plan(self.history, datetime.fromisoformat('2026-10-26T00:00:00+09:00'))
        self.assertEqual(len(result['proposals']), 1)
        self.assertEqual(self.history, before)
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertFalse(result['live_transport_changed'])

    def test_invalid_history_does_not_assume_empty(self):
        with self.assertRaises(ValueError):
            plan({}, datetime.fromisoformat('2026-10-26T00:00:00+09:00'))

    def test_unsupported_fact_cannot_bypass_duplicate_policy(self):
        self.card['editorial_fact'] = {'kind': 'arbitrary_new_angle'}
        self.write_card()
        self.assertEqual(plan(self.history, datetime.fromisoformat(
            '2026-10-26T00:00:00+09:00'))['proposals'], [])


if __name__ == '__main__':
    unittest.main()
