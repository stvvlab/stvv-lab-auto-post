"""End-to-end offline review handoff: candidate -> bundle -> SVG.

No network, approvals, Buffer scheduling, or X publishing.
"""
import tempfile
import unittest
from pathlib import Path

from editorial.review_bundle import prepare_review_bundle
from editorial.render_review_svg import render_bundle


def candidate(url, digest, **changes):
    value = {
        "status": "draft_needs_review",
        "approved": False,
        "source_url": url,
        "official_heading": "Official STVV update",
        "date_jst": "2026-11-15",
        "caption": "STVV official update for review.",
        "source_body_sha256": digest,
    }
    value.update(changes)
    return value


class ReviewSvgEndToEndTests(unittest.TestCase):
    def test_handoff_to_real_svg_without_publishing(self):
        handoff = {"items": [
            candidate("https://stvv.jp/news/invalid", "a"*64, date_jst="2026-02-30"),
            candidate("https://stvv.jp/news/valid", "b"*64),
            candidate("https://stvv.jp/news/valid", "b"*64),
            candidate("https://stvv.jp/news/approved", "c"*64, approved=True),
        ]}
        bundle = prepare_review_bundle(handoff)
        self.assertEqual(bundle["status"], "review_required")
        self.assertEqual(len(bundle["items"]), 1)
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle(bundle, tmp)
            self.assertEqual(len(result["images"]), 1)
            record = result["images"][0]
            self.assertEqual(record["status"], "rendered_unapproved")
            self.assertEqual(record["source_url"], "https://stvv.jp/news/valid")
            svg = Path(record["path"]).read_text(encoding="utf-8")
            self.assertIn('width="1200" height="675"', svg)
            self.assertIn("Official STVV update", svg)
            self.assertIn("REVIEW ONLY", svg)
            self.assertEqual(list(Path(tmp).glob("*.svg")), [Path(record["path"])])
        for key in ("approval_performed", "buffer_sent", "x_published"):
            self.assertIs(result[key], False)
        for key in ("chat_delivery_performed", "approval_performed",
                    "buffer_sent", "x_published"):
            self.assertIs(bundle[key], False)

    def test_same_url_distinct_phases_can_render(self):
        def item(digest, phase):
            fields = {
                "source_url": "https://stvv.jp/news/game/example",
                "official_heading": "STVV match update",
                "date_jst": "2026-11-17",
                "caption": "STVV match update",
                "source_body_sha256": digest,
                "approval_status": "not_approved",
                "ready_for_buffer": False,
                "editorial_purpose": {"phase": phase},
            }
            return {
                "preview": {**fields, "image_status": "not_generated"},
                "image_brief": {**fields, "image_status": "brief_only", "image_path": None},
            }
        bundle = {"status": "review_required", "items": [
            item("a" * 64, "preview"),
            item("b" * 64, "result"),
            item("c" * 64, "result"),
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle(bundle, tmp)
            self.assertEqual([i["status"] for i in result["images"]],
                             ["rendered_unapproved", "rendered_unapproved", "skipped"])
            self.assertEqual(len(list(Path(tmp).glob("*.svg"))), 2)
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])

    def test_no_candidates_does_not_create_images(self):
        bundle = prepare_review_bundle({"items": []})
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle(bundle, tmp)
            self.assertEqual(result["images"], [])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
