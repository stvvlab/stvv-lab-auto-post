import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from editorial.pipeline_progress import snapshot


class PipelineProgressTests(unittest.TestCase):
    def test_snapshot_is_read_only_and_does_not_claim_external_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir()
            (root / "editorial").mkdir()
            data = {
                "reports/preparation-latest.json": {
                    "status": "candidates_need_review",
                    "candidates": [{"status": "needs_editorial_review"}],
                    "image_generation_performed": False,
                },
                "reports/delivery-latest.json": {
                    "status": "blocked_schedule_more_than_six_hours_late",
                    "new_reservations": [],
                },
                "editorial/imagegen_cards.json": {
                    "cards": [
                        {"status": "ready", "reviewed": True},
                        {"status": "ready", "reviewed": False},
                    ]
                },
                "posted.json": {"publication_log": [{"source": "https://stvv.jp/example"}]},
            }
            for path, value in data.items():
                (root / path).write_text(json.dumps(value), encoding="utf-8")
            before = {p: (root / p).read_bytes() for p in data}
            result = snapshot(root, datetime(2026, 11, 14, 3, tzinfo=ZoneInfo("Asia/Tokyo")))
            self.assertEqual(result["counts"]["candidates"], 1)
            self.assertEqual(result["counts"]["approved_ready_cards"], 1)
            self.assertEqual(result["counts"]["new_reservations"], 0)
            self.assertFalse(result["remote_x_checked"])
            self.assertFalse(result["buffer_checked"])
            self.assertFalse(result["posting_performed"])
            self.assertEqual(before, {p: (root / p).read_bytes() for p in data})

    def test_legacy_news_and_publication_log_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir()
            (root / "editorial").mkdir()
            fixtures = {
                "reports/preparation-latest.json": {
                    "status": "candidates_need_review",
                    "candidates": [
                        {"source_url": "https://stvv.jp/legacy"},
                        {"source_url": "https://stvv.jp/sent"},
                        {"source_url": "https://stvv.jp/fresh"},
                    ],
                },
                "reports/delivery-latest.json": {"new_reservations": []},
                "editorial/imagegen_cards.json": {"cards": []},
                "posted.json": {
                    "news": ["https://stvv.jp/legacy"],
                    "publication_log": [{"source": "https://stvv.jp/sent"}],
                },
            }
            for path, value in fixtures.items():
                (root / path).write_text(json.dumps(value), encoding="utf-8")
            result = snapshot(root)
            self.assertEqual(result["counts"]["duplicate_source_candidates"], 2)
            self.assertEqual(result["counts"]["fresh_local_candidates"], 1)
            self.assertEqual(result["fresh_candidate_sources"], ["https://stvv.jp/fresh"])
            self.assertFalse(result["posting_performed"])

    def test_missing_files_do_not_produce_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = snapshot(Path(tmp))
            self.assertEqual(result["counts"]["approved_ready_cards"], 0)
            self.assertEqual(result["counts"]["new_reservations"], 0)
            self.assertEqual(result["stages"]["01_source_collection"], "unknown")
            self.assertFalse(result["remote_x_checked"])


if __name__ == "__main__":
    unittest.main()
