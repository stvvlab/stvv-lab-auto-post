import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import prepared_media as media
import stvv_post as posting


class PreparedDesignTests(unittest.TestCase):
    def test_style_metadata_requires_exact_reviewed_card(self):
        card = {"source_url": "https://stvv.jp/news/example/", "text": "確認済み本文",
                "slots": ["news"], "reviewed": True, "status": "ready",
                "art_direction": "comic-cover"}
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "cards.json"
            for change, expected in [({}, "comic-cover"), ({"reviewed": False}, None),
                                     ({"status": "published"}, None),
                                     ({"art_direction": "unreviewed-style"}, None)]:
                manifest.write_text(json.dumps({"enabled": True, "cards": [dict(card, **change)]}))
                with patch.object(media, "MANIFEST", manifest):
                    self.assertEqual(media.prepared_art_direction("news", card["text"], card["source_url"]), expected)
                    self.assertIsNone(media.prepared_art_direction("news", "changed caption", card["source_url"]))

    def test_design_history_saved_before_send_and_after_acceptance(self):
        history = {"used_posts": [], "pending_posts": {}, "publication_log": [], "news": []}
        snapshots = []
        with patch.object(posting, "save", side_effect=lambda h: snapshots.append(copy.deepcopy(h))), \
             patch.object(posting, "send", return_value={"id": "mock", "status": "sent"}):
            self.assertTrue(posting.publish(history, "k", "確認済み本文", "vote", art_direction="comic-cover"))
        self.assertEqual(snapshots[0]["pending_posts"]["k"]["art_direction"], "comic-cover")
        self.assertEqual(history["publication_log"][0]["art_direction"], "comic-cover")
