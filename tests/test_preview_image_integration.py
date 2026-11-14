"""Read-only integration tests for draft -> chat preview -> image brief."""
import unittest
from editorial.chat_preview import build_preview
from editorial.image_briefs import build_image_briefs


class PreviewImageIntegrationTests(unittest.TestCase):
    def candidate(self, url="https://stvv.jp/news/example", **changes):
        item = {
            "status": "draft_needs_review",
            "approved": False,
            "source_url": url,
            "official_heading": "Official club update",
            "date_jst": "2026-11-15",
            "caption": "Club update from the official source.",
            "source_body_sha256": "a" * 64,
        }
        item.update(changes)
        return item

    def test_draft_to_image_brief_preserves_provenance_and_unapproved_state(self):
        preview = build_preview({"items": [self.candidate()]})
        result = build_image_briefs(preview)
        self.assertEqual(len(result["briefs"]), 1)
        brief = result["briefs"][0]
        for key in ("source_url", "official_heading", "date_jst", "caption", "source_body_sha256"):
            self.assertEqual(brief[key], preview["previews"][0][key])
        self.assertEqual(brief["approval_status"], "not_approved")
        self.assertFalse(brief["ready_for_buffer"])
        self.assertIsNone(brief["image_path"])
        self.assertFalse(result["image_generation_performed"])
        self.assertFalse(result["buffer_sent"])
        self.assertFalse(result["x_published"])

    def test_duplicate_or_approved_candidate_cannot_produce_second_brief(self):
        preview = build_preview({"items": [
            self.candidate(),
            self.candidate(),
            self.candidate("https://stvv.jp/news/approved", approved=True),
        ]})
        self.assertEqual(len(preview["previews"]), 1)
        self.assertEqual(len(build_image_briefs(preview)["briefs"]), 1)

    def test_invalid_candidate_does_not_block_next_valid_candidate(self):
        preview = build_preview({"items": [
            self.candidate("https://stvv.jp/news/bad", date_jst="2026-02-30"),
            self.candidate("https://stvv.jp/news/good"),
        ]})
        result = build_image_briefs(preview)
        self.assertEqual(len(result["briefs"]), 1)
        self.assertEqual(result["briefs"][0]["source_url"], "https://stvv.jp/news/good")


if __name__ == "__main__":
    unittest.main()
