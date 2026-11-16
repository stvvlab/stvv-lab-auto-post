"""Regression for offline SVG status synchronization; never schedules posts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from editorial.offline_review_smoke import run


class OfflineReviewStatusTests(unittest.TestCase):
    def test_rendered_svg_updates_both_records_without_approval(self):
        digest = "a" * 64
        source = {
            "source_url": "https://stvv.jp/news/event/test/",
            "official_heading": "公式イベント情報",
            "date_jst": "2026-11-16",
            "caption": "公式イベント情報",
            "source_body_sha256": digest,
            "approval_status": "not_approved",
            "ready_for_buffer": False,
        }
        bundle = {
            "status": "review_required",
            "items": [{
                "preview": dict(source, image_status="not_generated"),
                "image_brief": dict(source, image_status="brief_only", image_path=None),
            }],
            "image_generation_performed": False,
            "chat_delivery_performed": False,
            "approval_performed": False,
            "buffer_sent": False,
            "x_published": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "handoff.json"
            handoff.write_text("{}", encoding="utf-8")
            with patch("editorial.offline_review_smoke.prepare_review_bundle", return_value=bundle):
                result = run(handoff, root / "output")
            saved = json.loads(Path(result["bundle_path"]).read_text(encoding="utf-8"))
            self.assertTrue(saved["image_generation_performed"])
            preview = saved["items"][0]["preview"]
            brief = saved["items"][0]["image_brief"]
            self.assertEqual(preview["image_status"], "generated_unapproved")
            self.assertEqual(brief["image_status"], "generated_unapproved")
            self.assertEqual(preview["image_path"], brief["image_path"])
            self.assertTrue(Path(preview["image_path"]).is_file())
            self.assertEqual(preview["approval_status"], "not_approved")
            self.assertFalse(preview["ready_for_buffer"])
            self.assertFalse(saved["chat_delivery_performed"])
            self.assertFalse(saved["buffer_sent"])
            self.assertFalse(saved["x_published"])


if __name__ == "__main__":
    unittest.main()
