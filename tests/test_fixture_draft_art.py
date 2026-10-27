import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from PIL import Image

from fixture_draft_art import prepare, validate, render


REPORT = {
    'fixture': 'STVV - OH Leuven', 'fixture_date_local': '2026-11-01',
    'status': 'official_sources_disagree_block_kickoff',
    'source_times_local': {'stvv': '15:00', 'ohl': '16:00', 'stvv_jp': '16:00'},
    'source_checks': [{'source': x, 'status': 'ok', 'url': 'https://example.test/' + x}
                      for x in ('stvv', 'ohl', 'stvv_jp')],
}


class FixtureDraftArtTests(unittest.TestCase):
    def test_conflicting_kickoff_still_allows_time_free_unapproved_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'draft.png'
            metadata = Path(tmp) / 'draft.json'
            info = prepare(REPORT, output, metadata, date(2026, 10, 27))
            with Image.open(output) as img:
                self.assertEqual(img.size, (1200, 1500))
            self.assertFalse(info['can_publish'])
            self.assertFalse(info['reviewed'])
            self.assertTrue(info['kickoff_omitted'])
            self.assertTrue(info['date_omitted_from_artwork'])
            self.assertTrue(info['source_conflict'])
            self.assertFalse(info['buffer_called'])
            self.assertTrue(json.loads(metadata.read_text())['sha256'])

    def test_three_distinct_variants_and_contact_sheet_are_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'draft.png'
            metadata = Path(tmp) / 'draft.json'
            info = prepare(REPORT, output, metadata, date(2026, 10, 27))
            self.assertEqual(len(info['variants']), 3)
            self.assertEqual(len({v['sha256'] for v in info['variants']}), 3)
            self.assertEqual(
                [v['concept'] for v in info['variants']],
                ['editorial-poster', 'split-duel', 'stadium-lines'])
            for variant in info['variants']:
                self.assertTrue(Path(variant['image_path']).is_file())
                self.assertFalse(variant['reviewed'])
                self.assertFalse(variant['can_publish'])
                with Image.open(variant['image_path']) as image:
                    self.assertEqual(image.size, (1200, 1500))
            with Image.open(info['contact_sheet']) as sheet:
                self.assertEqual(sheet.size, (1180, 560))
            persisted = json.loads(metadata.read_text())
            self.assertEqual(len(persisted['variants']), 3)
            self.assertFalse(persisted['can_publish'])
            self.assertFalse(persisted['buffer_called'])

    def test_local_date_never_appears_in_japanese_review_artwork(self):
        # A Belgian local date differs from the JST calendar date. If the
        # date were drawn, changing it would change the image bytes.
        with tempfile.TemporaryDirectory() as tmp:
            for variant in range(3):
                first = render(date(2026, 11, 1), Path(tmp)/f'a{variant}.png', variant)
                second = render(date(2026, 11, 2), Path(tmp)/f'b{variant}.png', variant)
                self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_incomplete_source_blocks_preview(self):
        data = dict(REPORT, status='source_incomplete_block_kickoff')
        with self.assertRaises(ValueError):
            validate(data, date(2026, 10, 27))

    def test_expired_fixture_blocks_preview(self):
        with self.assertRaises(ValueError):
            validate(REPORT, date(2026, 11, 2))

    def test_far_future_fixture_blocks_preview(self):
        with self.assertRaises(ValueError):
            validate(REPORT, date(2026, 10, 1))

    def test_missing_verified_source_blocks_preview(self):
        data = dict(REPORT, source_checks=REPORT['source_checks'][:2])
        with self.assertRaises(ValueError):
            validate(data, date(2026, 10, 27))

    def test_false_agreement_blocks_preview(self):
        data = dict(REPORT, status='sources_agree_manual_review_required')
        with self.assertRaises(ValueError):
            validate(data, date(2026, 10, 27))

    def test_actual_agreement_still_unapproved(self):
        data = dict(REPORT, status='sources_agree_manual_review_required',
                    source_times_local={k: '16:00' for k in REPORT['source_times_local']})
        with tempfile.TemporaryDirectory() as tmp:
            info = prepare(data, Path(tmp)/'draft.png', Path(tmp)/'draft.json', date(2026, 10, 27))
            self.assertFalse(info['can_publish'])
            self.assertFalse(info['source_conflict'])

    def test_unknown_match_blocks_preview(self):
        data = dict(REPORT, fixture='Another match')
        with self.assertRaises(ValueError):
            validate(data, date(2026, 10, 27))


if __name__ == '__main__':
    unittest.main()
