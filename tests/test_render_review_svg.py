"""Regression tests for offline review-only SVG image creation."""
import tempfile
import unittest
from pathlib import Path
from editorial.render_review_svg import render_bundle, render_svg


def item(title="Official update", digest="a"*64):
    p = {"source_url":"https://stvv.jp/news/example","official_heading":title,"date_jst":"2026-11-15","caption":"Official update","source_body_sha256":digest,"approval_status":"not_approved","ready_for_buffer":False,"image_status":"not_generated"}
    b = {**p, "image_status":"brief_only","image_path":None}
    return {"preview":p,"image_brief":b}


class RenderReviewSvgTests(unittest.TestCase):
    def test_creates_unapproved_svg_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle({"status":"review_required","items":[item("Official & <Update>")]}, tmp)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            svg = Path(result["images"][0]["path"]).read_text()
            self.assertIn("Official &amp; &lt;Update&gt;", svg)
            self.assertIn("REVIEW ONLY", svg)
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])

    def test_invalid_item_skipped_next_continues(self):
        bad = item("Bad")
        bad["image_brief"]["source_url"] = "https://stvv.jp/news/other"
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle({"status":"review_required","items":[bad,item("Good","b"*64)]}, tmp)
            self.assertEqual([x["status"] for x in result["images"]], ["skipped","rendered_unapproved"])

    def test_duplicate_digest_different_urls_does_not_overwrite(self):
        first = item("First", "d"*64)
        second = item("Second", "d"*64)
        second["preview"]["source_url"] = "https://stvv.jp/news/second"
        second["image_brief"]["source_url"] = "https://stvv.jp/news/second"
        with tempfile.TemporaryDirectory() as tmp:
            result = render_bundle({"status": "review_required", "items": [first, second]}, tmp)
            self.assertEqual([r["status"] for r in result["images"]], ["rendered_unapproved", "skipped"])
            self.assertIn("First", next(Path(tmp).glob("*.svg")).read_text())
            self.assertNotIn("Second", next(Path(tmp).glob("*.svg")).read_text())

    def test_xml_forbidden_control_characters_are_removed(self):
        import xml.etree.ElementTree as ET
        svg = render_svg(item("Official\\x00 & <Update>"))
        ET.fromstring(svg)
        self.assertNotIn("\\x00", svg)
        self.assertIn("Official &amp; &lt;Update&gt;", svg)

    def test_existing_svg_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ("review-" + "a"*64 + ".svg")
            path.write_text("existing approved asset", encoding="utf-8")
            result = render_bundle({"status": "review_required", "items": [item()]}, tmp)
            self.assertEqual(result["images"][0]["status"], "skipped")
            self.assertEqual(path.read_text(encoding="utf-8"), "existing approved asset")

    def test_no_approved_image_or_clipped_headline(self):
        approved = item()
        approved["preview"]["approval_status"] = "approved"
        with self.assertRaises(ValueError):
            render_svg(approved)
        with self.assertRaises(ValueError):
            render_svg(item("x"*65))


if __name__ == "__main__":
    unittest.main()
