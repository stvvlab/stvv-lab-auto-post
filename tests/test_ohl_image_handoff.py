"""Regression checks for the exact user-approved image upload handoff."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_ohl_image import ASSET, EXPECTED_SHA256, EXPECTED_SIZE, verify_asset


class ImageHandoffTests(unittest.TestCase):
    def test_expected_identity_is_pinned(self):
        self.assertEqual(ASSET.as_posix(), 'generated/ohl_match_announcement_20261102.png')
        self.assertEqual(EXPECTED_SHA256, '81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5')
        self.assertEqual(EXPECTED_SIZE, (1448, 1086))

    def test_missing_asset_is_never_approved(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'missing'):
                verify_asset(td)

    def test_wrong_or_recompressed_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ASSET
            path.parent.mkdir()
            path.write_bytes(b'not the approved image')
            with self.assertRaisesRegex(ValueError, 'Wrong image bytes'):
                verify_asset(td)


if __name__ == '__main__':
    unittest.main()
