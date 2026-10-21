"""Smoke-test all seven Japanese editorial layouts."""
import tempfile
import unittest
import json
from pathlib import Path
from PIL import Image
from content_card import LABELS, render_content_card, story, wrap, font, panel_boxes, fitted
from PIL import ImageDraw

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

    def test_scorer_panels_keep_order_and_source_label_is_not_orphaned(self):
        rows = ['松澤海斗：15分', '新川志音：39分', 'ソエル・ソエル：62分', 'ムブク：71分']
        _, _, groups = story('\n'.join(['得点時間', 'STVV 4–1 ロンメル', *rows,
                                        '公式：https://stvv.jp/news/game/20261019_1/']))
        self.assertEqual(groups, ['\n'.join(rows[:2]), '\n'.join(rows[2:]), ''])

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

    def test_no_empty_panels_and_width_adapts_to_content(self):
        self.assertEqual(panel_boxes(['', '', '']), [])
        single = panel_boxes(['本文', '', ''])
        pair = panel_boxes(['本文一', '本文二', ''])
        self.assertEqual(len(single), 1)
        self.assertEqual(len(pair), 2)
        self.assertGreater(single[0][1][2], pair[0][1][2])
        self.assertLessEqual(pair[-1][1][0] + pair[-1][1][2], 1332)

    def test_quality_audit_contains_real_copy_and_font_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'audit.jpg'
            render_content_card('recap', '試合結果\nSTVV 4–1 ロンメル\n松澤海斗、同点ゴール。', output)
            audit = json.loads(output.with_suffix('.layout.json').read_text())
            self.assertEqual(audit['template_version'], 6)
            self.assertEqual(audit['score_from_caption'], ['4', '1', 'ロンメル'])
            self.assertEqual(len(audit['panels']), 1)
            self.assertEqual(audit['panels'][0]['text'], '松澤海斗、同点ゴール。')
            self.assertGreaterEqual(audit['panels'][0]['font_size'], 22)
            sweep = audit['heading_sweep']
            self.assertEqual(sweep['box'], [448, 350, 520, 35])
            self.assertEqual(len(sweep['bristles']), 5)

    def test_panel_hierarchy_preserves_exact_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'hierarchy.jpg'
            render_content_card('recap', '試合結果\nSTVV 4–1 ロンメル\n松澤海斗、同点ゴール。', output)
            panel = json.loads(output.with_suffix('.layout.json').read_text())['panels'][0]
            self.assertEqual(panel['delimiter'].join(panel['parts']), panel['text'])
            self.assertGreater(panel['lead_layout']['font_size'], panel['body_layout']['font_size'])

    def test_scoring_times_align_without_splitting_or_losing_names(self):
        rows = ['松澤海斗：15分', '新川志音：39分', 'ソエル・ソエル：62分', 'ムブク：71分']
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'scorers.jpg'
            render_content_card('data', '\n'.join(['得点時間', 'STVV 4–1 ロンメル', *rows]), output)
            panels = json.loads(output.with_suffix('.layout.json').read_text())['panels']
            reconstructed = []
            for panel in panels:
                self.assertEqual(panel['hierarchy'], 'scorer-times')
                self.assertEqual(len({row['time_layout']['box'][0] for row in panel['rows']}), 1)
                for row in panel['rows']:
                    reconstructed.append(row['name'] + row['delimiter'] + row['time'])
                    self.assertEqual(row['name_layout']['lines'], [row['name']])
                    name_box, time_box = row['name_layout']['box'], row['time_layout']['box']
                    self.assertLess(name_box[0] + name_box[2], time_box[0])
            self.assertEqual(reconstructed, rows)

    def test_news_body_balances_orphan_ending_without_changing_copy_or_size(self):
        news = json.loads(Path('editorial/verified_news_heading.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'news.jpg'
            render_content_card('news', 'STVV公式ニュース\n' + news['headline'], output)
            panel = json.loads(output.with_suffix('.layout.json').read_text())['panels'][0]
            self.assertEqual(''.join(panel['lines']), panel['text'])
            self.assertEqual(panel['font_size'], 48)
            self.assertEqual(len(panel['lines']), 2)
            draw = ImageDraw.Draw(Image.new('RGB', (1374, 1145)))
            lengths = [draw.textlength(line, font=font(48)) for line in panel['lines']]
            self.assertGreater(min(lengths) / max(lengths), 0.55)
            self.assertTrue(all(length <= panel['box'][2] for length in lengths))
            self.assertTrue(any('ゴール' in line for line in panel['lines']))
            self.assertTrue(any('加入後初ゴール' in line for line in panel['lines']))

    def test_balancing_keeps_explicit_line_breaks(self):
        draw = ImageDraw.Draw(Image.new('RGB', (1400, 300)))
        value = '攻撃の組み立てを確認する。\n守備。'
        layout = fitted(draw, value, (0, 0, 1238, 175), 48, 22, dry_run=True, balance=True)
        self.assertEqual(layout['lines'], value.splitlines())

    def test_match_date_is_metadata_not_a_statistics_panel(self):
        message = '試合結果\n2026-10-19｜ホーム\nSTVV 4–1 ロンメル\n結果：勝利。'
        _, _, groups, metadata = story(message, include_metadata=True)
        self.assertEqual(metadata, ['2026-10-19｜ホーム'])
        self.assertNotIn('2026-10-19｜ホーム', groups)
        # A date outside an explicit match must not disappear from the story.
        _, _, groups = story('日程のお知らせ\n2026-10-19｜ホーム')
        self.assertIn('2026-10-19｜ホーム', groups)

    def test_long_detail_retains_full_panel_layout_without_losing_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'long.jpg'
            detail = '注目点、' + '攻撃の組み立てを確認。' * 20
            render_content_card('analysis', '戦術の見方\n' + detail, output)
            panel = json.loads(output.with_suffix('.layout.json').read_text())['panels'][0]
            self.assertEqual(panel['hierarchy'], 'body')
            self.assertEqual(panel['text'], detail)

    def test_japanese_names_and_units_are_not_split_when_they_fit(self):
        draw = ImageDraw.Draw(Image.new('RGB', (800, 600)))
        face = font(40)
        for text in ['松澤海斗、同点ゴール。', 'ソエル・ソエル62分／ムブク71分。', '新川志音、加入後初ゴール。']:
            rows = wrap(draw, text, face, 360)
            self.assertEqual(''.join(rows), text)
            self.assertTrue(all(draw.textlength(row, font=face) <= 360 for row in rows))
            self.assertFalse(any(row.startswith(('、', '。', 'ー')) for row in rows))
        rows = wrap(draw, '松澤海斗、同点ゴール。', face, 360)
        self.assertTrue(any('ゴール' in row for row in rows))

    def test_punctuation_at_width_boundary_shrinks_without_splitting_name(self):
        draw = ImageDraw.Draw(Image.new('RGB', (400, 300)))
        for text, word in [('松澤海斗、同点ゴール。', '松澤海斗、'),
                           ('ゴール。', 'ゴール。')]:
            width = int(draw.textlength(word[:-1], font=font(40)))
            layout = fitted(draw, text, (0, 0, width, 200), 40, 22)
            self.assertLess(layout['font_size'], 40)
            self.assertIn(word, layout['lines'])
            self.assertEqual(''.join(layout['lines']), text)
            self.assertTrue(all(draw.textlength(line, font=font(layout['font_size'])) <= width
                                for line in layout['lines']))
