"""Scheduled path must attach the adopted image or send nothing. Offline."""
import unittest
import tempfile
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
import stvv_post as posting


class ScheduledStadiumTests(unittest.TestCase):
    def test_composition_cycle_advances_only_with_publication_history(self):
        history = {'publication_log': [], 'pending_posts': {}}
        observed = []
        for index in range(6):
            observed.append(posting.next_card_variant(history))
            self.assertEqual(posting.next_card_variant(history), observed[-1])
            history['pending_posts']['unconfirmed'] = {}
            self.assertEqual(posting.next_card_variant(history), observed[-1])
            history['publication_log'].append({'key': str(index)})
        self.assertEqual(observed, ['stadium', 'split', 'poster'] * 2)

    def test_mock_results_do_not_pollute_actions_posting_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / 'summary.md'
            for schedule in ['', 'invalid', '0 23 * * *']:
                with patch.dict(posting.os.environ, {
                    'GITHUB_STEP_SUMMARY': str(summary),
                    'GITHUB_SCHEDULE': schedule,
                }), patch.object(posting, 'log'):
                    posting.run_result('submitted_to_buffer', 'test result')
                if schedule in posting.SLOTS:
                    self.assertIn('submitted_to_buffer', summary.read_text())
                else:
                    self.assertFalse(summary.exists())

    def run_scheduled_vote(self, media):
        history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
        with ExitStack() as stack:
            for name, value in [
                ('load', history), ('load_feedback', []), ('feedback_scores', {}),
                ('auto_feedback_scores', {}), ('slot_for_run', ('vote', '2026-10-21')),
                ('latest_match', {'idEvent': 'new-match'}),
                ('match_post', '対戦相手戦をどこから振り返る？\n① 攻撃\n② 守備\n③ 選手'),
            ]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            image = stack.enter_context(patch.object(posting, 'content_card_media', return_value=media))
            publish = stack.enter_context(patch.object(posting, 'publish'))
            for old in ['generic_topic_media', 'faceless_player_media', 'media_for']:
                stack.enter_context(patch.object(posting, old, side_effect=AssertionError('Old card fallback used')))
            result = posting.main()
            return image, publish, result

    def test_verified_image_flows_to_buffer_publication(self):
        url = 'https://raw.githubusercontent.com/stvvlab/stvv-lab-auto-post/revision/generated/content.jpg'
        image, publish, result = self.run_scheduled_vote(url)
        image.assert_called_once_with('vote', '2026-10-21', '対戦相手戦をどこから振り返る？\n① 攻撃\n② 守備\n③ 選手', source='thesportsdb:new-match', variant='stadium')
        publish.assert_called_once()
        self.assertIn('① 攻撃\n② 守備\n③ 選手', publish.call_args.args[2])
        self.assertEqual(publish.call_args.args[6], url)
        self.assertEqual(result, 'submitted_to_buffer')

    def test_failed_image_never_falls_back_or_publishes(self):
        _, publish, result = self.run_scheduled_vote(None)
        publish.assert_not_called()
        self.assertEqual(result, 'skipped_image_verification')

    def test_no_verified_non_vote_content_is_an_explicit_skip(self):
        history = {'used_posts': [], 'pending_posts': {}, 'publication_log': [], 'news': []}
        with patch.object(posting, 'load', return_value=history), \
             patch.object(posting, 'load_feedback', return_value=[]), \
             patch.object(posting, 'feedback_scores', return_value={}), \
             patch.object(posting, 'auto_feedback_scores', return_value={}), \
             patch.object(posting, 'articles', return_value=[]), \
             patch.object(posting, 'slot_for_run', return_value=('player', '2026-10-21')):
            self.assertEqual(posting.main(), 'skipped_no_verified_content')

    def test_vote_without_verified_context_never_uses_generic_fallback(self):
        history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
        with ExitStack() as stack:
            for name, value in [('load', history), ('load_feedback', []),
                                ('feedback_scores', {}), ('auto_feedback_scores', {}),
                                ('slot_for_run', ('vote', '2026-10-22')), ('latest_match', None)]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            choose = stack.enter_context(patch.object(posting, 'choose_fallback'))
            image = stack.enter_context(patch.object(posting, 'content_card_media'))
            publish = stack.enter_context(patch.object(posting, 'publish'))
            self.assertEqual(posting.main(), 'skipped_no_verified_content')
            choose.assert_not_called()
            image.assert_not_called()
            publish.assert_not_called()

    def test_official_data_reaches_image_but_never_reposts_same_copy(self):
        message, source = '公式得点時間データ', 'https://stvv.jp/news/game/20261019_1/'
        for state in ['new', 'published', 'pending', 'unavailable']:
            history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
            old = {'text': message + posting.HASHTAGS}
            if state == 'published':
                history['publication_log'].append(old)
            if state == 'pending':
                history['pending_posts']['older_data'] = old
            with ExitStack() as stack:
                for name, value in [('load', history), ('load_feedback', []),
                                    ('feedback_scores', {}), ('auto_feedback_scores', {}),
                                    ('slot_for_run', ('data', '2026-10-21')), ('latest_match', None)]:
                    stack.enter_context(patch.object(posting, name, return_value=value))
                stack.enter_context(patch('official_match_data.scoring_data',
                                         return_value=None if state == 'unavailable' else (message, source)))
                image = stack.enter_context(patch.object(posting, 'content_card_media', return_value='https://example.org/card.jpg'))
                publish = stack.enter_context(patch.object(posting, 'publish', return_value=True))
                result = posting.main()
                if state == 'new':
                    self.assertEqual(result, 'submitted_to_buffer')
                    image.assert_called_once_with('data', '2026-10-21', message, source=source, variant='stadium')
                    publish.assert_called_once()
                else:
                    self.assertEqual(result, 'skipped_no_verified_content' if state == 'unavailable'
                                     else 'skipped_repeated_content')
                    image.assert_not_called()
                    publish.assert_not_called()
