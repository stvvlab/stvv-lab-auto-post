"""Read-only review bundle integration tests."""
import unittest
from editorial.review_bundle import prepare_review_bundle


def candidate(url="https://stvv.jp/news/valid", **updates):
    item = {
        "status": "draft_needs_review",
        "approved": False,
        "source_url": url,
        "official_heading": "Official update",
        "date_jst": "2026-11-15",
        "caption": "Official STVV update.",
        "source_body_sha256": "a" * 64,
    }
    item.update(updates)
    return item


class ReviewBundleTests(unittest.TestCase):
    def test_matching_preview_and_brief_and_no_side_effects(self):
        bundle = prepare_review_bundle({"items": [candidate()]})
        self.assertEqual(bundle["status"], "review_required")
        self.assertEqual(len(bundle["items"]), 1)
        item = bundle["items"][0]
        self.assertEqual(item["preview"]["source_url"], item["image_brief"]["source_url"])
        self.assertEqual(item["preview"]["caption"], item["image_brief"]["caption"])
        self.assertEqual(item["image_brief"]["approval_status"], "not_approved")
        self.assertIsNone(item["image_brief"]["image_path"])
        for key in ("chat_delivery_performed", "image_generation_performed",
                    "approval_performed", "buffer_sent", "x_published"):
            self.assertIs(bundle[key], False)

    def test_duplicate_and_invalid_skipped_without_blocking_next(self):
        bundle = prepare_review_bundle({"items": [
            candidate("https://stvv.jp/news/bad", date_jst="2026-02-30"),
            candidate("https://stvv.jp/news/good"),
            candidate("https://stvv.jp/news/good"),
            candidate("https://stvv.jp/news/approved", approved=True),
        ]})
        self.assertEqual(len(bundle["items"]), 1)
        self.assertEqual(bundle["items"][0]["preview"]["source_url"],
                         "https://stvv.jp/news/good")

    def test_empty_candidates(self):
        bundle = prepare_review_bundle({"items": []})
        self.assertEqual(bundle["status"], "no_preview_ready")
        self.assertEqual(bundle["items"], [])


if __name__ == "__main__":
    unittest.main()
