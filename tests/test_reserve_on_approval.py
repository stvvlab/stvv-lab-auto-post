"""Offline tests for the new manifest-push reservation trigger."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import reserve_on_approval as trigger


class ApprovedCardTriggerTests(unittest.TestCase):
    def test_reject_non_main_or_non_push_or_missing_opt_in(self):
        good = {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "STVV_APPROVED_CARD_TRIGGER": "true",
            "STVV_ADVANCE_RESERVATIONS": "true",
        }
        trigger.assert_authorized_event(good)
        for key, wrong in [
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/feature"),
            ("STVV_APPROVED_CARD_TRIGGER", "false"),
            ("STVV_ADVANCE_RESERVATIONS", "false"),
        ]:
            with self.subTest(key=key, wrong=wrong):
                with self.assertRaises(RuntimeError):
                    trigger.assert_authorized_event({**good, key: wrong})
        with self.assertRaises(RuntimeError):
            trigger.assert_authorized_event({})

    def test_no_ready_card_is_no_reservation_not_a_post(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(trigger, "ROOT", Path(temp)), \
                 patch.object(trigger, "assert_authorized_event"), \
                 patch.object(trigger.publisher, "load", return_value={}), \
                 patch.object(trigger.publisher, "save") as save, \
                 patch.object(trigger.advance_reservations, "run", return_value={
                     "status": "skipped_no_verified_content",
                     "updates": [], "new_reservations": []
                 }) as run:
                report = trigger.main()
            self.assertEqual(report["status"], "skipped_no_verified_content")
            self.assertEqual(report["new_reservations"], [])
            self.assertEqual(report["publications_performed"], 0)
            self.assertFalse(report["x_display_verified"])
            self.assertTrue((Path(temp) / "reports/reservation-trigger-latest.json").exists())
            self.assertEqual(run.call_count, 1)
            save.assert_not_called()

    def test_reservation_is_not_misreported_as_published(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(trigger, "ROOT", Path(temp)), \
                 patch.object(trigger, "assert_authorized_event"), \
                 patch.object(trigger.publisher, "load", return_value={}), \
                 patch.object(trigger.advance_reservations, "run", return_value={
                     "status": "reserved_in_buffer",
                     "updates": [],
                     "new_reservations": [{"key": "daily_test", "buffer_status": "scheduled"}]
                 }):
                report = trigger.main()
            self.assertEqual(len(report["new_reservations"]), 1)
            self.assertEqual(report["publications_performed"], 0)
            self.assertFalse(report["x_display_verified"])

    def test_unknown_failure_records_class_and_never_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(trigger, "ROOT", Path(temp)), \
                 patch.object(trigger, "assert_authorized_event"), \
                 patch.object(trigger.publisher, "load", return_value={}), \
                 patch.object(trigger.advance_reservations, "run",
                              side_effect=TimeoutError("private response")) as run:
                with self.assertRaises(TimeoutError):
                    trigger.main()
            import json
            record = json.loads((Path(temp) / "reports/reservation-trigger-latest.json").read_text())
            self.assertEqual(record["status"], "execution_failed_do_not_retry")
            self.assertEqual(record["error_type"], "TimeoutError")
            self.assertNotIn("private response", str(record))
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
