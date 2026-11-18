"""Regression: stale schedule is skipped, not published or failed."""
import os
import unittest
from datetime import datetime
from unittest.mock import patch

from stvv_post import JST, slot_for_run


class StaleScheduleTests(unittest.TestCase):
    def test_stale_schedule_skips(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_SCHEDULE": "0 9 * * *"}):
            slot, marker = slot_for_run(datetime(2026, 11, 19, 1, 5, tzinfo=JST))
        self.assertIsNone(slot)
        self.assertEqual(marker, "stale_schedule")

    def test_on_time_schedule_preserved(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_SCHEDULE": "0 9 * * *"}):
            slot, day = slot_for_run(datetime(2026, 11, 18, 18, 5, tzinfo=JST))
        self.assertEqual((slot, day), ("news", "2026-11-18"))

    def test_manual_still_read_only(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            self.assertEqual(slot_for_run(datetime(2026, 11, 18, 21, 5, tzinfo=JST)), (None, None))


if __name__ == "__main__":
    unittest.main()
