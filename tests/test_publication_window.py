"""Timing regression tests for minimal publication safety."""
import unittest
from datetime import datetime, timedelta, timezone

from publication_window import due_block_reason


JST = timezone(timedelta(hours=9))


class PublicationWindowTests(unittest.TestCase):
    def setUp(self):
        self.due = datetime(2026, 11, 10, 18, 0, tzinfo=JST)
        self.card = {"publish_due_jst": self.due.isoformat()}

    def test_exact_due_is_backward_compatible(self):
        self.assertIsNone(due_block_reason(self.card, self.due))
        self.assertEqual(due_block_reason(self.card, self.due + timedelta(seconds=1)),
                         "fixed_publish_due_missed")

    def test_reviewed_window_allows_delayed_execution(self):
        self.card.update(publish_window_end_jst=(self.due + timedelta(hours=4)).isoformat(),
                         publish_window_reviewed=True)
        self.assertIsNone(due_block_reason(self.card, self.due + timedelta(hours=3, minutes=16)))
        self.assertEqual(due_block_reason(self.card, self.due + timedelta(hours=5)),
                         "publish_window_expired")

    def test_never_open_window_without_explicit_review(self):
        self.card["publish_window_end_jst"] = (self.due + timedelta(hours=3)).isoformat()
        self.assertEqual(due_block_reason(self.card, self.due), "unreviewed_publish_window")

    def test_oversized_window_rejected(self):
        self.card.update(publish_window_end_jst=(self.due + timedelta(hours=7)).isoformat(),
                         publish_window_reviewed=True)
        self.assertEqual(due_block_reason(self.card, self.due), "invalid_publish_window")

    def test_malformed_or_naive_time_rejected(self):
        self.card["publish_due_jst"] = "2026-11-10T18:00:00"
        self.assertEqual(due_block_reason(self.card, self.due), "invalid_fixed_publish_due")
        self.card["publish_due_jst"] = "not a timestamp"
        self.assertEqual(due_block_reason(self.card, self.due), "invalid_publish_window")

    def test_existing_matchday_reminder_is_not_recycled(self):
        old = {"publish_due_jst": "2026-11-01T18:00:00+09:00"}
        self.assertEqual(
            due_block_reason(old, datetime(2026, 11, 9, 11, 16, tzinfo=JST)),
            "fixed_publish_due_missed")


if __name__ == "__main__":
    unittest.main()
