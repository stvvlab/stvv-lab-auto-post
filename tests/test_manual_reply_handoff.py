"""Manual correction must remain read-only and parent-bound."""
import copy
import unittest
from unittest.mock import patch

import manual_reply_handoff as handoff

SOURCE = 'https://stvv.jp/news/game/20260522_1/'
PARENT_SOURCE = 'https://stvv.jp/news/game/20261026_1/'
PARENT_URL = 'https://x.com/stvvlabo/status/2114727647368331366'
PARENT_TEXT = '🌟 新川志音がリーグ初先発。\n公式：' + PARENT_SOURCE
CORRECTION = ('【訂正】10/26の投稿で新川志音選手を「リーグ初先発」と紹介しましたが、'
              'STVV公式の5/22アンデルレヒト戦の記事には、すでに先発出場の記録があります。'
              '10/26を初先発と断定した表現は不正確でした。訂正します。\n'
              '公式：' + SOURCE)
PARENT = {'parent_key':'daily_2026-10-26_vote', 'parent_x_url':PARENT_URL,
          'parent_post_id':'2114727647368331366', 'owner':'stvvlabo',
          'verified':True, 'parent_text':PARENT_TEXT, 'buffer_id':'buffer1',
          'source_url':PARENT_SOURCE}
HISTORY = {'publication_log':[{'key':PARENT['parent_key'], 'text':PARENT_TEXT,
                               'buffer_id':'buffer1', 'source':PARENT_SOURCE}]}
DRAFT = {'kind':'correction', 'status':'draft', 'reviewed':False,
         'parent_key':PARENT['parent_key'], 'parent_x_url':PARENT_URL,
         'parent_post_id':PARENT['parent_post_id'], 'source_url':SOURCE,
         'text':CORRECTION, 'evidence_excerpt':'新川志音がベルギー移籍後初先発'}
QUEUE = {'enabled':False, 'transport':None, 'replies':[DRAFT]}
BODY = '公式試合記事。新川志音がベルギー移籍後初先発。アンデルレヒト戦で先発。'


class ManualHandoffTests(unittest.TestCase):
    def test_verified_correction_is_read_only_and_not_ready(self):
        history, queue = copy.deepcopy(HISTORY), copy.deepcopy(QUEUE)
        with patch('supplemental_replies.read_parent_registry', return_value=[PARENT]):
            result = handoff.prepare_manual_handoff(history, queue, PARENT['parent_key'], BODY)
        self.assertEqual(result['status'], 'manual_review_required')
        self.assertFalse(result['auto_send'])
        self.assertEqual(result['parent_x_url'], PARENT_URL)
        self.assertEqual(history, HISTORY)
        self.assertEqual(queue, QUEUE)
        self.assertNotIn('pending_posts', history)
        self.assertNotIn('pending_replies', history)

    def test_unverified_historical_evidence_is_blocked(self):
        with patch('supplemental_replies.read_parent_registry', return_value=[PARENT]):
            with self.assertRaises(ValueError):
                handoff.prepare_manual_handoff(HISTORY, QUEUE, PARENT['parent_key'], '別の記事')

    def test_unrelated_parent_is_blocked(self):
        bad = copy.deepcopy(QUEUE)
        bad['replies'][0]['parent_x_url'] = 'https://x.com/stvvlabo/status/9999'
        with patch('supplemental_replies.read_parent_registry', return_value=[PARENT]):
            with self.assertRaises(ValueError):
                handoff.prepare_manual_handoff(HISTORY, bad, PARENT['parent_key'], BODY)

    def test_no_automatic_transport_or_preapproved_candidate(self):
        for change in ({'enabled':True}, {'transport':'api'}):
            q = {**QUEUE, **change}
            with self.assertRaises(ValueError):
                handoff.prepare_manual_handoff(HISTORY, q, PARENT['parent_key'], BODY)
        q = copy.deepcopy(QUEUE)
        q['replies'][0]['reviewed'] = True
        with self.assertRaises(ValueError):
            handoff.prepare_manual_handoff(HISTORY, q, PARENT['parent_key'], BODY)


if __name__ == '__main__':
    unittest.main()
