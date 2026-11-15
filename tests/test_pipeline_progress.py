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

    def test_missing_files_do_not_produce_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = snapshot(Path(tmp))
            self.assertEqual(result["counts"]["approved_ready_cards"], 0)
            self.assertEqual(result["counts"]["new_reservations"], 0)
            self.assertEqual(result["stages"]["01_source_collection"], "unknown")
            self.assertFalse(result["remote_x_checked"])


if __name__ == "__main__":
    unittest.main()
