"""Offline tests: quality gate runs before pending state / Buffer calls."""
import copy
import unittest
from unittest.mock import patch
import stvv_post as p


class PublishQualityIntegrationTests(unittest.TestCase):
    def history(self):
        return {"used_posts": [], "pending_posts": {}, "publication_log": [], "news": []}

    def test_unverified_news_blocks_without_state_change(self):
        history = self.history()
        initial = copy.deepcopy(history)
        with patch.object(p, "save") as save, patch.object(p, "send") as send:
            result = p.publish(history, "test_news", "試合速報", "news", source=None)
        self.assertFalse(result)
        self.assertEqual(history, initial)
        save.assert_not_called()
        send.assert_not_called()

    def test_sponsor_blocks_before_sending(self):
        history = self.history()
        with patch.object(p, "save") as save, patch.object(p, "send") as send:
            result = p.publish(history, "test_vote", "スポンサーのニュース", "vote")
        self.assertFalse(result)
        save.assert_not_called()
        send.assert_not_called()

    def test_valid_sourced_news_reaches_send(self):
        history = self.history()
        with patch.object(p, "save"), patch.object(p, "send", return_value={"id": "test-buffer-id", "status": "sent"}) as send:
            result = p.publish(history, "test_sourced", "STVV公式ニュース速報", "news",
                               source="https://stvv.jp/news/example/")
        self.assertTrue(result)
        send.assert_called_once()
        self.assertIn("test_sourced", history["used_posts"])

    def test_generic_warning_is_not_a_blocker(self):
        history = self.history()
        with patch.object(p, "save"), patch.object(p, "send", return_value={"id": "test-id", "status": "sent"}) as send:
            result = p.publish(history, "test_vote_warning", "ここが重要です", "vote")
        self.assertTrue(result)
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
