import unittest
from editorial_handoff import build_handoff


class EditorialHandoffTests(unittest.TestCase):
    def test_duplicate_skipped_and_next_candidate_selected(self):
        inventory = {
            "skipped": [{"source_url": "https://stvv.jp/news/team/old/"}],
            "candidates": [
                {"source_url": "https://stvv.jp/news/event/new/",
                 "status": "needs_editorial_review", "source_body": "verified",
                 "body_sha256": "abc", "official_heading": "New event"},
                {"source_url": "https://stvv.jp/news/team/unavailable/",
                 "status": "source_unavailable"}],
            "unapproved_draft_suggestions": [
                {"source_url": "https://stvv.jp/news/event/new/",
                 "status": "draft_unapproved", "source_body_sha256": "abc",
                 "text": "Proposed caption"}]}
        result = build_handoff(inventory)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["items"][0]["caption"], "Proposed caption")
        self.assertFalse(result["items"][0]["approved"])
        self.assertFalse(result["publication_performed"])

    def test_stale_draft_cannot_be_handed_off(self):
        inventory = {
            "candidates": [{"source_url": "https://stvv.jp/news/team/new/",
                            "status": "needs_editorial_review",
                            "source_body": "verified", "body_sha256": "new"}],
            "unapproved_draft_suggestions": [
                {"source_url": "https://stvv.jp/news/team/new/",
                 "status": "draft_unapproved", "source_body_sha256": "old",
                 "text": "Stale caption"}]}
        result = build_handoff(inventory)
        self.assertIsNone(result["items"][0]["caption"])
        self.assertEqual(result["items"][0]["status"], "caption_needed")


if __name__ == "__main__":
    unittest.main()
