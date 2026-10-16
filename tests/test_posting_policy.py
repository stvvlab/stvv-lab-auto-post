"""Offline tests for safe fallback selection. No API calls or posting."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import stvv_post as p

class PostingPolicyTests(unittest.TestCase):
    def test_low_manual_rating_still_blocks_candidate(self):
        day = "2026-10-16"
        candidate = p.TOPICS["news"][0]
        selected = p.choose_fallback("news", day, {candidate: 1},
            {candidate: 5.0})
        self.assertNotEqual(selected, candidate)

    def test_no_automatic_feedback_keeps_existing_order(self):
        day = "2026-10-16"
        original = p.choose_fallback("compare", day, {})
        new = p.choose_fallback("compare", day, {}, {})
        self.assertEqual(original, new)

    def test_metric_ranking_applies_after_two_samples(self):
        high = p.TOPICS["analysis"][0]
        low = p.TOPICS["analysis"][1]
        with tempfile.TemporaryDirectory() as td:
            filepath = Path(td) / "feedback.json"
            filepath.write_text(json.dumps({
                "settings": {"feedback_enabled": True, "auto_improvement_enabled": True},
                "automatic_feedback": [
                    {"post_key": "a", "rating": 5}, {"post_key": "b", "rating": 4},
                    {"post_key": "c", "rating": 1},
                ]}), encoding="utf-8")
            history = {"publication_log": [
                {"key": "a", "text": high + p.HASHTAGS},
                {"key": "b", "text": high + p.HASHTAGS},
                {"key": "c", "text": low + p.HASHTAGS},
            ]}
            with patch.object(p, "FEEDBACK_FILE", filepath):
                ratings = p.auto_feedback_scores(history)
            self.assertEqual(ratings, {high: 4.5})
            chosen = p.choose_fallback("analysis", "2026-10-16", {}, ratings)
            self.assertEqual(chosen, high)

if __name__ == "__main__":
    unittest.main()
