import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
import prepared_media as media
import stvv_post as posting
from editorial_novelty import fact_metadata, distinct_fact_reason

NOW = datetime.now(posting.JST)
URL = 'https://stvv.jp/news/game/' + NOW.strftime('%Y%m%d') + '_1/'
CLAIM = '架空太郎がリーグ初先発。'
BODY = '公式本文。' * 20 + CLAIM
TEXT = '🌟 ' + CLAIM + '\n今後どんなプレーに期待しますか？\n\n公式：' + URL


class NoveltyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'generated').mkdir()
        asset = self.root / 'generated/card.png'
        Image.new('RGB', (40, 30), 'navy').save(asset)
        self.raw = asset.read_bytes()
        self.card = dict(source_url=URL, text=TEXT, slots=['vote'], date_jst=NOW.date().isoformat(),
                         reviewed=True, status='ready', asset_path='generated/card.png',
                         dimensions=[40, 30], sha256=hashlib.sha256(self.raw).hexdigest(),
                         editorial_fact=dict(kind='league_first_start', subject='架空太郎', claim=CLAIM,
                                             source_body_sha256=hashlib.sha256(BODY.encode()).hexdigest()))
        self.manifest = self.root / 'cards.json'
        self.write()
        self.history = {'news': [URL], 'used_posts': [], 'pending_posts': {},
                        'publication_log': [{'source': URL, 'text': 'STVV 2–3 クラブ・ブルージュ'}]}
        for item in [patch.object(media, 'ROOT', self.root), patch.object(media, 'MANIFEST', self.manifest),
                     patch.object(media.subprocess, 'check_output', return_value='a' * 40)]:
            item.start()
            self.addCleanup(item.stop)

    def write(self):
        self.manifest.write_text(json.dumps({'enabled': True, 'cards': [self.card]}))

    def test_historical_conflict_blocks_ambiguous_first_ever_claim(self):
        # Official May 22 match report already lists Shinkawa as a starter.
        self.card['editorial_fact']['subject'] = '新川志音'
        self.card['editorial_fact']['claim'] = '新川志音がリーグ初先発。'
        self.card['text'] = self.card['text'].replace('架空太郎', '新川志音')
        self.write()
        self.assertIsNone(fact_metadata(self.card, NOW))
        self.assertTrue(distinct_fact_reason(self.history, self.card, NOW))
        self.assertTrue(media.prepared_duplicate_reason(self.history, self.card['text'], URL, 'vote', NOW))

    def test_distinct_reviewed_milestone_passes_but_recap_and_generic_question_do_not(self):
        self.assertIsNone(media.prepared_duplicate_reason(self.history, TEXT, URL, 'vote', NOW))
        for message in ['STVV 2–3 クラブ・ブルージュ', '次戦は誰に期待しますか？']:
            self.assertTrue(media.prepared_duplicate_reason(self.history, message, URL, 'vote', NOW))
        self.assertTrue(media.prepared_duplicate_reason(self.history, TEXT, URL, 'news', NOW))

    def test_invalid_unreviewed_stale_score_or_unsupported_fact_cannot_open_gate(self):
        original = copy.deepcopy(self.card)
        variants = [dict(reviewed=False), dict(date_jst=(NOW.date()-timedelta(days=8)).isoformat()),
                    dict(text=TEXT+'\nSTVV 2–3'), dict(editorial_fact={'kind': 'opinion'})]
        for change in variants:
            self.card = {**copy.deepcopy(original), **change}
            self.write()
            self.assertTrue(media.prepared_duplicate_reason(self.history, self.card['text'], URL, 'vote', NOW))

    def test_pending_source_blocks_new_fact_without_mutation(self):
        self.history['pending_posts']['unknown'] = {'source': URL, 'text': '結果'}
        before = copy.deepcopy(self.history)
        self.assertTrue(distinct_fact_reason(self.history, self.card, NOW))
        self.assertEqual(self.history, before)

    def test_paraphrase_or_fact_id_cannot_republish_milestone(self):
        for previous in [{'source': URL, 'text': '架空太郎が初スタメン'},
                         {'source': URL, 'text': '別の表現', 'editorial_fact': fact_metadata(self.card, NOW)}]:
            self.history['publication_log'].append(previous)
            self.assertTrue(distinct_fact_reason(self.history, self.card, NOW))
            self.history['publication_log'].pop()

    def test_changed_official_body_fails_before_public_image_request(self):
        session = Mock()
        with patch('preparation_inventory.read_body', return_value=BODY+'更新'):
            with self.assertRaises(ValueError):
                media.prepared_media(session, 'vote', TEXT, URL)
        session.get.assert_not_called()

    def test_matching_official_body_and_image_bytes_pass(self):
        session = Mock()
        session.get.return_value.content = self.raw
        with patch('preparation_inventory.read_body', return_value=BODY):
            enabled, url = media.prepared_media(session, 'vote', TEXT, URL)
        self.assertTrue(enabled)
        self.assertIn('/'+'a'*40+'/generated/card.png', url)

    def test_pending_is_persisted_with_fact_before_send_and_unknown_not_retried(self):
        order = []
        def save(history):
            self.assertIn('fact_id', history['pending_posts']['daily']['editorial_fact'])
            order.append('save')
        def send(*args, **kwargs):
            order.append('send')
            raise RuntimeError('unknown')
        with patch.object(posting, 'save', side_effect=save), patch.object(posting, 'send', side_effect=send) as transport:
            with self.assertRaises(RuntimeError):
                posting.publish(self.history, 'daily', TEXT+posting.HASHTAGS, 'vote', URL, image_url='https://example.test/card')
            self.assertFalse(posting.publish(self.history, 'daily', TEXT+posting.HASHTAGS, 'vote', URL, image_url='https://example.test/card'))
            self.assertEqual(transport.call_count, 1)
        self.assertEqual(order, ['save', 'send'])

    def test_success_persists_fact_and_blocks_later_slot(self):
        with patch.object(posting, 'save'), patch.object(posting, 'send', return_value={'id': 'test', 'status': 'sent'}) as send:
            self.assertTrue(posting.publish(self.history, 'daily', TEXT+posting.HASHTAGS, 'vote', URL, image_url='https://example.test/card'))
            self.assertFalse(posting.publish(self.history, 'different_daily', TEXT+posting.HASHTAGS, 'vote', URL, image_url='https://example.test/card'))
            self.assertEqual(send.call_count, 1)
        self.assertIn('fact_id', self.history['publication_log'][-1]['editorial_fact'])
        self.assertTrue(media.prepared_duplicate_reason(self.history, TEXT, URL, 'vote', NOW))

    def test_invalid_reviewed_metadata_is_blocked_before_pending_or_send(self):
        self.card['editorial_fact']['source_body_sha256'] = 'invalid'
        self.write()
        before = copy.deepcopy(self.history)
        with patch.object(posting, 'save') as save, patch.object(posting, 'send') as send:
            self.assertFalse(posting.publish(self.history, 'bad', TEXT+posting.HASHTAGS, 'vote', URL, image_url='https://example.test/card'))
        save.assert_not_called()
        send.assert_not_called()
        self.assertEqual(self.history, before)

    def test_regular_vote_path_selects_reviewed_new_fact_over_existing_recap(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name, value in [('load', self.history), ('load_feedback', []), ('feedback_scores', {}),
                                ('auto_feedback_scores', {}), ('slot_for_run', ('vote', NOW.date().isoformat()))]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            image = stack.enter_context(patch.object(posting, 'content_card_media', return_value='https://example.test/card'))
            publish = stack.enter_context(patch.object(posting, 'publish', return_value=True))
            self.assertEqual(posting.main(), 'submitted_to_buffer')
        image.assert_called_once()
        self.assertEqual(publish.call_args.args[2], TEXT+posting.HASHTAGS)


if __name__ == '__main__':
    unittest.main()
