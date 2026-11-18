"""Regression: time-locked fixture is not eligible until approved asset is ready."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import prepared_media
from reservation_preview import future_slots, plan


class CharleroiReservationWindowTests(unittest.TestCase):
    def test_pending_fixture_never_proposed_and_window_is_bounded(self):
        now = datetime.fromisoformat('2026-11-18T16:22:00+09:00')
        due = datetime.fromisoformat('2026-11-20T18:00:00+09:00')
        self.assertNotIn((due, 'news'), future_slots(now))
        self.assertIn((due, 'news'), future_slots(
            datetime.fromisoformat('2026-11-19T07:00:00+09:00')))
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'cards.json'
            card = {
                'source_url': 'https://stvv.jp/game/2026-2027/',
                'date_jst': '2026-11-18',
                'text': 'STVV next fixture https://stvv.jp/game/2026-2027/',
                'slots': ['news'], 'reviewed': True,
                'status': 'asset_pending',
                'asset_path': 'generated/approved_charleroi_20261120.png',
                'sha256': 'd2416e0c5bba352b9c0558551447cffec1553b41c7fc26ff7465f2c115662b9b',
                'publish_due_jst': due.isoformat(),
                'editorial_purpose': {
                    'kind': 'fixture', 'phase': 'initial',
                    'event_id': 'stvv-charleroi-2026-11-22'},
            }
            manifest.write_text(json.dumps({'enabled': True, 'cards': [card]}))
            history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
            with patch.object(prepared_media, 'MANIFEST', manifest):
                report = plan(history, datetime.fromisoformat(
                    '2026-11-19T07:00:00+09:00'))
                self.assertEqual(report['proposals'], [])
                self.assertEqual(report['content_readiness']['future_slots_with_candidate'], 0)
                self.assertFalse(report['can_publish'])
                card['status'] = 'ready'
                manifest.write_text(json.dumps({'enabled': True, 'cards': [card]}))
                self.assertEqual(len(prepared_media.prepared_candidates('news', due)), 1)
                self.assertEqual(len(prepared_media.prepared_candidates(
                    'news', due.replace(hour=23))), 0)


if __name__ == '__main__':
    unittest.main()
