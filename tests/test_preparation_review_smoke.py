"""Regression: confirmed external X publications must not enter image review."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from editorial.preparation_review_smoke import run_preparation


class PreparationReviewSmokeTests(unittest.TestCase):
    def test_confirmed_x_post_skipped_next_candidate_rendered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = "Verified official body"
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            def candidate(url):
                return {"source_url": url, "status": "needs_editorial_review",
                        "source_body": body, "body_sha256": digest,
                        "date_jst": "2026-11-15", "official_heading": "Official news"}
            prep = root / "preparation.json"
            prep.write_text(json.dumps({"candidates": [
                candidate("https://stvv.jp/news/posted/"),
                candidate("https://stvv.jp/news/new/")
            ], "unapproved_draft_suggestions": [{
                "source_url": "https://stvv.jp/news/new/",
                "status": "draft_unapproved", "source_body_sha256": digest,
                "text": "Official news from STVV."
            }]}), encoding="utf-8")
            external = root / "external.json"
            external.write_text(json.dumps({"items": [{
                "source_url": "https://stvv.jp/news/posted/",
                "status": "confirmed_external_publication"
            }]}), encoding="utf-8")
            result = run_preparation(prep, external, root / "output")
            self.assertEqual(result["confirmed_external_skipped"], 1)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])


if __name__ == "__main__":
    unittest.main()
