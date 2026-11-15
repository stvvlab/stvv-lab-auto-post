import hashlib
import unittest

from editorial_handoff import build_handoff


def candidate(body, digest=None):
    return {
        "status": "needs_editorial_review",
        "source_url": "https://stvv.jp/news/game/20261109_1/",
        "source_body": body,
        "body_sha256": digest or hashlib.sha256(body.encode()).hexdigest(),
    }


class HandoffFallbackTests(unittest.TestCase):
    def test_verified_candidate_without_precomputed_draft(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        report = build_handoff({"candidates": [candidate(body)],
                                "unapproved_draft_suggestions": [], "skipped": []})
        self.assertEqual(report["items"][0]["status"], "draft_needs_review")
        self.assertIn("4-1", report["items"][0]["caption"])
        self.assertFalse(report["items"][0]["approved"])
        self.assertFalse(report["publication_performed"])

    def test_mismatched_body_never_generates_draft(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        report = build_handoff({"candidates": [candidate(body, "invalid")],
                                "unapproved_draft_suggestions": [], "skipped": []})
        self.assertEqual(report["items"], [])
        self.assertEqual(report["status"], "no_verified_candidates")

    def test_cached_draft_cannot_bypass_body_integrity(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\\n結果：4-1"
        item = candidate(body, "invalid")
        report = build_handoff({
            "candidates": [item],
            "unapproved_draft_suggestions": [{
                "source_url": item["source_url"],
                "source_body_sha256": "invalid",
                "status": "draft_unapproved",
                "text": "STALE CAPTION",
            }],
            "skipped": [],
        })
        self.assertEqual(report["items"], [])

    def test_blank_cached_draft_falls_back_to_verified_source(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\\n結果：4-1"
        item = candidate(body)
        report = build_handoff({
            "candidates": [item],
            "unapproved_draft_suggestions": [{
                "source_url": item["source_url"],
                "source_body_sha256": item["body_sha256"],
                "status": "draft_unapproved",
                "text": "",
            }],
            "skipped": [],
        })
        self.assertEqual(report["items"][0]["status"], "draft_needs_review")
        self.assertIn("4-1", report["items"][0]["caption"])

    def test_duplicate_url_produces_one_review_item(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\\n結果：4-1"
        item = candidate(body)
        report = build_handoff({
            "candidates": [item, dict(item)],
            "unapproved_draft_suggestions": [],
            "skipped": [],
        })
        self.assertEqual(len(report["items"]), 1)
        self.assertFalse(report["items"][0]["approved"])


    def test_previously_skipped_url_is_not_requeued(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        item = candidate(body)
        report = build_handoff({"candidates": [item], "skipped": [
            {"source_url": item["source_url"], "reason": "already_published"}]})
        self.assertEqual(report["items"], [])
        self.assertFalse(report["publication_performed"])

    def test_malformed_skipped_inventory_does_not_stop_handoff(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\\n結果：4-1"
        report = build_handoff({"candidates": [candidate(body)], "skipped": None})
        self.assertEqual(len(report["items"]), 1)
        self.assertEqual(report["skipped_count"], 0)
        self.assertFalse(report["publication_performed"])

    def test_malformed_candidate_is_skipped_without_blocking_valid_candidate(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        valid = candidate(body)
        report = build_handoff({
            "candidates": [None, "invalid", {"status": "unknown"}, valid],
            "unapproved_draft_suggestions": [None, "invalid"],
            "skipped": [],
        })
        self.assertEqual(len(report["items"]), 1)
        self.assertEqual(report["items"][0]["source_url"], valid["source_url"])
        self.assertFalse(report["items"][0]["approved"])

if __name__ == "__main__":
    unittest.main()
