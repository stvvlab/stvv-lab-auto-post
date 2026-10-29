"""iPhone UUID filename is acceptable when original bytes are unchanged."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.normalize_ohl_upload import normalize
from scripts.verify_ohl_image import ASSET


class MobileImageUploadTests(unittest.TestCase):
    def test_uuid_filename_is_renamed_only_if_exact_bytes_match(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "generated" / "A0FA045B-D054-4C6B-B8BB-3F1AFC.png"
            src.parent.mkdir()
            Image.new("RGB", (1, 1), (10, 20, 30)).save(src, "PNG")
            digest = hashlib.sha256(src.read_bytes()).hexdigest()
            with patch("scripts.normalize_ohl_upload.EXPECTED_SHA256", digest), \
                 patch("scripts.verify_ohl_image.EXPECTED_SHA256", digest), \
                 patch("scripts.verify_ohl_image.EXPECTED_SIZE", (1, 1)):
                result = normalize(td)
                self.assertEqual(result["status"], "renamed_exact_original")
                self.assertFalse(src.exists())
                self.assertTrue((Path(td) / ASSET).exists())
                self.assertEqual(normalize(td)["status"], "already_canonical")
                self.assertFalse(result["publication_approved"])

    def test_mismatched_bytes_never_move(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "generated" / "A0FA045B.png"
            src.parent.mkdir()
            src.write_bytes(b"wrong image")
            with self.assertRaisesRegex(ValueError, "found 0"):
                normalize(td)
            self.assertTrue(src.exists())
            self.assertFalse((Path(td) / ASSET).exists())


if __name__ == "__main__":
    unittest.main()
