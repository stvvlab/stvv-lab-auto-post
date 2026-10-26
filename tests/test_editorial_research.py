import copy
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import requests
import editorial_research as research
from stvv_post import JST

NOW = datetime(2026, 10, 26, 20, tzinfo=JST)
URL = 'https://stvv.jp/news/game/20261026_1/'
BODY = ('新川志音がリーグ初先発。相手のカウンターから失点した。リーグ4連敗となった。'
        'この本文は公式情報の引用を下書き候補に留めるための検証用です。')


class ResearchTests(unittest.TestCase):
    def build(self, text='STVV 2–3 クラブ・ブルージュ', pending=None, body=BODY):
        history = {'publication_log': [{'source': URL, 'text': text}], 'pending_posts': pending or {}}
        manifest = {'cards': []}
        before = copy.deepcopy((history, manifest))
        with patch.object(research, 'read_body', return_value=body) as read:
            result = research.build_research(history, manifest, NOW, Mock())
        self.assertEqual((history, manifest), before)
        return result, read

    def test_used_source_yields_three_exact_evidence_drafts_without_duplicate_bypass(self):
        result, _ = self.build()
        self.assertEqual({d['angle'] for d in result['drafts']}, {'player', 'analysis', 'vote'})
        for draft in result['drafts']:
            self.assertIn(draft['evidence_excerpt'], BODY)
            self.assertFalse(draft['reviewed'])
            self.assertFalse(draft['can_publish'])
            self.assertTrue(draft['current_duplicate_gate'])
            self.assertLessEqual(draft['x_length_with_tags'], 270)
            self.assertNotIn('asset_path', draft)
        self.assertFalse(result['publication_performed'])

    def test_known_evidence_is_not_proposed_again(self):
        result, _ = self.build(text=BODY)
        self.assertEqual(result['drafts'], [])

    def test_pending_source_does_not_fetch_or_spawn_related_drafts(self):
        result, read = self.build(pending={'p': {'source': URL}})
        self.assertEqual(result['drafts'], [])
        read.assert_not_called()

    def test_id_is_stable_for_identical_evidence(self):
        first, _ = self.build()
        second, _ = self.build()
        self.assertEqual([d['candidate_id'] for d in first['drafts']], [d['candidate_id'] for d in second['drafts']])

    def test_external_sponsor_stale_future_or_invalid_source_is_rejected(self):
        for url in ['https://evil.test/news/20261026_1/', URL.replace('game/', 'sponsor/'),
                    URL.replace('20261026', '20261001'), URL.replace('20261026', '20261027'),
                    URL.replace('20261026', '20269999')]:
            self.assertFalse(research.eligible_source(url, NOW))

    def test_failed_body_is_not_reported_as_no_news(self):
        with patch.object(research, 'read_body', side_effect=requests.Timeout('timeout')):
            result = research.build_research({'publication_log': [{'source': URL}]}, {}, NOW, Mock())
        self.assertEqual(result['source_checks'][0]['status'], 'source_unavailable')
        self.assertEqual(result['status'], 'source_scan_failed')
        self.assertEqual(result['drafts'], [])


if __name__ == '__main__':
    unittest.main()
