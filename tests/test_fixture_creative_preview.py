import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image

from fixture_creative_preview import make_preview
from tests.test_fixture_draft_art import REPORT


class CreativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.art = self.root / 'original.png'
        Image.new('RGB', (900, 900), '#ffdb28').save(self.art)
        self.output = self.root / 'review.png'
        self.metadata = self.root / 'review.json'

    def test_creative_image_and_unapproved_review_packet(self):
        result = make_preview(REPORT, self.art, self.output, self.metadata,
                              date(2026, 10, 27))
        with Image.open(self.output) as image:
            self.assertEqual(image.size, (1200, 1500))
            self.assertEqual(image.format, 'PNG')
        self.assertEqual(result['status'], 'unapproved_creative_preview')
        self.assertFalse(result['reviewed'])
        self.assertFalse(result['can_publish'])
        self.assertFalse(result['buffer_called'])
        self.assertFalse(result['x_publication_performed'])
        self.assertTrue(result['source_conflict'])
        self.assertTrue(result['kickoff_omitted'])
        self.assertEqual(len(result['preview_sha256']), 64)
        self.assertNotIn('15:00', result['draft_caption'])
        self.assertNotIn('16:00', result['draft_caption'])
        self.assertEqual(json.loads(self.metadata.read_text())['preview_sha256'],
                         result['preview_sha256'])

    def test_expired_or_unverified_fixture_cannot_render(self):
        with self.assertRaises(ValueError):
            make_preview(REPORT, self.art, self.output, self.metadata,
                         date(2026, 11, 2))
        self.assertFalse(self.output.exists())
        bad = dict(REPORT, status='source_incomplete_block_kickoff')
        with self.assertRaises(ValueError):
            make_preview(bad, self.art, self.output, self.metadata,
                         date(2026, 10, 27))
        self.assertFalse(self.output.exists())

    def test_never_overwrites_source_or_accepts_missing_art(self):
        with self.assertRaises(ValueError):
            make_preview(REPORT, self.art, self.art, self.metadata,
                         date(2026, 10, 27))
        with self.assertRaises(ValueError):
            make_preview(REPORT, self.root / 'missing.png',
                         self.output, self.metadata, date(2026, 10, 27))


if __name__ == '__main__':
    unittest.main()
