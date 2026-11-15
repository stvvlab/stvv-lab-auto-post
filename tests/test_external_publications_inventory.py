"""Regression tests: externally confirmed posts must be skipped, not block the scan."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock

import preparation_inventory as inventory
from stvv_post import JST


class ExternalPublicationTests(unittest.TestCase):
    def test_confirmed_external_story_skipped_and_next_story_processed(self):
        old = 'https://stvv.jp/news/game/20261109_1/'
        fresh = 'https://stvv.jp/news/team/20261113_1/'
        now = datetime(2026, 11, 14, 4, tzinfo=JST)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'editorial'
            directory.mkdir()
            (directory / 'external_publications.json').write_text(json.dumps({
                'items': [{'source_url': old,
                           'status': 'confirmed_external_publication',
                           'evidence_note': 'User screenshot of already published X post'}]
            }), encoding='utf-8')
            with patch.object(inventory, 'ROOT', Path(tmp)), patch.object(
                inventory, 'scan_articles', return_value=(
                    [(old, (now.date(), '既出記事')),
                     (fresh, (now.date(), '新しい公式ニュース'))],
                    [{'status': 'ok'}])), patch.object(
                inventory, 'read_body', return_value='公式本文' * 40) as body:
                result = inventory.build_inventory(
                    {'news': [], 'publication_log': [], 'pending_posts': {}},
                    {'cards': []}, now, session=Mock())
        self.assertEqual([c['source_url'] for c in result['candidates']], [fresh])
        self.assertEqual(result['skipped'][0]['source_url'], old)
        body.assert_called_once_with(unittest.mock.ANY, fresh)
        self.assertFalse(result['publication_performed'])

    def test_unconfirmed_entry_cannot_silently_suppress_story(self):
        now = datetime(2026, 11, 14, 4, tzinfo=JST)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'editorial'
            directory.mkdir()
            (directory / 'external_publications.json').write_text(json.dumps({
                'items': [{'source_url': 'https://stvv.jp/news/game/20261109_1/',
                           'status': 'unverified'}]
            }), encoding='utf-8')
            with patch.object(inventory, 'ROOT', Path(tmp)), patch.object(
                inventory, 'scan_articles', return_value=([], [{'status': 'ok'}])):
                with self.assertRaises(ValueError):
                    inventory.build_inventory(
                        {'news': [], 'publication_log': [], 'pending_posts': {}},
                        {'cards': []}, now, session=Mock())


if __name__ == '__main__':
    unittest.main()
