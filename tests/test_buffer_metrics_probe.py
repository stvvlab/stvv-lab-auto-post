import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from buffer_metrics_probe import collect, eligible_posts, read_metrics

NOW = datetime(2026, 10, 27, 2, 0, tzinfo=timezone.utc)


def item(hours, id='a', status='sent'):
    return {'key': 'post-' + id, 'buffer_id': id, 'buffer_status': status,
            'submitted_at': (NOW - timedelta(hours=hours)).isoformat(),
            'slot': 'news', 'source': 'https://stvv.jp/news/game/example/'}


class BufferMetricsProbeTests(unittest.TestCase):
    def test_only_sent_48h_to_14d_and_deduplicated(self):
        history = {'publication_log': [item(50, 'a'), item(50, 'a'), item(20, 'b'),
                                       item(60, 'c', 'scheduled'), item(340, 'd'),
                                       item(55, 'e')]}
        self.assertEqual([x['buffer_id'] for x in eligible_posts(history, NOW)], ['a', 'e'])

    def test_never_query_pending_unknown_or_future(self):
        session = Mock()
        result = collect({'publication_log': [item(50, 'a', 'pending'), item(1, 'b')]},
                         NOW, session, 'secret')
        self.assertEqual(result['status'], 'no_eligible_sent_posts')
        session.post.assert_not_called()

    def test_valid_read_only_query_preserves_zero_and_freshness(self):
        session = Mock()
        session.post.return_value.json.return_value = {'data': {'post': {
            'id': 'a', 'status': 'sent', 'metricsUpdatedAt': '2026-10-27T00:00:00Z',
            'metrics': [{'type': 'impressions', 'name': 'Impressions', 'value': 0, 'unit': 'count'},
                        {'type': 'reactions', 'name': 'Reactions', 'value': 3, 'unit': 'count'}]}}}
        report = collect({'publication_log': [item(50)]}, NOW, session, 'secret')
        self.assertEqual(report['status'], 'metrics_collected')
        self.assertEqual(report['posts'][0]['metrics']['impressions']['value'], 0)
        self.assertFalse(report['x_display_verified'])
        args = session.post.call_args.kwargs
        self.assertIn('query GetPostMetrics', args['json']['query'])
        self.assertNotIn('mutation', args['json']['query'].lower())
        self.assertEqual(args['json']['variables'], {'id': 'a'})

    def test_missing_metrics_not_reported_as_zero(self):
        session = Mock()
        session.post.return_value.json.return_value = {'data': {'post': {
            'id': 'a', 'status': 'sent', 'metricsUpdatedAt': None, 'metrics': None}}}
        report = collect({'publication_log': [item(50)]}, NOW, session, 'secret')
        self.assertEqual(report['status'], 'no_metrics_collected')
        self.assertIsNone(report['posts'][0]['metrics'])

    def test_api_error_sanitized_and_no_retry(self):
        session = Mock()
        session.post.return_value.json.return_value = {'errors': [{'message': 'secret'}]}
        report = collect({'publication_log': [item(50)]}, NOW, session, 'secret')
        self.assertEqual(report['posts'][0]['metrics_state'], 'query_failed')
        self.assertNotIn('secret', str(report))
        self.assertEqual(session.post.call_count, 1)

    def test_missing_key_does_not_make_request(self):
        session = Mock()
        report = collect({'publication_log': [item(50)]}, NOW, session, None)
        self.assertEqual(report['status'], 'missing_personal_api_key')
        session.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
