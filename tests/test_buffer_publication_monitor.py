"""Read-only publication-monitor regression tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.buffer_publication_monitor import classify, collect


class BufferPublicationMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-10-30T09:20:00+00:00")
        self.due = "2026-10-30T09:00:00Z"

    def test_overdue_never_counts_as_sent(self):
        self.assertEqual(classify("scheduled", self.due, self.now),
                         "overdue_not_sent_do_not_retry")

    def test_sent_is_not_x_verified(self):
        self.assertEqual(classify("sent", self.due, self.now),
                         "buffer_reports_sent_x_unverified")

    def test_draft_is_not_sent(self):
        self.assertEqual(classify("draft", self.due, self.now),
                         "moved_to_drafts_not_published")

    def test_early_due_waits(self):
        now = datetime.fromisoformat("2026-10-30T08:50:00+00:00")
        self.assertEqual(classify("scheduled", self.due, now),
                         "waiting_for_due")

    def test_unauthorized_identity_never_approved(self):
        class Client:
            def get_post(self, _):
                return {"id": "wrong", "channelId": "bad", "text": "unsafe",
                        "status": "sent"}
        history = {"reserved_posts": {"test": {"buffer_id": "expected",
                   "text": "approved", "due_at": self.due, "image_url": "https://example.org/a.png",
                   "dimensions": [1448, 1086]}}}
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            collect(history, Client(), self.now)


if __name__ == "__main__":
    unittest.main()
