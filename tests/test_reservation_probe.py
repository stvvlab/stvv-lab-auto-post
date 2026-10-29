"""Read-only probe must expose stale reservation state without reposting."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import buffer_reservations as module
import stvv_post as publisher


class ReservationProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        previous = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, previous)
        self.history = {
            'publication_log': [{
                'buffer_id': 'published-id', 'text': 'Earlier verified publication'
            }],
            'reserved_posts': {
                'daily_2026-10-29_news': {
                    'buffer_id': 'scheduled-id', 'text': 'Cancelled story',
                    'due_at': '2026-10-29T09:00:00Z',
                    'buffer_status': 'scheduled'
                }
            }
        }
        self.client = Mock()
        self.client.preflight.return_value = {
            'channel_id': publisher.CHANNEL,
            'scheduled_limit': 10, 'active_count': 0,
            'remaining_capacity': 10, 'posts': []
        }
        self.client.get_post.side_effect = [
            {'id': 'published-id', 'text': 'Earlier verified publication',
             'channelId': publisher.CHANNEL, 'status': 'sent'},
            {'id': 'scheduled-id', 'text': 'Cancelled story',
             'channelId': publisher.CHANNEL, 'status': 'draft',
             'dueAt': None, 'assets': []}
        ]
        p1 = patch.object(module, 'BufferReservations', return_value=self.client)
        p2 = patch.object(publisher, 'load', return_value=self.history)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

    def test_probe_reports_draft_and_preserves_ledger(self):
        before = json.dumps(self.history, sort_keys=True)
        module.probe()
        report = json.loads(Path('reports/reservation-capability.json').read_text())
        self.assertEqual(report['status'], 'read_permission_capacity_and_status_query_verified')
        self.assertEqual(report['active_count'], 0)
        self.assertEqual(report['observed_reservation_states'], [{
            'key': 'daily_2026-10-29_news', 'buffer_id': 'scheduled-id',
            'ledger_status': 'scheduled', 'remote_status': 'draft',
            'ledger_updated': False, 'x_display_verified': False
        }])
        self.assertEqual(json.dumps(self.history, sort_keys=True), before)
        self.client.schedule.assert_not_called()

    def test_changed_remote_draft_identity_fails_closed(self):
        self.client.get_post.side_effect = [
            {'id': 'published-id', 'text': 'Earlier verified publication',
             'channelId': publisher.CHANNEL, 'status': 'sent'},
            {'id': 'scheduled-id', 'text': 'Different story',
             'channelId': publisher.CHANNEL, 'status': 'draft'}
        ]
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            module.probe()
        report = json.loads(Path('reports/reservation-capability.json').read_text())
        self.assertEqual(report['error_type'], 'RuntimeError')
        self.client.schedule.assert_not_called()


if __name__ == '__main__':
    unittest.main()
