import unittest

from editorial.chat_preview import build_preview


class ChatPreviewTests(unittest.TestCase):
    def item(self, **overrides):
        item = {
            "source_url": "https://stvv.jp/news/123",
            "official_heading": "Official update",
            "date_jst": "2026-11-14",
            "caption": "Official source-based draft",
            "source_body_sha256": "a" * 64,
            "status": "draft_needs_review",
            "approved": False,
        }
        item.update(overrides)
        return item

    def test_valid_draft_stays_unapproved(self):
        result = build_preview({"items": [self.item()]})
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(len(result["previews"]), 1)
        self.assertFalse(result["previews"][0]["ready_for_buffer"])
        self.assertFalse(result["approval_performed"])
        self.assertFalse(result["chat_delivery_performed"])

    def test_duplicates_and_bad_records_are_skipped(self):
        result = build_preview({"items": [
            self.item(), self.item(), self.item(approved=True),
            self.item(source_body_sha256="invalid"),
            self.item(source_url="https://example.com/news/1"),
            self.item(caption=""),
        ]})
        self.assertEqual(len(result["previews"]), 1)

    def test_invalid_inventory_rejected(self):
        with self.assertRaises(ValueError):
            build_preview({"items": {}})


if __name__ == "__main__":
    unittest.main()
