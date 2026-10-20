"""Scheduled path must attach the adopted image or send nothing. Offline."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch
import stvv_post as posting


class ScheduledStadiumTests(unittest.TestCase):
    def run_scheduled_vote(self, media):
        history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
        with ExitStack() as stack:
            for name, value in [
                ('load', history), ('load_feedback', []), ('feedback_scores', {}),
                ('auto_feedback_scores', {}), ('slot_for_run', ('vote', '2026-10-21')),
                ('latest_match', None), ('choose_fallback', '次に読みたい分析は？'),
            ]:
                stack.enter_context(patch.object(posting, name, return_value=value))
            image = stack.enter_context(patch.object(posting, 'content_card_media', return_value=media))
            publish = stack.enter_context(patch.object(posting, 'publish'))
            for old in ['generic_topic_media', 'faceless_player_media', 'media_for']:
                stack.enter_context(patch.object(posting, old, side_effect=AssertionError('Old card fallback used')))
            posting.main()
            return image, publish

    def test_verified_image_flows_to_buffer_publication(self):
        url = 'https://raw.githubusercontent.com/stvvlab/stvv-lab-auto-post/revision/generated/content.jpg'
        image, publish = self.run_scheduled_vote(url)
        image.assert_called_once_with('vote', '2026-10-21', '次に読みたい分析は？', source=None)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[2], '次に読みたい分析は？' + posting.HASHTAGS)
        self.assertEqual(publish.call_args.args[6], url)

    def test_failed_image_never_falls_back_or_publishes(self):
        _, publish = self.run_scheduled_vote(None)
        publish.assert_not_called()
