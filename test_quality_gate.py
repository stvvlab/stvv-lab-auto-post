"""Tests for the non-blocking STVV LAB quality audit."""
import unittest
from quality_gate import audit, can_publish


class QualityGateTests(unittest.TestCase):
    def test_non_object_fails_closed(self):
        for value in [None, [], "text"]:
            self.assertFalse(can_publish(value))

    def test_japanese_uses_weighted_length(self):
        self.assertIn("over_280_characters", audit({"text": "あ" * 141}))

    def test_long_url_does_not_false_block(self):
        self.assertTrue(can_publish({"text": "公式：https://stvv.jp/news/" + "a" * 300}))

    def test_missing_text(self):
        self.assertIn("missing_text", audit({"text": ""}))

    def test_character_limit(self):
        self.assertIn("over_280_characters", audit({"text": "a" * 281}))

    def test_promotional_content(self):
        self.assertIn("excluded_promotion", audit({"text": "新スポンサーが決定"}))

    def test_generic_phrase(self):
        self.assertIn("generic_language_review", audit({"text": "分析が重要です"}))

    def test_missing_source(self):
        self.assertIn("missing_source_reference", audit({"type": "news", "text": "試合速報"}))

    def test_clean_with_source(self):
        post = {"type": "news", "text": "STVV 1-0 相手チーム",
                "source_url": "https://example.com/match/123"}
        self.assertEqual([], audit(post))

    def test_generic_warning_does_not_block(self):
        self.assertTrue(can_publish({"type": "vote", "text": "ここが重要"}))

    def test_excluded_promotion_blocks(self):
        self.assertFalse(can_publish({"type": "vote", "text": "スポンサー発表"}))

    def test_news_without_source_blocks(self):
        self.assertFalse(can_publish({"type": "news", "text": "試合速報"}))

    def test_sourced_news_allowed(self):
        self.assertTrue(can_publish({"type": "news", "text": "試合速報",
                                    "source_url": "https://example.com/news"}))

    def test_bad_url(self):
        post = {"type": "news", "text": "試合速報", "source_url": "not-a-url"}
        self.assertIn("malformed_source_url", audit(post))

    def test_url_requires_host_and_no_embedded_credentials(self):
        for source in ["https:///news", "https://user:password@stvv.jp/news/a", "https://[bad"]:
            self.assertFalse(can_publish({"type": "news", "text": "公式発表", "source_url": source}))


if __name__ == "__main__":
    unittest.main()
