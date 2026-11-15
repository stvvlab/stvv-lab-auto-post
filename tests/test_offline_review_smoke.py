"""Offline smoke runner regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from editorial.offline_review_smoke import run


class OfflineReviewSmokeTests(unittest.TestCase):
    def test_explicit_handoff_creates_svg_and_bundle_without_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "handoff.json"
            handoff.write_text(json.dumps({"items": [{
                "status": "draft_needs_review", "approved": False,
                "source_url": "https://stvv.jp/news/example",
                "official_heading": "Official STVV update",
                "date_jst": "2026-11-15",
                "caption": "Official update.",
                "source_body_sha256": "a" * 64
            }]}), encoding="utf-8")
            result = run(handoff, root / "review")
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            self.assertTrue(Path(result["images"][0]["path"]).is_file())
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])
            with self.assertRaises(FileExistsError):
                run(handoff, root / "review")

    def test_empty_handoff_produces_no_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "empty.json"
            handoff.write_text('{"items":[]}', encoding="utf-8")
            result = run(handoff, root / "review")
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["images"], [])


if __name__ == "__main__":
    unittest.main()
