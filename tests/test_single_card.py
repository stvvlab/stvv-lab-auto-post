import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import single_card
import publish_single_card as pilot


class SingleCardTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(pilot.MANIFEST.read_text())

    def test_verified_card_renders_png(self):
        with tempfile.TemporaryDirectory() as folder:
            path = single_card.render(self.data, Path(folder) / 'card.png')
            with Image.open(path) as im:
                self.assertEqual(im.size, (1200, 1500))
                self.assertEqual(im.format, 'PNG')
                im.verify()

    def test_rejects_missing_or_unverified_inputs(self):
        for field in ['source_url', 'home_score', 'away']:
            data = copy.deepcopy(self.data)
            del data[field]
            with self.assertRaises(ValueError):
                single_card.validate(data)
        data = dict(self.data, source_url='https://example.org/')
        with self.assertRaises(ValueError):
            single_card.validate(data)

    def test_render_only_never_contacts_buffer(self):
        with patch.object(pilot, 'render'), patch.object(pilot.posting, 'send') as send:
            pilot.main(False)
            send.assert_not_called()

    def test_used_and_pending_are_never_resent(self):
        for history in [dict(used_posts=[self.data['key']], pending_posts={}),
                        dict(used_posts=[], pending_posts={self.data['key']: {}})]:
            with patch.object(pilot, 'render'), patch.object(pilot.posting, 'load', return_value=history), \
                 patch.object(pilot.posting, 'publish') as publish:
                pilot.main(True)
                publish.assert_not_called()

    def test_approved_asset_is_used_without_redrawing(self):
        with patch.object(pilot, 'render') as render:
            self.assertEqual(pilot.prepare_image(self.data), Path(self.data['asset_path']))
            render.assert_not_called()

    def test_modified_asset_fails_before_send(self):
        data = dict(self.data, asset_sha256='0' * 64)
        with self.assertRaises(ValueError):
            pilot.prepare_image(data)
