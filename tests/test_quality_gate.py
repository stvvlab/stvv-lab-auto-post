"""Quality rules: critical findings block publication; warnings remain advisory."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import quality_gate
from quality_gate import audit, can_publish


class QualityGateTests(unittest.TestCase):
    def test_three_level_decisions(self):
        cases = [
            ({"type": "news", "text": "STVV公式の次戦案内",
              "source_url": "https://stvv.jp/news/game/20261030_1/"},
             "pass", [], []),
            ({"type": "vote", "text": "このプレーが重要"},
             "pass_with_warning", [], ["generic_language_review"]),
            ({"type": "news", "text": "短い公式告知"},
             "block", ["missing_source_reference"], []),
            ({"type": "news", "text": "公式発表が重要"},
             "block", ["missing_source_reference"], ["generic_language_review"]),
        ]
        for post, status, blocking, warnings in cases:
            with self.subTest(status=status, post=post):
                decision = quality_gate.classify(post)
                self.assertEqual(status, decision["status"])
                self.assertEqual(blocking, decision["blocking"])
                self.assertEqual(warnings, decision["warnings"])
                self.assertEqual(status != "block", can_publish(post))

    def test_three_level_decision_cli_prints_clean_and_warning(self):
        posts = [{"type": "vote", "text": "短い告知"},
                 {"type": "vote", "text": "このプレーが重要"},
                 {"type": "news", "text": "出典なし"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts.json"
            path.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["quality_gate.py", "--posts", str(path)]), redirect_stdout(output):
                quality_gate.main()
            self.assertIn("POST 0: 通過", output.getvalue())
            self.assertIn("POST 1: 警告のみで通過", output.getvalue())
            self.assertIn("POST 2: 停止", output.getvalue())

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

    def test_promotion_requires_source_but_wording_is_warning_only(self):
        self.assertFalse(can_publish({"type": "vote", "text": "スポンサー発表"}))
        sourced = {"type": "news", "text": "公式スポンサー発表",
                   "source_url": "https://stvv.jp/news/sponsor/20261030_1/"}
        self.assertTrue(can_publish(sourced))
        self.assertIn("excluded_promotion", audit(sourced))
        self.assertNotIn("missing_source_reference", audit(sourced))

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

    def test_strict_cli_blocks_critical_but_not_style_warnings(self):
        cases = [
            ("stylistic warning", {"type": "vote", "text": "ここが重要"}, ["--strict"], False),
            ("critical issue", {"type": "vote", "text": "スポンサー発表"}, ["--strict"], True),
            ("sourced promotion warning", {"type": "news", "text": "スポンサー発表",
             "source_url": "https://stvv.jp/news/sponsor/20261030_1/"}, ["--strict"], False),
            ("explicit all findings", {"type": "vote", "text": "ここが重要"}, ["--strict-all"], True),
            ("critical only alias", {"type": "vote", "text": "ここが重要"}, ["--enforce-critical"], False),
        ]
        for name, post, flags, should_fail in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "posts.json"
                path.write_text(json.dumps([post], ensure_ascii=False), encoding="utf-8")
                argv = ["quality_gate.py", "--posts", str(path), *flags]
                with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                    if should_fail:
                        with self.assertRaises(SystemExit) as raised:
                            quality_gate.main()
                        self.assertEqual(raised.exception.code, 1)
                    else:
                        quality_gate.main()



if __name__ == "__main__":
    unittest.main()
