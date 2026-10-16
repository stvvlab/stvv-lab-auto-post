"""Portraitless card safety tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import generate_social_cards as cards
import stvv_post as post

class PlayerCardTests(unittest.TestCase):
    def test_generated_art_is_portrait_free_data_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = cards.render(Path(tmp) / "player.png")
            self.assertTrue(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(p.stat().st_size, 1000)

    def test_only_generic_player_posts_eligible(self):
        self.assertIsNone(post.faceless_player_media("news", None))
        self.assertIsNone(post.faceless_player_media("player", "thesportsdb:123"))

    def test_missing_image_falls_back_to_text(self):
        with patch.object(post.Path, "is_file", return_value=False):
            self.assertIsNone(post.faceless_player_media("player", None))

if __name__ == "__main__":
    unittest.main()
