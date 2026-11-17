import json
import tempfile
import unittest
from pathlib import Path
from editorial.review_queue import build_review_queue


class ReviewQueueTests(unittest.TestCase):
    def test_deduplicates_and_never_approves_or_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir()
            (root / "editorial").mkdir()
            fixtures = {
                "reports/preparation-latest.json": {"candidates": [
                    {"source_url": "https://stvv.jp/old", "official_heading": "old"},
                    {"source_url": " https://stvv.jp/new ", "official_heading": "new"},
                    {"source_url": "https://stvv.jp/new", "official_heading": "duplicate"},
                    {"source_url": "", "official_heading": "missing"},
                ]},
                "reports/delivery-latest.json": {},
                "editorial/imagegen_cards.json": {"cards": []},
                "posted.json": {"news": ["https://stvv.jp/old"]},
            }
            for name, value in fixtures.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            before = {name: (root / name).read_bytes() for name in fixtures}
            result = build_review_queue(root)
            self.assertEqual(len(result["queue"]), 1)
            self.assertEqual(result["queue"][0]["source_url"], "https://stvv.jp/new")
            self.assertFalse(result["queue"][0]["approved"])
            self.assertFalse(result["queue"][0]["publish_allowed"])
            self.assertFalse(result["posting_performed"])
            self.assertEqual(before, {name: (root / name).read_bytes() for name in fixtures})

    def test_empty_or_malformed_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_review_queue(Path(tmp))
            self.assertEqual(result["queue"], [])
            self.assertEqual(result["status"], "no_fresh_candidate")


if __name__ == "__main__":
    unittest.main()
