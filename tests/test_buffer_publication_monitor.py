"""Read-only publication-monitor regression tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.buffer_publication_monitor import classify, collect, needs_attention, x_permalink_candidate


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

    def test_scheduled_reservation_moved_to_drafts_requires_attention(self):
        row = {"delivery_state": "moved_to_drafts_not_published",
               "ledger_status": "scheduled"}
        self.assertTrue(needs_attention(row))
        row["ledger_status"] = "sending"
        self.assertTrue(needs_attention(row))

    def test_historical_cancelled_draft_is_not_a_new_failure(self):
        row = {"delivery_state": "moved_to_drafts_not_published",
               "ledger_status": "cancelled_by_user"}
        self.assertFalse(needs_attention(row))
        row["ledger_status"] = "draft_no_longer_scheduled"
        self.assertFalse(needs_attention(row))

    def test_sent_transport_not_flagged_as_error_or_x_verified(self):
        row = {"delivery_state": "buffer_reports_sent_x_unverified",
               "ledger_status": "scheduled"}
        self.assertFalse(needs_attention(row))

    def test_external_link_is_only_an_unverified_own_account_locator(self):
        good = {"externalLink": "https://twitter.com/stvvlabo/status/2114727647368331366"}
        self.assertEqual(x_permalink_candidate(good),
                         "https://x.com/stvvlabo/status/2114727647368331366")
        for value in [None, "", "https://x.com/other/status/2114727647368331366",
                      "https://evil.example/stvvlabo/status/2114727647368331366",
                      "https://x.com/stvvlabo/status/not-an-id",
                      "https://x.com/stvvlabo/status/2114727647368331366?redirect=1",
                      "http://x.com/stvvlabo/status/2114727647368331366",
                      "https://x.com:443/stvvlabo/status/2114727647368331366",
                      "https://x.com@evil.example/stvvlabo/status/2114727647368331366"]:
            with self.subTest(value=value):
                self.assertIsNone(x_permalink_candidate({"externalLink": value}))

    def test_sent_post_exposes_candidate_but_never_marks_x_verified(self):
        from unittest.mock import patch
        from stvv_post import CHANNEL
        from buffer_reservations import BufferReservations
        from advance_reservations import verify_echo
        from unittest.mock import Mock
        client = Mock(spec=BufferReservations)
        client.get_post.return_value = {
            "id": "buffer-fixture", "channelId": CHANNEL, "text": "approved",
            "dueAt": self.due, "status": "sent",
            "externalLink": "https://x.com/stvvlabo/status/2114727647368331366",
            "assets": [{"id": "asset-1"}],
        }
        history = {"reserved_posts": {"fixture": {
            "buffer_id": "buffer-fixture", "text": "approved",
            "due_at": self.due, "image_url": "https://example.org/a.png",
            "dimensions": [1448, 1086], "buffer_asset_ids": ["asset-1"],
        }}}
        rows = collect(history, client, self.now)
        self.assertEqual(rows[0]["x_permalink_candidate"],
                         "https://x.com/stvvlabo/status/2114727647368331366")
        self.assertFalse(rows[0]["x_display_verified"])
        self.assertEqual(rows[0]["delivery_state"], "buffer_reports_sent_x_unverified")
        self.assertNotIn("x_permalink_candidate", history["reserved_posts"]["fixture"])

    def test_read_only_get_post_requests_external_link(self):
        from buffer_reservations import BufferReservations
        from unittest.mock import Mock
        client = BufferReservations(Mock())
        client.query = Mock(return_value={"post": {"id": "some-post"}})
        self.assertEqual(client.get_post("some-post")["id"], "some-post")
        self.assertIn("externalLink", client.query.call_args.args[0])

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
