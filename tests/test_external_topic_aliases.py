"""Explicit aliases skip the same externally published topic, then continue."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import preparation_inventory as inventory
from stvv_post import JST


class ExternalTopicAliasTests(unittest.TestCase):
    def test_alias_skips_published_topic_but_keeps_next_candidate(self):
        source = 'https://stvv.jp/news/team/20261106_3/'
        alias = 'https://stvv.jp/news/team/20261107_2/'
        fresh = 'https://stvv.jp/news/event/20261113_2/'
        now = datetime(2026, 11, 14, 5, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'editorial').mkdir()
            (root / 'editorial/external_publications.json').write_text(
                json.dumps({'items': [{
                    'source_url': source,
                    'related_source_urls': [alias],
                    'status': 'confirmed_external_publication',
                    'evidence_note': 'User-confirmed X post screenshot',
                }]}), encoding='utf-8')
            with patch.object(inventory, 'ROOT', root), patch.object(
                inventory, 'scan_articles', return_value=([
                    (alias, (now.date(), '別URLの既出話題')),
                    (fresh, (now.date(), '別の新規イベント')),
                ], [{'status': 'ok'}])), patch.object(
                inventory, 'read_body', return_value='公式本文。' * 40) as body:
                result = inventory.build_inventory(
                    {'news': [], 'publication_log': [], 'pending_posts': {}},
                    {'cards': []}, now, session=Mock())
        self.assertEqual([x['source_url'] for x in result['candidates']], [fresh])
        self.assertEqual([x['source_url'] for x in result['skipped']], [alias])
        body.assert_called_once_with(unittest.mock.ANY, fresh)

    def test_invalid_alias_does_not_silently_suppress_candidates(self):
        now = datetime(2026, 11, 14, 5, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'editorial').mkdir()
            (root / 'editorial/external_publications.json').write_text(
                json.dumps({'items': [{
                    'source_url': 'https://stvv.jp/news/team/20261106_3/',
                    'related_source_urls': ['https://example.com/untrusted'],
                    'status': 'confirmed_external_publication',
                    'evidence_note': 'Screenshot',
                }]}), encoding='utf-8')
            with patch.object(inventory, 'ROOT', root), patch.object(
                inventory, 'scan_articles', return_value=([], [{'status': 'ok'}])):
                with self.assertRaisesRegex(ValueError, 'aliases are invalid'):
                    inventory.build_inventory(
                        {'news': [], 'publication_log': [], 'pending_posts': {}},
                        {'cards': []}, now, session=Mock())


if __name__ == '__main__':
    unittest.main()
