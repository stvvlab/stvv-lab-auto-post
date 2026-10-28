import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import ImageFont
import simple_image_previews as previews


class PreviewTests(unittest.TestCase):
    def test_all_palettes_and_layouts_have_valid_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(previews, "font", side_effect=lambda size: ImageFont.load_default(size=size)):
                for idx, palette in enumerate(previews.PALETTES):
                    for layout in ("editorial", "centered", "sideband"):
                        output = Path(directory) / f"{idx}-{layout}.png"
                        previews.render_card("公式発表：試合日程", output, palette, layout)
                        from PIL import Image
                        with Image.open(output) as image:
                            self.assertEqual(image.size, (1448, 1086))

    def test_invalid_style_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                previews.render_card("test", Path(directory) / "test.png", layout="invalid")

    def test_drafts_are_never_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            result = previews.build_previews({"drafts": []}, directory)
            self.assertEqual(result["images_approved"], 0)
            self.assertFalse(result["publication_performed"])


if __name__ == "__main__":
    unittest.main()
