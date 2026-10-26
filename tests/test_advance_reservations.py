"""Offline failure injection around the one-mutation reservation boundary."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import advance_reservations as a
import prepared_media as media
import stvv_post as publisher
from delivery_run import delivery_evidence
from buffer_reservations import BufferReservations, ReservationRejected

NOW = datetime.fromisoformat('2026-10-27T06:00:00+09:00')
DUE = '2026-10-26T23:00:00Z'
KEY = 'daily_2026-10-27_player'


class AdvanceReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manifest = Path(self.temp.name) / 'cards.json'
        self.card = {'source_url': 'https://stvv.jp/news/team/20261027_1/',
                     'text': '公式発表を確認。https://stvv.jp/news/team/20261027_1/',
                     'date_jst': '2026-10-27', 'slots': ['player', 'news'],
                     'status': 'ready', 'reviewed': True,
                     'asset_path': 'generated/card.png', 'sha256': 'a' * 64,
                     'dimensions': [1448, 1086]}
        self.write_card()
        self.history = {'news': [], 'used_posts': [], 'publication_log': [],
                        'pending_posts': {}, 'reserved_posts': {}}
        self.durable = copy.deepcopy(self.history)
        self.saved = []
        self.client = Mock()
        self.client.preflight.return_value = {'posts': [], 'remaining_capacity': 10}
        self.client.schedule.side_effect = lambda text, image, due: {
            'id': 'buffer-fixture', 'text': text, 'channelId': publisher.CHANNEL,
            'dueAt': due, 'status': 'scheduled', 'assets': [{'id': 'asset'}]}
        for p in [patch.object(media, 'MANIFEST', self.manifest),
                  patch.object(a, 'read_body', return_value='公式発表の確認済み本文。'),
                  patch.object(a, 'prepared_media', return_value=(True, 'https://raw.githubusercontent.com/image')),
                  patch.object(a, 'datetime', wraps=datetime)]:
            mocked = p.start()
            if p.attribute == 'datetime':
                mocked.now.return_value = NOW
            self.addCleanup(p.stop)

    def write_card(self):
        self.manifest.write_text(json.dumps({'enabled': True, 'cards': [self.card]}))

    def save(self, history):
        self.saved.append(copy.deepcopy(history))
        self.durable = copy.deepcopy(history)

    def run_one(self):
        return a.run(self.history, NOW, self.client, self.save, Mock())

    def accepted(self):
        self.assertEqual(self.run_one()['status'], 'reserved_in_buffer')
        return self.history['reserved_posts'][KEY]

    def test_persist_pending_before_one_send_and_reservation_is_not_published(self):
        def send(text, image, due):
            self.assertIn(KEY, self.durable['pending_posts'])
            return {'id': 'buffer-fixture', 'text': text, 'channelId': publisher.CHANNEL,
                    'dueAt': due, 'status': 'scheduled', 'assets': [{'id': 'asset'}]}
        self.client.schedule.side_effect = send
        record = self.accepted()
        self.assertEqual(record['due_at'], DUE)
        self.assertIn(KEY, self.history['used_posts'])
        self.assertFalse(self.history['publication_log'])
        self.assertFalse(self.history['news'])
        self.assertFalse(self.history['pending_posts'])
        self.assertFalse(record['x_display_verified'])
        self.client.schedule.assert_called_once()
        self.assertEqual(len(self.saved), 2)

    def test_pending_save_failure_sends_nothing(self):
        with self.assertRaises(OSError):
            a.run(self.history, NOW, self.client, Mock(side_effect=OSError()), Mock())
        self.client.schedule.assert_not_called()

    def test_timeout_leaves_durable_pending_and_next_run_never_resends(self):
        self.client.schedule.side_effect = TimeoutError('fixture timeout')
        with self.assertRaises(TimeoutError):
            self.run_one()
        self.assertIn(KEY, self.durable['pending_posts'])
        self.history = copy.deepcopy(self.durable)
        result = self.run_one()
        self.assertEqual(result['status'], 'blocked_pending_outcome_unknown')
        self.client.schedule.assert_called_once()

    def test_explicit_rejection_is_not_unknown_and_never_retried(self):
        self.client.schedule.side_effect = ReservationRejected('rejected')
        with self.assertRaises(ReservationRejected):
            self.run_one()
        self.assertEqual(self.durable['pending_posts'][KEY]['send_state'], 'rejected_no_retry')
        self.assertEqual(self.run_one()['status'], 'blocked_buffer_rejected')
        evidence = delivery_evidence({}, self.durable, '2026-10-26', 'vote', advance=True)
        self.assertEqual(evidence['delivery_state'], 'buffer_rejected_not_published')
        self.client.schedule.assert_called_once()

    def test_acceptance_save_failure_does_not_cause_recreation(self):
        def save(history):
            if len(self.saved) == 1:
                raise OSError('acceptance persistence failed')
            self.save(history)
        with self.assertRaises(OSError):
            a.run(self.history, NOW, self.client, save, Mock())
        self.history = copy.deepcopy(self.durable)
        self.assertEqual(self.run_one()['status'], 'blocked_pending_outcome_unknown')
        self.client.schedule.assert_called_once()

    def test_reconcile_sent_once_and_keep_x_unverified(self):
        record = self.accepted()
        self.client.get_post.return_value = {'id': 'buffer-fixture', 'text': record['text'],
            'dueAt': DUE, 'channelId': publisher.CHANNEL, 'status': 'sent', 'assets': [{'id': 'asset'}]}
        later = datetime.fromisoformat('2026-10-27T10:30:00+09:00')
        a.run(self.history, later, self.client, self.save, Mock())
        a.run(self.history, later, self.client, self.save, Mock())
        self.assertEqual(len(self.history['publication_log']), 1)
        self.assertFalse(self.history['publication_log'][0]['x_display_verified'])
        self.assertEqual(self.history['news'], [record['source']])
        self.client.schedule.assert_called_once()

    def test_changed_identity_or_early_sent_blocks_without_resending(self):
        record = self.accepted()
        original = {'id': 'buffer-fixture', 'text': record['text'], 'dueAt': DUE,
                    'channelId': publisher.CHANNEL, 'status': 'scheduled', 'assets': [{'id': 'asset'}]}
        for change in [{'id': 'different'}, {'text': 'changed'}, {'channelId': 'other'},
                       {'dueAt': '2026-10-27T09:00:00Z'}, {'status': 'sent'}, {'assets': []}]:
            with self.subTest(change=change):
                self.client.get_post.return_value = {**original, **change}
                with self.assertRaises(RuntimeError):
                    self.run_one()
        self.client.schedule.assert_called_once()

    def test_buffer_error_blocks_new_sends(self):
        record = self.accepted()
        self.client.get_post.return_value = {'id': 'buffer-fixture', 'text': record['text'],
            'dueAt': DUE, 'channelId': publisher.CHANNEL, 'status': 'error', 'assets': [{'id': 'asset'}]}
        self.assertEqual(self.run_one()['status'], 'blocked_reservation_error')
        self.assertFalse(self.history['publication_log'])
        self.client.schedule.assert_called_once()

    def test_new_reservation_blocks_same_source_in_other_slots(self):
        self.accepted()
        from prepared_media import prepared_duplicate_reason
        reason = prepared_duplicate_reason(self.history, self.card['text'] + publisher.HASHTAGS,
                                           self.card['source_url'], 'news', NOW)
        self.assertTrue(reason)
        self.client.get_post.return_value = {'id': 'buffer-fixture',
            'text': self.card['text'] + publisher.HASHTAGS, 'dueAt': DUE,
            'channelId': publisher.CHANNEL, 'status': 'scheduled', 'assets': [{'id': 'asset'}]}
        self.assertEqual(self.run_one()['status'], 'skipped_no_verified_content')
        self.client.schedule.assert_called_once()

    def test_official_or_image_gate_failure_sends_nothing(self):
        with patch.object(a, 'read_body', return_value=''):
            with self.assertRaises(RuntimeError):
                self.run_one()
        with patch.object(a, 'prepared_media', side_effect=ValueError('public bytes differ')):
            with self.assertRaises(ValueError):
                self.run_one()
        self.client.schedule.assert_not_called()
        self.assertFalse(self.saved)

    def test_remote_duplicate_or_occupied_time_sends_nothing(self):
        for post in [{'text': self.card['text'] + publisher.HASHTAGS, 'dueAt': None},
                     {'text': 'other content', 'dueAt': DUE},
                     {'text': 'same source: ' + self.card['source_url'], 'dueAt': None}]:
            self.client.preflight.return_value['posts'] = [dict(post, id='unknown', status='scheduled')]
            self.assertTrue(self.run_one()['status'].startswith('blocked_remote_'))
        self.client.schedule.assert_not_called()
        self.assertFalse(self.saved)

    def test_capacity_error_sends_nothing_and_expired_lead_does_not_shift_slot(self):
        self.client.preflight.side_effect = RuntimeError('capacity exhausted')
        with self.assertRaises(RuntimeError):
            self.run_one()
        self.client.preflight.side_effect = None
        with patch.object(a, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = datetime.fromisoformat('2026-10-27T07:31:00+09:00')
            self.assertEqual(self.run_one()['status'], 'skipped_reservation_lead_expired')
        self.client.schedule.assert_not_called()

    def test_unexpected_mutation_echo_retains_pending(self):
        self.client.schedule.side_effect = None
        self.client.schedule.return_value = {'id': 'returned', 'text': 'wrong',
            'channelId': publisher.CHANNEL, 'dueAt': DUE, 'status': 'scheduled', 'assets': [{'id': 'asset'}]}
        with self.assertRaises(RuntimeError):
            self.run_one()
        self.assertIn(KEY, self.durable['pending_posts'])
        self.assertFalse(self.history['publication_log'])

    def test_reviewed_first_start_checks_body_and_reservation_fact_identity(self):
        claim = '新川志音がリーグ初先発。'
        self.card['text'] = claim + self.card['source_url']
        self.card['editorial_fact'] = {'kind': 'league_first_start', 'subject': '新川志音',
            'claim': claim, 'source_body_sha256': hashlib.sha256(claim.encode()).hexdigest()}
        self.write_card()
        with patch.object(a, 'read_body', return_value='changed official body'):
            with self.assertRaises(RuntimeError):
                self.run_one()
        self.client.schedule.assert_not_called()
        with patch.object(a, 'read_body', return_value=claim):
            self.accepted()
        from editorial_novelty import distinct_fact_reason
        self.assertTrue(distinct_fact_reason(self.history, self.card, NOW))

    def test_manual_or_ci_cannot_run_live_transport(self):
        for event in ['workflow_dispatch', 'pull_request', 'push']:
            with patch.dict(os.environ, {'GITHUB_EVENT_NAME': event,
                    'GITHUB_SCHEDULE': '0 23 * * *', 'STVV_ADVANCE_RESERVATIONS': 'true'}, clear=True):
                with self.assertRaises(RuntimeError):
                    a.main()
        self.client.schedule.assert_not_called()

    def test_legacy_publisher_is_blocked_in_reservation_mode(self):
        with patch.dict(os.environ, {'STVV_ADVANCE_RESERVATIONS': 'true'}), patch.object(publisher, 'load') as load:
            self.assertEqual(publisher.main(), 'blocked_legacy_share_now')
            load.assert_not_called()

    def test_report_distinguishes_reservation_from_publication(self):
        before = copy.deepcopy(self.history)
        self.accepted()
        evidence = delivery_evidence(before, self.history, '2026-10-26', 'vote', advance=True)
        self.assertEqual(evidence['delivery_state'], 'buffer_scheduled_not_published')
        self.assertEqual(len(evidence['new_reservations']), 1)
        self.assertEqual(evidence['new_publications'], [])
        self.assertFalse(evidence['x_display_verified'])


class BufferTransportTests(unittest.TestCase):
    def test_scheduling_request_is_one_custom_scheduled_mutation(self):
        session = Mock()
        session.post.return_value.json.return_value = {'data': {'createPost': {'post': {'id': 'fixture'}}}}
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'offline-fixture'}):
            BufferReservations(session).schedule('確認済み', 'https://example.test/image', DUE)
        session.post.assert_called_once()
        args = session.post.call_args.kwargs['json']['variables']['input']
        self.assertEqual(args['mode'], 'customScheduled')
        self.assertEqual(args['dueAt'], DUE)
        self.assertNotIn('replyTo', args)
        self.assertEqual(len(args['assets']), 1)

    def test_explicit_mutation_error_has_a_distinct_rejected_state(self):
        session = Mock()
        session.post.return_value.json.return_value = {'data': {'createPost': {'message': 'denied'}}}
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'offline-fixture'}):
            with self.assertRaises(ReservationRejected):
                BufferReservations(session).schedule('確認済み', 'https://example.test/image', DUE)
        session.post.assert_called_once()

    def test_http_timeout_is_not_retried(self):
        session = Mock()
        session.post.side_effect = TimeoutError()
        with patch.dict(os.environ, {'BUFFER_API_KEY': 'offline-fixture'}):
            with self.assertRaises(TimeoutError):
                BufferReservations(session).schedule('確認済み', 'https://example.test/image', DUE)
        session.post.assert_called_once()

    def test_live_permission_capacity_channel_and_pagination_are_checked(self):
        client = BufferReservations(Mock())
        organization = {'id': 'org', 'limits': {'scheduledPosts': 10}}
        channel = {'id': publisher.CHANNEL, 'name': 'stvvlabo', 'service': 'twitter',
                   'externalLink': 'https://x.com/stvvlabo', 'isLocked': False,
                   'isDisconnected': False, 'isQueuePaused': False,
                   'allowedActions': ['scheduleUpdates']}
        def query(text, variables=None):
            if 'account {' in text:
                return {'account': {'organizations': [organization]}}
            if 'channels(input' in text:
                return {'channels': [channel]}
            return {'posts': {'edges': [], 'pageInfo': {'hasNextPage': False}}}
        client.query = Mock(side_effect=query)
        self.assertEqual(client.preflight()['remaining_capacity'], 10)
        for field, value in [('isLocked', True), ('isDisconnected', True),
                             ('isQueuePaused', True), ('name', 'other'),
                             ('service', 'instagram'), ('allowedActions', []),
                             ('externalLink', 'https://x.com/not_stvvlabo')]:
            original = channel[field]
            channel[field] = value
            with self.assertRaises(RuntimeError):
                client.preflight()
            channel[field] = original
        organization['limits']['scheduledPosts'] = -1
        with self.assertRaises(RuntimeError):
            client.preflight()
        client.query.return_value = None
        client.query.side_effect = lambda *args: {'posts': {'edges': [], 'pageInfo': {'hasNextPage': True}}}
        with self.assertRaises(RuntimeError):
            client.posts('org', ['scheduled'])

    def test_full_capacity_is_blocked(self):
        client = BufferReservations(Mock())
        client.query = Mock(side_effect=[
            {'account': {'organizations': [{'id': 'org', 'limits': {'scheduledPosts': 1}}]}},
            {'channels': [{'id': publisher.CHANNEL, 'name': 'stvvlabo', 'service': 'twitter',
                           'externalLink': 'https://x.com/stvvlabo', 'isLocked': False,
                           'isDisconnected': False, 'isQueuePaused': False,
                           'allowedActions': ['scheduleUpdates']}] }])
        client.posts = Mock(return_value=[{'id': 'existing'}])
        with self.assertRaises(RuntimeError):
            client.preflight()


if __name__ == '__main__':
    unittest.main()
