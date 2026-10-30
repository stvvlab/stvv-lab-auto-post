"""Tests for isolated publish preflight; no network or publishing."""
import io
import json
import unittest
from unittest.mock import patch
import preflight_post


class PreflightTests(unittest.TestCase):
    def run_post(self, value):
        inp = io.StringIO(value)
        out = io.StringIO()
        with patch("sys.stdin", inp), patch("sys.stdout", out):
            status = preflight_post.main()
        return status, json.loads(out.getvalue())

    def test_valid_post(self):
        status, result = self.run_post(json.dumps({
            "type": "news", "text": "試合速報",
            "source_url": "https://example.com/match"}))
        self.assertEqual(status, 0)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["warnings"], [])

    def test_missing_source(self):
        status, result = self.run_post('{"type":"news","text":"試合速報"}')
        self.assertEqual(status, 1)
        self.assertIn("missing_source_reference", result["blocking"])
        self.assertEqual(result["decision"], "block")

    def test_sourced_promotion_is_warning_only(self):
        status, result = self.run_post(json.dumps({
            "type": "news", "text": "公式スポンサー発表",
            "source_url": "https://stvv.jp/news/sponsor/20261030_1/"}))
        self.assertEqual(status, 0)
        self.assertIn("excluded_promotion", result["warnings"])
        self.assertEqual(result["blocking"], [])
        self.assertEqual(result["decision"], "pass_with_warnings")

    def test_invalid_json(self):
        status, result = self.run_post("{bad")
        self.assertEqual(status, 1)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "block")

    def test_array_input(self):
        status, result = self.run_post('[]')
        self.assertEqual(status, 1)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "block")

    def test_warning_does_not_block(self):
        status, result = self.run_post('{"type":"vote","text":"ここが重要"}')
        self.assertEqual(status, 0)
        self.assertIn("generic_language_review", result["warnings"])
        self.assertEqual(result["decision"], "pass_with_warnings")

    def test_block_takes_precedence_over_warning(self):
        status, result = self.run_post('{"type":"news","text":"ここが重要"}')
        self.assertEqual(status, 1)
        self.assertIn("generic_language_review", result["warnings"])
        self.assertIn("missing_source_reference", result["blocking"])
        self.assertEqual(result["decision"], "block")


if __name__ == "__main__":
    unittest.main()
