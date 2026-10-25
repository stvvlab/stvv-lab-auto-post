"""Tests for the non-blocking STVV LAB quality audit."""
import unittest
from quality_gate import audit, can_publish


class QualityGateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
