"""Verify real-send evidence boundaries without network or Buffer access."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
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

    def test_schedule_lag_label_does_not_blame_runner_without_job_metadata(self):
        # The nominal slot-to-delivery delay cannot identify which GitHub
        # scheduling stage was slow. Run/job creation timestamps are separate.
        self.assertEqual(d.schedule_delay_diagnostic(-1), 'clock_or_schedule_mismatch')
        self.assertEqual(d.schedule_delay_diagnostic(899), 'within_15_minutes')
        self.assertEqual(d.schedule_delay_diagnostic(900),
                         'schedule_to_delivery_delay_unattributed')
        self.assertEqual(d.schedule_delay_diagnostic(3599),
                         'schedule_to_delivery_delay_unattributed')
        self.assertEqual(d.schedule_delay_diagnostic(3600),
                         'severe_schedule_to_delivery_delay_unattributed')
        self.assertEqual(d.schedule_delay_diagnostic(14857),
                         'severe_schedule_to_delivery_delay_unattributed')

    def test_six_hour_late_guard_records_failure_without_buffer_or_false_pending_claim(self):
        # The 18:00 JST cron was actually started at 00:43 the next day.
        # A prior production run failed before creating any delivery evidence.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '40904274559',
                   'GITHUB_SCHEDULE': '0 9 * * *', 'GITHUB_EVENT_NAME': 'schedule',
                   'STVV_ADVANCE_RESERVATIONS': 'true'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d, 'datetime', wraps=datetime) as clock, \
                    patch.object(d.publisher, 'slot_for_run',
                                 side_effect=RuntimeError('実行が6時間以上遅れたため安全停止')), \
                    patch('advance_reservations.main') as reserve, \
                    patch.object(d.publisher, 'main') as legacy:
                clock.now.return_value = datetime.fromisoformat('2026-10-30T00:43:04+09:00')
                with self.assertRaisesRegex(RuntimeError, '6時間以上'):
                    d.main()
                reserve.assert_not_called()
                legacy.assert_not_called()
            report = json.loads((root / 'reports/delivery-runs/40904274559.json').read_text())
            self.assertEqual(report['status'], 'blocked_schedule_more_than_six_hours_late')
            self.assertEqual(report['scheduled_at'], '2026-10-29T18:00:00+09:00')
            self.assertEqual(report['start_delay_seconds'], 24184)
            self.assertEqual(report['schedule_delay_diagnostic'],
                             'severe_schedule_to_delivery_delay_unattributed')
            self.assertEqual(report['delivery_state'], 'no_buffer_mutation_due_to_schedule_guard')
            self.assertEqual(report['pending_state'], 'not_checked')
            self.assertFalse(report['x_display_verified'])
            self.assertEqual(report['new_reservations'], [])
            self.assertEqual(json.loads((root / 'reports/delivery-latest.json').read_text()),
                             report)

    def test_late_guard_reports_local_reservations_without_network_or_send(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'posted.json').write_text(json.dumps({
                'reserved_posts': {
                    'daily_2026-10-30_news': {'buffer_status': 'scheduled'},
                    'daily_2026-10-30_vote': {'buffer_status': 'draft'},
                },
                'pending_posts': {'daily_2026-10-30_player': {'send_state': 'unknown'}},
            }))
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '123456',
                   'GITHUB_SCHEDULE': '0 9 * * *', 'GITHUB_EVENT_NAME': 'schedule',
                   'STVV_ADVANCE_RESERVATIONS': 'true'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d, 'datetime', wraps=datetime) as clock, \
                    patch.object(d.publisher, 'slot_for_run',
                                 side_effect=RuntimeError('実行が6時間以上遅れたため安全停止')), \
                    patch('advance_reservations.main') as reserve:
                clock.now.return_value = datetime.fromisoformat('2026-10-30T00:43:04+09:00')
                with self.assertRaises(RuntimeError):
                    d.main()
                reserve.assert_not_called()
            report = json.loads((root / 'reports/delivery-runs/123456.json').read_text())
            self.assertEqual(report['reservation_coverage']['reserved_count'], 2)
            self.assertEqual(report['reservation_coverage']['pending_count'], 1)
            self.assertEqual(report['reservation_coverage']['scheduled_keys'],
                             ['daily_2026-10-30_news'])
            self.assertEqual(report['delivery_state'], 'no_buffer_mutation_due_to_schedule_guard')
            self.assertFalse(report['x_display_verified'])

    def test_late_guard_read_only_probe_of_overdue_reservation(self):
        now = datetime.fromisoformat('2026-10-30T19:30:00+09:00')
        record = {'buffer_id': 'test-buffer-id', 'buffer_status': 'scheduled',
                  'due_at': '2026-10-30T09:00:00Z', 'text': 'reviewed caption'}
        future = {'buffer_id': 'future-buffer-id', 'buffer_status': 'scheduled',
                  'due_at': '2026-10-31T09:00:00Z', 'text': 'future caption'}
        ledger = {'reserved_posts': {'due': record, 'future': future}}
        original = json.dumps(ledger, sort_keys=True)
        remote = {'id': 'test-buffer-id', 'status': 'sent',
                  'text': 'reviewed caption', 'channelId': d.publisher.CHANNEL}
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'dummy'}), \
                patch('buffer_reservations.BufferReservations') as client, \
                patch('advance_reservations.verify_echo') as verify:
            client.return_value.get_post.return_value = remote
            result = d.probe_overdue_reservations(ledger, now)
            client.return_value.get_post.assert_called_once_with('test-buffer-id')
            verify.assert_called_once_with(remote, record)
        self.assertEqual(result['status'], 'read_only_completed')
        self.assertEqual(result['overdue_count'], 1)
        self.assertEqual(result['results'][0]['remote_status'], 'sent')
        self.assertFalse(result['results'][0]['x_display_verified'])
        self.assertFalse(result['results'][0]['ledger_updated'])
        self.assertEqual(json.dumps(ledger, sort_keys=True), original)

    def test_late_reserved_slot_confirmed_sent_is_non_error_without_reposting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = 'daily_2026-11-01_news'
            ledger = {'reserved_posts': {key: {
                'buffer_id': 'original-reservation', 'buffer_status': 'scheduled',
                'due_at': '2026-11-01T09:00:00Z', 'text': 'approved text'}},
                'pending_posts': {}}
            (root / 'posted.json').write_text(json.dumps(ledger))
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '41321793518',
                   'GITHUB_SCHEDULE': '0 9 * * *', 'GITHUB_EVENT_NAME': 'schedule',
                   'STVV_ADVANCE_RESERVATIONS': 'true'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d, 'datetime', wraps=datetime) as clock, \
                    patch.object(d.publisher, 'slot_for_run',
                                 side_effect=RuntimeError('実行が6時間以上遅れたため安全停止')), \
                    patch.object(d, 'probe_overdue_reservations', return_value={
                        'status': 'read_only_completed', 'results': [
                            {'key': key, 'remote_status': 'sent',
                             'x_display_verified': False, 'ledger_updated': False}]}), \
                    patch('advance_reservations.main') as reserve:
                clock.now.return_value = datetime.fromisoformat('2026-11-02T00:33:17+09:00')
                self.assertEqual(d.main(),
                                 'late_existing_reservation_buffer_sent_x_unverified')
                reserve.assert_not_called()
            report = json.loads((root / 'reports/delivery-latest.json').read_text())
            self.assertEqual(report['delivery_state'],
                             'buffer_reports_sent_x_unverified_no_new_send')
            self.assertFalse(report['x_display_verified'])
            self.assertEqual(report['new_publications'], [])
            self.assertEqual(json.loads((root / 'posted.json').read_text()), ledger)

    def test_late_other_reservation_sent_does_not_hide_missing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'posted.json').write_text(json.dumps({
                'reserved_posts': {'daily_2026-10-31_news': {
                    'buffer_status': 'scheduled'}}, 'pending_posts': {}}))
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '41321793519',
                   'GITHUB_SCHEDULE': '0 9 * * *', 'GITHUB_EVENT_NAME': 'schedule',
                   'STVV_ADVANCE_RESERVATIONS': 'true'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d, 'datetime', wraps=datetime) as clock, \
                    patch.object(d.publisher, 'slot_for_run',
                                 side_effect=RuntimeError('実行が6時間以上遅れたため安全停止')), \
                    patch.object(d, 'probe_overdue_reservations', return_value={
                        'status': 'read_only_completed', 'results': [
                            {'key': 'daily_2026-10-31_news', 'remote_status': 'sent'}]}):
                clock.now.return_value = datetime.fromisoformat('2026-11-02T00:33:17+09:00')
                with self.assertRaises(RuntimeError):
                    d.main()
            report = json.loads((root / 'reports/delivery-latest.json').read_text())
            self.assertEqual(report['status'], 'blocked_schedule_more_than_six_hours_late')

    def test_late_guard_probe_missing_auth_and_identity_mismatch_are_not_success(self):
        now = datetime.fromisoformat('2026-10-30T19:30:00+09:00')
        ledger = {'reserved_posts': {'due': {
            'buffer_id': 'test-buffer-id', 'buffer_status': 'scheduled',
            'due_at': '2026-10-30T09:00:00Z', 'text': 'approved caption'}}}
        with patch.dict(os.environ, {'BUFFER_API_KEY': ''}):
            result = d.probe_overdue_reservations(ledger, now)
        self.assertEqual(result['status'], 'read_only_probe_not_configured')
        self.assertEqual(result['results'], [])
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'dummy'}), \
                patch('buffer_reservations.BufferReservations') as client:
            client.return_value.get_post.return_value = {
                'id': 'test-buffer-id', 'status': 'draft',
                'channelId': d.publisher.CHANNEL, 'text': 'wrong caption'}
            result = d.probe_overdue_reservations(ledger, now)
        self.assertEqual(result['results'][0]['remote_status'], 'unverified')
        self.assertEqual(result['results'][0]['error_type'], 'RuntimeError')
        self.assertEqual(ledger['reserved_posts']['due']['buffer_status'], 'scheduled')

    def test_late_guard_probe_client_initialization_failure_keeps_evidence(self):
        now = datetime.fromisoformat('2026-10-30T19:30:00+09:00')
        ledger = {'reserved_posts': {'due': {
            'buffer_id': 'test-buffer-id', 'buffer_status': 'scheduled',
            'due_at': '2026-10-30T09:00:00Z', 'text': 'approved caption'}}}
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'dummy'}), \
                patch('buffer_reservations.BufferReservations',
                      side_effect=RuntimeError('private provider payload')):
            result = d.probe_overdue_reservations(ledger, now)
        self.assertEqual(result['status'], 'read_only_probe_unavailable')
        self.assertEqual(result['overdue_count'], 1)
        self.assertEqual(result['checked_count'], 0)
        self.assertEqual(result['error_type'], 'RuntimeError')
        self.assertNotIn('private provider payload', json.dumps(result))
        self.assertEqual(ledger['reserved_posts']['due']['buffer_status'], 'scheduled')

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

    def test_advance_wrapper_tracks_future_reservation_and_never_calls_share_now(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / 'posted.json'
            ledger.write_text(json.dumps(history()))
            def reserve():
                changed = history()
                changed['reserved_posts'] = {'daily_2026-10-28_player': {
                    'buffer_id': 'offline-fixture', 'buffer_status': 'scheduled',
                    'due_at': '2026-10-27T23:00:00Z'}}
                ledger.write_text(json.dumps(changed))
                return 'reserved_in_buffer'
            env = {'STVV_DELIVERY_RECORD': 'true', 'GITHUB_RUN_ID': '789',
                   'GITHUB_SCHEDULE': '0 12 * * *', 'GITHUB_EVENT_NAME': 'schedule',
                   'STVV_ADVANCE_RESERVATIONS': 'true'}
            with patch.dict(os.environ, env, clear=True), patch.object(d, 'ROOT', root), \
                    patch.object(d.publisher, 'slot_for_run', return_value=('vote', '2026-10-27')), \
                    patch.object(d, 'queue_snapshot', return_value={}), \
                    patch.object(d.publisher, 'main') as legacy, \
                    patch('advance_reservations.main', side_effect=reserve) as advance:
                d.main()
                legacy.assert_not_called()
                advance.assert_called_once()
            result = json.loads((root / 'reports/delivery-latest.json').read_text())
            self.assertEqual(result['delivery_mode'], 'advance_reservations')
            self.assertEqual(result['delivery_state'], 'buffer_scheduled_not_published')
            self.assertEqual(result['new_reservations'][0]['key'], 'daily_2026-10-28_player')
            self.assertEqual(result['new_publications'], [])

    def test_draft_is_not_scheduled_and_never_attributes_actor(self):
        # Old ledgers used an actor-attributing label. Keep them readable,
        # but never infer a human action from Buffer's draft status.
        for status in ('draft_no_longer_scheduled', 'cancelled_by_user'):
            with self.subTest(status=status):
                before = history()
                after = history()
                after['reserved_posts'] = {'daily_2026-10-29_news': {
                    'buffer_id': 'buffer-fixture', 'buffer_status': status,
                    'due_at': '2026-10-29T09:00:00Z'}}
                result = d.delivery_evidence(before, after, '2026-10-29', 'news', advance=True)
                self.assertEqual(result['delivery_state'], 'buffer_draft_not_scheduled_x_unverified')
                self.assertEqual(result['reservation_states'][0]['buffer_status'], status)
                self.assertFalse(result['x_display_verified'])
                self.assertEqual(result['new_publications'], [])

    def test_mixed_sent_and_cancelled_reservations_are_not_all_drafts(self):
        # The cancelled G-football reservation must not obscure a separately
        # Buffer-sent OH Leuven announcement. This run made no new send.
        for terminal in ('cancelled_by_user', 'draft_no_longer_scheduled'):
            with self.subTest(terminal=terminal):
                before = history()
                after = history()
                after['reserved_posts'] = {
                    'daily_2026-10-29_news': {
                        'buffer_id': 'cancelled-id', 'buffer_status': terminal,
                        'due_at': '2026-10-29T09:00:00Z'},
                    'daily_2026-10-30_news': {
                        'buffer_id': 'sent-id', 'buffer_status': 'sent',
                        'due_at': '2026-10-30T09:00:00Z'}}
                result = d.delivery_evidence(
                    before, after, '2026-10-30', 'recap', advance=True)
                self.assertEqual(
                    result['delivery_state'],
                    'historical_sent_and_cancelled_no_new_acceptance')
                self.assertEqual(result['new_publications'], [])
                self.assertFalse(result['x_display_verified'])
                self.assertEqual(len(result['reservation_states']), 2)

    def test_unknown_buffer_status_does_not_claim_scheduled(self):
        before = history()
        after = history()
        after['reserved_posts'] = {'daily_2026-10-29_news': {
            'buffer_id': 'buffer-fixture', 'buffer_status': 'unknown',
            'due_at': '2026-10-29T09:00:00Z'}}
        result = d.delivery_evidence(before, after, '2026-10-29', 'news', advance=True)
        self.assertEqual(result['delivery_state'], 'buffer_reservation_state_unverified_do_not_retry')
        self.assertFalse(result['x_display_verified'])

    def test_unreadable_history_is_not_zero_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'posted.json'
            path.write_text('broken')
            with self.assertRaises(ValueError):
                d.read_ledger(path)
