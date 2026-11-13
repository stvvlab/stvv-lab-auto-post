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
        self.assertIsNone(report["items"][0]["caption"])
        self.assertEqual(report["items"][0]["status"], "caption_needed")


if __name__ == "__main__":
    unittest.main()
