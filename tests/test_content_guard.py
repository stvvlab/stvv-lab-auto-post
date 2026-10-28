"""Regression cases from the two overlapping official Lommel posts."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from contextlib import ExitStack
from content_guard import duplicate_reason
import stvv_post as posting

URL = 'https://stvv.jp/news/game/20261019_1/'
OLD = '⚽ STVV、4–1でカップ戦初戦を突破！\n松澤海斗の同点弾、新川志音の加入後初ゴールも生まれ、ロンメルに逆転勝利。'
TIMES = '📊 公式記録で振り返る得点時間\nSTVV 4–1 ロンメル\n松澤海斗：15分\n新川志音：39分\nソエル・ソエル：62分\nムブク：71分'
SHOTS = '⚔️ シュート数比較\nSTVV 4–1 ロンメル\nSTVV 14／相手 6'
NOW = datetime(2026, 10, 21, 14, tzinfo=timezone(timedelta(hours=9)))


class FixedDateTime(datetime):
    """Keep historical duplicate-guard tests at their original 2026-10-21 clock."""
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)


class ContentGuardTests(unittest.TestCase):
    def setUp(self):
        clock = patch.object(posting, 'datetime', FixedDateTime)
        clock.start()
        self.addCleanup(clock.stop)

    def history(self, text=OLD, source=URL, pending=False):
        item = {'text': text, 'source': source, 'submitted_at': NOW.isoformat()}
        return {'used_posts': [], 'publication_log': [] if pending else [item],
                'pending_posts': {'older': item} if pending else {}}

    def test_result_then_goal_minutes_is_blocked_across_slots(self):
        self.assertIsNotNone(duplicate_reason(self.history(), TIMES, URL, NOW))

    def test_pending_and_tracking_url_variations_are_blocked(self):
        self.assertIsNotNone(duplicate_reason(self.history(pending=True), TIMES, URL+'?utm_source=x', NOW))

    def test_same_match_across_official_and_stats_provider_is_blocked(self):
        self.assertIsNotNone(duplicate_reason(self.history(), TIMES.replace('ロンメル', 'Lommel'), 'thesportsdb:2611487', NOW))

    def test_new_shot_comparison_is_allowed_once(self):
        self.assertIsNone(duplicate_reason(self.history(), SHOTS, 'thesportsdb:2611487', NOW))
        self.assertIsNotNone(duplicate_reason(self.history(SHOTS), SHOTS.replace('比較', 'データ'), URL, NOW))

    def test_unrelated_new_official_news_is_allowed(self):
        self.assertIsNone(duplicate_reason(self.history(), '新しい公式発表', 'https://stvv.jp/news/new-announcement/', NOW))

    def test_expired_publication_does_not_block_new_coverage(self):
        history = self.history()
        history['publication_log'][0]['submitted_at'] = (NOW - timedelta(days=8)).isoformat()
        self.assertIsNone(duplicate_reason(history, TIMES, URL, NOW))

    def test_previous_comparison_cannot_be_reused_as_new_data(self):
        history = self.history(SHOTS)
        history['publication_log'].append({'text': OLD, 'source': URL})
        rewritten = 'シュート：14 対 6\nSTVV 4–1 ロンメル'
        self.assertIsNotNone(duplicate_reason(history, rewritten, URL, NOW))

    def test_whitespace_punctuation_and_hashtags_do_not_evade_exact_guard(self):
        self.assertIsNotNone(duplicate_reason(self.history('質問：どのプレー？'), '質問 どのプレー！\n#STVV', None, NOW))

    def test_repeated_content_stops_before_image_or_buffer(self):
        with ExitStack() as stack:
            for name, value in [('load', self.history()), ('load_feedback', []),
                                ('feedback_scores', {}), ('auto_feedback_scores', {}),
                                ('slot_for_run', ('data', '2026-10-21')), ('latest_match', None)]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            stack.enter_context(patch('official_match_data.scoring_data', return_value=(TIMES, URL)))
            image = stack.enter_context(patch.object(posting, 'content_card_media'))
            publish = stack.enter_context(patch.object(posting, 'publish'))
            self.assertEqual(posting.main(), 'skipped_repeated_content')
            image.assert_not_called()
            publish.assert_not_called()

    def run_news_candidates(self, candidates, pending=False, slot='news'):
        history = self.history(pending=pending)
        history['news'] = []
        with ExitStack() as stack:
            for name, value in [('load', history), ('load_feedback', []),
                                ('feedback_scores', {}), ('auto_feedback_scores', {}),
                                ('slot_for_run', (slot, '2026-10-21')),
                                ('articles', candidates)]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            # This unit tests HTML-news selection in isolation. A production-ready
            # imagegen queue item must not override the mocked article list.
            stack.enter_context(patch('prepared_media.prepared_candidates', return_value=[]))
            image = stack.enter_context(patch.object(posting, 'content_card_media', return_value='https://example.test/card.jpg'))
            publish = stack.enter_context(patch.object(posting, 'publish', return_value=True))
            result = posting.main()
            return result, image, publish

    def test_repeated_news_candidate_does_not_hide_next_distinct_article(self):
        fresh = 'https://stvv.jp/news/team/20261020_1/'
        result, image, publish = self.run_news_candidates([
            (URL, (NOW.date(), 'ロンメル戦の試合結果について')),
            (fresh, (NOW.date(), '別の公式発表について'))])
        self.assertEqual(result, 'submitted_to_buffer')
        self.assertEqual(image.call_args.kwargs['source'], fresh)
        self.assertEqual(publish.call_args.args[4], fresh)
        self.assertNotIn('ロンメル', publish.call_args.args[2])

    def test_all_news_candidates_pending_or_published_stop_before_image(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                result, image, publish = self.run_news_candidates([
                    (URL+'?utm_source=x', (NOW.date(), 'ロンメル戦の試合結果について'))], pending)
                self.assertEqual(result, 'skipped_repeated_content')
                image.assert_not_called()
                publish.assert_not_called()

    def test_player_slot_selects_official_player_headline_after_unrelated_article(self):
        fresh = 'https://stvv.jp/news/team/player-announcement/'
        result, image, publish = self.run_news_candidates([
            ('https://stvv.jp/news/team/general/', (NOW.date(), '公式の試合日程')),
            (fresh, (NOW.date(), '選手の復帰について'))], slot='player')
        self.assertEqual(result, 'submitted_to_buffer')
        self.assertEqual(image.call_args.args[0], 'player')
        self.assertEqual(image.call_args.kwargs['source'], fresh)
        self.assertEqual(publish.call_args.args[5], fresh)

    def test_player_slot_without_player_article_skips_before_media(self):
        result, image, publish = self.run_news_candidates([
            ('https://stvv.jp/news/team/general/', (NOW.date(), '公式の試合日程'))], slot='player')
        self.assertEqual(result, 'skipped_no_verified_content')
        image.assert_not_called()
        publish.assert_not_called()

    def test_player_slot_keeps_published_and_pending_source_guard(self):
        for pending in (False, True):
            result, image, publish = self.run_news_candidates([
                (URL, (NOW.date(), '日本人選手のロンメル戦での得点について'))],
                pending=pending, slot='player')
            self.assertEqual(result, 'skipped_repeated_content')
            image.assert_not_called()
            publish.assert_not_called()

    def run_repeated_match_vote(self, fallback_already_posted=False):
        fallback = 'MOMを決めるなら、どのプレーを重視する？'
        history = self.history(TIMES)
        if fallback_already_posted:
            history['publication_log'].append({'text': fallback, 'source': None})
        with ExitStack() as stack:
            # Test the repeated stats-provider path, independent of a live
            # reviewed editorial queue that may legitimately cover another fact.
            stack.enter_context(patch('prepared_media.prepared_candidates', return_value=[]))
            for name, value in [('load', history), ('load_feedback', []),
                                ('feedback_scores', {}), ('auto_feedback_scores', {}),
                                ('slot_for_run', ('vote', '2026-10-21')),
                                ('latest_match', {'idEvent': '2611487'}),
                                ('match_post', TIMES + '\nこの試合で印象に残った場面は？')]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            choose = stack.enter_context(patch.object(posting, 'choose_fallback', return_value=fallback))
            image = stack.enter_context(patch.object(posting, 'content_card_media', return_value='https://example.test/card.jpg'))
            publish = stack.enter_context(patch.object(posting, 'publish', return_value=True))
            return posting.main(), choose, image, publish, fallback

    def test_repeated_match_vote_does_not_fill_slot_with_generic_question(self):
        result, choose, image, publish, fallback = self.run_repeated_match_vote()
        self.assertEqual(result, 'skipped_repeated_content')
        choose.assert_not_called()
        image.assert_not_called()
        publish.assert_not_called()

    def test_repeated_match_and_repeated_fallback_still_stop_before_media(self):
        result, choose, image, publish, _ = self.run_repeated_match_vote(True)
        self.assertEqual(result, 'skipped_repeated_content')
        choose.assert_not_called()
        image.assert_not_called()
        publish.assert_not_called()
