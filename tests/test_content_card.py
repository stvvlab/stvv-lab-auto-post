"""Smoke-test all seven Japanese editorial layouts."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from content_card import LABELS, render_content_card

class ContentCardSmokeTests(unittest.TestCase):
    def test_all_layouts(self):
        sample = "⚽ STVV試合分析\n日本人選手の動きと守備の切り替えを確認。\nシュート数と枠内シュートを比較。"
        with tempfile.TemporaryDirectory() as tmp:
            for slot in LABELS:
                with self.subTest(slot=slot):
                    output = Path(tmp) / (slot + ".png")
                    render_content_card(slot, sample, output)
                    with Image.open(output) as image:
                        self.assertEqual(image.size, (1080, 1350))
                        self.assertEqual(image.format, "PNG")
                        self.assertGreater(output.stat().st_size, 10000)

    def test_unknown_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                render_content_card("unknown", "text", Path(tmp) / "x.png")
