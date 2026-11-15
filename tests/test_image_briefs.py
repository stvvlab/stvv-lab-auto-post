import unittest
from editorial.image_briefs import build_image_briefs


class ImageBriefTests(unittest.TestCase):
    def item(self, **changes):
        x = {"source_url": "https://stvv.jp/news/1", "official_heading": "Official",
             "date_jst": "2026-11-15", "caption": "Verified draft",
             "source_body_sha256": "a" * 64, "approval_status": "not_approved",
             "ready_for_buffer": False, "image_status": "not_generated"}
        x.update(changes)
        return x

    def test_read_only_handoff(self):
        result = build_image_briefs({"previews": [self.item()]})
        self.assertEqual(len(result["briefs"]), 1)
        self.assertIsNone(result["briefs"][0]["image_path"])
        self.assertFalse(result["image_generation_performed"])
        self.assertFalse(result["briefs"][0]["ready_for_buffer"])

    def test_duplicates_and_approved_or_external_sources_skipped(self):
        result = build_image_briefs({"previews": [
            self.item(), self.item(), self.item(source_url="https://example.com/a"),
            self.item(source_url="https://stvv.jp/news/2", approval_status="approved"),
            self.item(source_url="https://stvv.jp/news/3", ready_for_buffer=True)]})
        self.assertEqual(len(result["briefs"]), 1)

    def test_invalid_input_rejected(self):
        for value in (None, [], {"previews": {}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_image_briefs(value)


if __name__ == "__main__":
    unittest.main()
