"""Fail-closed regression for the exact, previously reviewed OH Leuven PNG handoff.

This test does not approve a draft or trigger a publication.  It becomes a
mandatory byte-for-byte check if the staged card is ever promoted to ready.
"""
import hashlib
import json
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://stvv.com/nl/nieuws/artikel/de-week-van-de-waarheid"
ASSET = "generated/ohl_match_announcement_20261102.png"
EXPECTED_SHA256 = "81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5"
EXPECTED_SIZE = 2786361
EXPECTED_DIMENSIONS = [1448, 1086]
EXPECTED_BODY_SHA256 = "47da9e748099f4fa18f3ee9097257f590fb5bf55058fcfd3423ae45f533a04c4"


class OhlExactAssetHandoffTests(unittest.TestCase):
    def test_draft_never_masquerades_as_ready(self):
        manifest = json.loads((ROOT / "editorial/imagegen_cards.json").read_text(encoding="utf-8"))
        cards = [c for c in manifest["cards"] if c.get("source_url") == SOURCE]
        self.assertLessEqual(len(cards), 1, "Ambiguous OH Leuven card")
        if not cards:
            self.skipTest("OH Leuven card has not been staged on this branch")
        card = cards[0]
        self.assertEqual(card.get("asset_path"), ASSET)
        self.assertEqual(card.get("sha256"), EXPECTED_SHA256)
        self.assertEqual(card.get("dimensions"), EXPECTED_DIMENSIONS)
        self.assertEqual(card.get("source_body_sha256"), EXPECTED_BODY_SHA256)
        self.assertEqual(card.get("date_jst"), "2026-10-27")
        self.assertEqual(card.get("expires_at_jst"), "2026-11-02T00:00:00+09:00")
        self.assertIn("7日間でホーム3連戦", card.get("text", ""))
        self.assertIn("OHルーヴェン", card.get("text", ""))
        self.assertIn(SOURCE, card.get("text", ""))
        self.assertNotIn("Japan Day", card.get("text", ""))

        path = ROOT / ASSET
        if card.get("status") not in {"ready", "published"}:
            self.assertIs(card.get("reviewed"), False,
                          "Non-ready OH Leuven card must not be reviewed")
            self.assertEqual(card.get("status"), "awaiting_exact_image_bytes")
            # A staged upload may precede the separate editorial approval.
            # The upload itself is never permission to publish.
            if not path.exists():
                return
        else:
            self.assertIs(card.get("reviewed"), True)
            self.assertTrue(path.is_file(), "Ready/published status without original PNG")

        self.assertTrue(path.is_file(), "Uploaded asset is not a regular file")
        self.assertFalse(path.is_symlink(), "Image symlink not allowed")
        raw = path.read_bytes()
        self.assertEqual(len(raw), EXPECTED_SIZE, "Original PNG size changed")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA256,
                         "Original reviewed image bytes changed")
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(list(image.size), EXPECTED_DIMENSIONS)
            image.verify()


if __name__ == "__main__":
    unittest.main()
