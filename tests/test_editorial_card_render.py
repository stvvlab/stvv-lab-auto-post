"""Render every editorial slot to catch font, layout and Pillow regressions."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from content_card import render_content_card, LABELS

class EditorialCardSmokeTests(unittest.TestCase):
    def test_all_seven_cards_render(self):
        samples = {
            "player": "🇯🇵 STVV選手分析｜前線での動きと守備への貢献",
            "compare": "⚔️ STVV 1–0 対戦相手\nシュート数の比較",
            "data": "📊 STVVの試合データ\n枠内シュート：3本",
            "analysis": "🧠 STVVの守備分析｜連動したプレス",
            "news": "📰 STVV公式ニュース\n新しいクラブ情報",
            "vote": "🗳️ 次に知りたい分析は？\n①守備 ②攻撃 ③選手",
            "recap": "⚽ STVV試合結果\nSTVV 1–0 対戦相手\n結果：勝利",
        }
        with tempfile.TemporaryDirectory() as directory:
            for slot in LABELS:
                with self.subTest(slot=slot):
                    path = Path(directory) / (slot + ".png")
                    render_content_card(slot, samples[slot], path)
                    with Image.open(path) as im:
                        self.assertEqual(im.size, (1080, 1350))
                        self.assertEqual(im.format, "PNG")
                        im.verify()

if __name__ == "__main__":
    unittest.main()
