"""Verify real-send evidence boundaries without network or Buffer access."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_run as d


def history():
    return {'publication_log': [], 'pending_posts': {}}


class DeliveryRunTests(unittest.TestCase):
    def test_buffer_acceptance_is_not_x_display(self):
        before = history()
        after = history()
        after['publication_log'] = [{'key': 'daily_2026-10-26_vote',
                                    'buffer_id': 'mock', 'buffer_status': 'sent'}]
        result = d.delivery_evidence(before, after, '2026-10-26', 'vote')
        self.assertEqual(result['delivery_state'], 'buffer_reports_sent_x_unverified')
        self.assertFalse(result['x_display_verified'])
        self.assertEqual(len(result['new_publications']), 1)

    def test_existing_acceptance_is_not_new_publication(self):
        before = history()
        before['publication_log'] = [{'key': 'daily_2026-10-26_vote'}]
        self.assertEqual(d.delivery_evidence(before, before, '2026-10-26', 'vote')
                         ['new_publications'], [])

    def test_ci_and_manual_calls_cannot_create_evidence(self):
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123',
                                    'GITHUB_EVENT_NAME': 'pull_request'}, clear=True), \
                patch.object(d.publisher, 'main') as publish:
            with self.assertRaises(RuntimeError):
                d.main()
            publish.assert_not_called()

    def test_unknown_send_persists_evidence_and_raises_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / 'posted.json'
            ledger.write_text(json.dumps(history()))

            def uncertain():
                changed = history()
                changed['pending_posts']['daily_2026-10-26_vote'] = {'text': 'test'}
                ledger.write_text(json.dumps(changed))
                raise TimeoutError('private payload must not enter evidence')

            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '123',
                   'GITHUB_SCHEDULE': '0 12 * * *',
                   'GITHUB_EVENT_NAME': 'schedule'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d.publisher, 'slot_for_run', return_value=('vote', '2026-10-26')), \
                    patch.object(d, 'queue_snapshot', return_value={}), \
                    patch.object(d.publisher, 'main', side_effect=uncertain) as publish:
                with self.assertRaises(TimeoutError):
                    d.main()
                publish.assert_called_once()
            result = json.loads((root / 'reports/delivery-runs/123.json').read_text())
            self.assertEqual(result['status'], 'execution_failed')
            self.assertEqual(result['delivery_state'], 'send_outcome_unknown_do_not_retry')
            self.assertEqual(result['error_type'], 'TimeoutError')
            self.assertNotIn('private payload', json.dumps(result))
            self.assertIn('daily_2026-10-26_vote', json.loads(ledger.read_text())['pending_posts'])

    def test_skip_and_queue_error_do_not_claim_send(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'posted.json').write_text(json.dumps(history()))
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '456',
                   'GITHUB_SCHEDULE': '0 12 * * *',
                   'GITHUB_EVENT_NAME': 'schedule'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d.publisher, 'slot_for_run', return_value=('vote', '2026-10-26')), \
                    patch.object(d, 'queue_snapshot', side_effect=ValueError()), \
                    patch.object(d.publisher, 'main', return_value='skipped_image_verification'):
                d.main()
            result = json.loads((root / 'reports/delivery-latest.json').read_text())
            self.assertEqual(result['status'], 'skipped_image_verification')
            self.assertEqual(result['delivery_state'], 'no_new_buffer_acceptance_recorded')
            self.assertEqual(result['queue_diagnosis_error'], 'ValueError')

    def test_unreadable_history_is_not_zero_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'posted.json'
            path.write_text('broken')
            with self.assertRaises(ValueError):
                d.read_ledger(path)
