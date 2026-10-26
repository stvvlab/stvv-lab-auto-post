import json
import tempfile
import unittest
from pathlib import Path
from non_adobe_trial import check_manifest

class NonAdobeTrialTests(unittest.TestCase):
    def test_only_ready_reviewed_cards_pass(self):
        good = {"status": "ready", "reviewed": True, "source_url": "https://stvv.jp/news/test/",
                "text": "sample", "asset_path": "generated/sample.png", "sha256": "abc",
                "dimensions": [100, 100], "slots": ["news"], "date_jst": "2026-10-27"}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cards.json"
            p.write_text(json.dumps({"enabled": True, "cards": [good, dict(good, reviewed=False), dict(good, status="published")]}))
            r = check_manifest(p)
            self.assertEqual(len(r["ready_metadata_candidates"]), 1)
            self.assertEqual(len(r["blocked"]), 1)
            self.assertFalse(r["adobe_api_used"])
            self.assertFalse(r["x_publication_performed"])
    def test_disabled_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cards.json"
            p.write_text('{"enabled": false, "cards": []}')
            with self.assertRaises(ValueError):
                check_manifest(p)

if __name__ == "__main__":
    unittest.main()
