"""Reviewed image delivery must reject changed text, assets and public bytes."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
import prepared_media as media
import stvv_post as posting


class PreparedMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'generated').mkdir()
        self.path = self.root / 'generated/card.png'
        Image.new('RGB', (40, 30), 'navy').save(self.path)
        self.raw = self.path.read_bytes()
        self.card = dict(source_url='https://stvv.jp/news/uefa-news/20261023_1/',
                         text='確認済みの試合結果', slots=['news'], reviewed=True, status='ready',
                         asset_path='generated/card.png', dimensions=[40, 30],
                         sha256=hashlib.sha256(self.raw).hexdigest())
        self.manifest = self.root / 'cards.json'
        self.write()
        self.session = Mock()
        self.session.get.return_value.content = self.raw
        self.patches = [patch.object(media, 'ROOT', self.root),
                        patch.object(media, 'MANIFEST', self.manifest),
                        patch.object(media.subprocess, 'check_output', return_value='a' * 40)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write(self, enabled=True):
        self.manifest.write_text(json.dumps(dict(enabled=enabled, cards=[self.card])))

    def deliver(self, **changes):
        args = dict(slot='news', message=self.card['text'], source=self.card['source_url'])
        args.update(changes)
        return media.prepared_media(self.session, **args)

    def test_reviewed_asset_uses_immutable_verified_public_bytes(self):
        enabled, url = self.deliver()
        self.assertTrue(enabled)
        self.assertIn('/' + 'a' * 40 + '/generated/card.png', url)

    def test_changed_caption_source_slot_or_review_cannot_reuse_image(self):
        for changes in [dict(message='別の情報'), dict(source='https://example.org/'), dict(slot='data')]:
            self.assertEqual(self.deliver(**changes), (True, None))
        self.card['reviewed'] = False
        self.write()
        self.assertEqual(self.deliver(), (True, None))
        self.session.get.assert_not_called()

    def test_ambiguous_entries_are_not_delivered(self):
        self.manifest.write_text(json.dumps(dict(enabled=True, cards=[self.card, self.card])))
        self.assertEqual(self.deliver(), (True, None))

    def test_changed_local_or_remote_image_is_rejected(self):
        self.path.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.deliver()
        self.session.get.assert_not_called()
        self.path.write_bytes(self.raw)
        self.session.get.return_value.content = b'wrong public image'
        with self.assertRaises(ValueError):
            self.deliver()

    def test_escaping_generated_directory_is_rejected(self):
        self.card['asset_path'] = 'generated/../private.png'
        self.write()
        with self.assertRaises(ValueError):
            self.deliver()

    def test_missing_or_disabled_manifest_preserves_legacy_mode(self):
        self.write(enabled=False)
        self.assertEqual(self.deliver(), (False, None))
        self.manifest.unlink()
        self.assertEqual(self.deliver(), (False, None))

    def test_enabled_mode_never_silently_redraws_unprepared_content(self):
        with patch('content_card.render_content_card') as render:
            self.assertIsNone(posting.content_card_media('news', '2026-10-24', '別の情報', self.card['source_url']))
            render.assert_not_called()

    def test_candidates_require_fresh_date_official_source_and_visible_citation(self):
        now = datetime(2026, 10, 24)
        self.card.update(date_jst='2026-10-23', text='結果\n' + self.card['source_url'])
        self.write()
        self.assertEqual(media.prepared_candidates('news', now), [(self.card['text'], self.card['source_url'])])
        for changes in [dict(date_jst='2026-10-01'), dict(date_jst='2026-10-25'),
                        dict(source_url='https://example.org/'), dict(text='出典がない結果')]:
            original = dict(self.card)
            self.card.update(changes)
            self.write()
            self.assertEqual(media.prepared_candidates('news', now), [])
            self.card = original
