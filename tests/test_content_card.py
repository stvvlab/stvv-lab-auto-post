"""Smoke-test all seven Japanese editorial layouts."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from content_card import LABELS, render_content_card, story

class ContentCardSmokeTests(unittest.TestCase):
    def test_all_layouts(self):
        sample = "⚽ STVV試合分析\n日本人選手の動きと守備の切り替えを確認。\nシュート数と枠内シュートを比較。"
        with tempfile.TemporaryDirectory() as tmp:
            for slot in LABELS:
                with self.subTest(slot=slot):
                    output = Path(tmp) / (slot + ".png")
                    render_content_card(slot, sample, output)
                    with Image.open(output) as image:
                        self.assertEqual(image.size, (1374, 1145))
                        self.assertEqual(image.format, "PNG")
                        self.assertGreater(output.stat().st_size, 10000)

    def test_unknown_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                render_content_card("unknown", "text", Path(tmp) / "x.png")

    def test_source_text_only_no_invented_score(self):
        headline, match, groups = story('STVV公式ニュース\n新川志音が加入後初ゴール。\nhttps://stvv.jp/news/game/20261019_1/')
        self.assertEqual(headline, '新川志音が加入後初ゴール。')
        self.assertIsNone(match)
        self.assertEqual(groups, ['', '', ''])

    def test_score_and_all_detail_paragraphs_preserved(self):
        headline, match, groups = story('試合結果\nSTVV 4–1 ロンメル\n松澤15分\n新川39分\n追加点62分\n追加点71分')
        self.assertEqual(match, ('4', '1', 'ロンメル'))
        self.assertEqual(sorted('\n'.join(groups).splitlines()),
                         sorted(['松澤15分', '新川39分', '追加点62分', '追加点71分']))

    def test_empty_or_overlong_copy_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for copy in ['', '非常に長い未整理の文章' * 200]:
                with self.assertRaises(ValueError):
                    render_content_card('news', copy, Path(tmp) / 'x.jpg')

    def test_jpeg_and_identical_content_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / ('x' + str(i) + '.jpg') for i in range(2)]
            for path in paths:
                render_content_card('vote', '次に読みたい分析は？\n攻撃／守備／選手', path)
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
            with Image.open(paths[0]) as image:
                self.assertEqual(image.format, 'JPEG')
