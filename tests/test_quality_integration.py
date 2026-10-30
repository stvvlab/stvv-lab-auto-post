"""Offline tests: quality gate runs before pending state / Buffer calls."""
import copy
import unittest
from unittest.mock import patch
import stvv_post as p


class PublishQualityIntegrationTests(unittest.TestCase):
    def test_japanese_weighted_overflow_never_saves_or_sends(self):
        history = self.history()
        initial = copy.deepcopy(history)
        with patch.object(p, "save") as save, patch.object(p, "send") as send:
            self.assertFalse(p.publish(history, "long", "あ" * 136, "vote"))
        self.assertEqual(history, initial)
        save.assert_not_called()
        send.assert_not_called()

    def test_long_source_url_is_shortened_for_limit_and_pending_precedes_send(self):
        history = self.history()
        source = "https://stvv.jp/news/" + "a" * 300 + "/"
        message = "公式ニュース：" + source + p.HASHTAGS
        events = []
        def save_state(state):
            events.append(("save", copy.deepcopy(state)))
        def send_message(*args, **kwargs):
            self.assertIn("valid", events[0][1]["pending_posts"])
            events.append(("send", None))
            return {"id": "mock-only", "status": "sent"}
        with patch.object(p, "save", side_effect=save_state), patch.object(p, "send", side_effect=send_message):
            self.assertTrue(p.publish(history, "valid", message, "news", source=source))
        self.assertEqual([e[0] for e in events], ["save", "send", "save"])

    def test_safe_limit_exact_boundary(self):
        for length, expected in [(270, True), (271, False)]:
            with self.subTest(length=length):
                with patch.object(p, "save"), patch.object(p, "send", return_value={"id": "mock", "status": "sent"}) as send:
                    self.assertEqual(p.publish(self.history(), "boundary", "a" * length, "vote"), expected)
                    self.assertEqual(send.call_count, int(expected))

    def test_unknown_send_stays_pending_and_cannot_resend(self):
        history = self.history()
        with patch.object(p, "save"), patch.object(p, "send", side_effect=TimeoutError) as send:
            with self.assertRaises(TimeoutError):
                p.publish(history, "unknown", "確認済みの本文", "vote")
            self.assertFalse(p.publish(history, "unknown", "確認済みの本文", "vote"))
        send.assert_called_once()
        self.assertIn("unknown", history["pending_posts"])
        self.assertEqual(history["publication_log"], [])

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

    def test_sourced_promotion_is_advisory_only(self):
        history = self.history()
        with patch.object(p, "save"), patch.object(p, "send",
                          return_value={"id": "mock-promotion", "status": "sent"}) as send:
            result = p.publish(history, "test_sourced_promotion", "公式スポンサー発表", "news",
                               source="https://stvv.jp/news/sponsor/20261030_1/")
        self.assertTrue(result)
        send.assert_called_once()
        self.assertIn("test_sourced_promotion", history["used_posts"])

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
