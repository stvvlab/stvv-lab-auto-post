"""Font setup must reject missing-glyph fonts before preview rendering."""
import os
import unittest
from pathlib import Path
from PIL import ImageFont


class CardFontInstallTests(unittest.TestCase):
    def test_exported_font_renders_distinct_japanese_glyphs(self):
        path = os.getenv("STVV_CARD_FONT")
        if not path:
            self.skipTest("Font installer not invoked in this environment")
        self.assertTrue(Path(path).is_file())
        face = ImageFont.truetype(path, 32)
        first, second = face.getmask("試"), face.getmask("合")
        self.assertTrue(any(bytes(first)))
        self.assertTrue(first.size != second.size or bytes(first) != bytes(second))


if __name__ == "__main__":
    unittest.main()
