import unittest
from recovery_triage import diagnose


class RecoveryTriageTests(unittest.TestCase):
    def test_missing_assets_and_skipped_delivery(self):
        data = diagnose({"cards": [{"status": "published", "reviewed": True}]},
                        {"status": "no_unposted_candidate_in_scanned_lists"},
                        {"status": "skipped_no_verified_content", "run_id": "123",
                         "start_delay_seconds": 2000, "new_reservations": []})
        self.assertEqual(data["ready_reviewed_cards"], 0)
        self.assertIn("approved_ready_assets_zero", data["problems"])
        self.assertIn("github_start_delayed_over_30_minutes", data["problems"])
        self.assertNotIn("scheduled_delivery_skipped", data["problems"])
        self.assertNotIn("image_verification_blocked", data["problems"])
        self.assertFalse(data["publishing_attempted"])

    def test_image_verification_skip_is_a_real_blocker(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "has_candidates"},
                        {"status": "skipped_image_verification", "run_id": "124"})
        self.assertIn("image_verification_blocked", data["problems"])
        self.assertEqual(data["status"], "needs_recovery")

    def test_safe_pending_assets_do_not_claim_x_published(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "has_candidates"},
                        {"status": "submitted_to_buffer", "new_publications": [{}]})
        self.assertIn("x_publication_not_verified", data["problems"])
        self.assertEqual(data["new_x_publications_verified"], 0)

    def test_failed_scheduled_step_is_detected_even_with_ready_content(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "candidates_need_review"},
                        {"status": "execution_failed", "delivery_state": "no_new_buffer_acceptance_recorded"})
        self.assertIn("scheduled_delivery_execution_failed", data["problems"])
        self.assertIn("failed scheduled job", data["next_fix"])
        self.assertEqual(data["new_x_publications_verified"], 0)

    def test_unknown_pending_without_publication_is_detected(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "candidates_need_review"},
                        {"status": "blocked_pending_outcome_unknown",
                         "pending_reservation_keys": ["reserve-123"],
                         "new_publications": []})
        self.assertIn("send_outcome_unknown_do_not_retry", data["problems"])
        self.assertIn("without resending", data["next_fix"])

    def test_explicit_buffer_rejection_and_reservation_error(self):
        rejected = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                            {"status": "candidates_need_review"},
                            {"status": "blocked_buffer_rejected",
                             "delivery_state": "buffer_rejected_not_published"})
        self.assertIn("buffer_explicitly_rejected", rejected["problems"])
        error = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                         {"status": "candidates_need_review"},
                         {"status": "blocked_reservation_error",
                          "reservation_states": [{"buffer_status": "error"}]})
        self.assertIn("buffer_reservation_error", error["problems"])

    def test_scheduled_buffer_reservation_is_not_an_x_publication(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "candidates_need_review"},
                        {"status": "reserved_in_buffer",
                         "delivery_state": "buffer_scheduled_not_published",
                         "new_reservations": [{"buffer_id": "one"}],
                         "reservation_states": [{"buffer_status": "scheduled"}],
                         "new_publications": []})
        self.assertEqual(data["new_buffer_reservations"], 1)
        self.assertEqual(data["new_x_publications_verified"], 0)
        self.assertNotIn("x_publication_not_verified", data["problems"])
        self.assertNotIn("buffer_reservation_error", data["problems"])

    def test_valid_state_does_not_create_issue(self):
        data = diagnose({"cards": [{"status": "ready", "reviewed": True}]},
                        {"status": "has_candidates"},
                        {"status": "submitted_to_buffer", "x_display_verified": True,
                         "new_publications": [{"x_display_verified": True}]})
        self.assertEqual(data["status"], "no_detected_blocker")
        self.assertEqual(data["new_x_publications_verified"], 1)


if __name__ == "__main__":
    unittest.main()
