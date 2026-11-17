"""Tests for the read-only delivery health summary."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "delivery_health_readonly.py"
spec = importlib.util.spec_from_file_location("delivery_health_readonly", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeliveryHealthTests(unittest.TestCase):
    def test_delayed_skipped_run_is_not_claimed_as_published(self):
        result = module.summarize(
            {"status": "skipped_no_verified_content", "start_delay_seconds": 21328,
             "new_publications": [], "new_reservations": [], "x_display_verified": False},
            {"status": "no_unposted_candidate_in_scanned_lists", "candidates": [], "ready_cards": 1},
        )
        self.assertTrue(result["schedule_delayed_over_hour"])
        self.assertEqual(result["new_publications"], 0)
        self.assertFalse(result["x_display_verified"])
        self.assertTrue(result["needs_editorial_preparation"])

    def test_sent_does_not_imply_x_verified(self):
        result = module.summarize(
            {"status": "sent", "new_publications": [{"buffer_status": "sent"}]},
            {"candidates": [{"source_url": "https://stvv.jp/news/team/example"}]},
        )
        self.assertFalse(result["x_display_verified"])
        self.assertFalse(result["schedule_delayed_over_hour"])
        self.assertFalse(result["needs_editorial_preparation"])


if __name__ == "__main__":
    unittest.main()
