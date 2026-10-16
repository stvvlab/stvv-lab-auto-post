"""Offline tests: validate image attachment without creating a real post."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import stvv_post as p

class FakeResponse:
    content = b"\x89PNG\r\n\x1a\nmock-data"
    def raise_for_status(self):
        pass

class ImageTests(unittest.TestCase):
    def test_wrong_or_missing_source_never_attaches(self):
        for value in [None, "other:123", "thesportsdb:abc"]:
            self.assertIsNone(p.media_for(value, "data"))
        self.assertIsNone(p.media_for("thesportsdb:123", "news"))

    def test_media_requires_same_match_and_identical_public_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "generated"
            folder.mkdir()
            (folder / "match_42.png").write_bytes(FakeResponse.content)
            (folder / "match_manifest.json").write_text(
                json.dumps({"event_id": "42", "image": "generated/match_42.png"}),
                encoding="utf-8"
            )
            import os
            previous = os.getcwd()
            try:
                os.chdir(root)
                with patch.object(p.subprocess, "check_output", return_value="a"*40 + "\n"), \
                     patch.object(p.SESSION, "get", return_value=FakeResponse()):
                    result = p.media_for("thesportsdb:42", "data")
                    self.assertIn("match_42.png", result)
                    self.assertIsNone(p.media_for("thesportsdb:43", "data"))
            finally:
                os.chdir(previous)

    def test_generic_media_requires_matching_public_png(self):
        with tempfile.TemporaryDirectory() as td:
            import os
            root = Path(td)
            (root / "generated").mkdir()
            (root / "generated/topic_vote.png").write_bytes(FakeResponse.content)
            before = os.getcwd()
            try:
                os.chdir(root)
                with patch.object(p.subprocess, "check_output", return_value="a" * 40 + "\n"), \
                     patch.object(p.SESSION, "get", return_value=FakeResponse()):
                    self.assertIn("topic_vote.png", p.generic_topic_media("vote"))
                    self.assertIsNone(p.generic_topic_media("news"))
                    self.assertIsNone(p.generic_topic_media("player"))
            finally:
                os.chdir(before)

    def test_buffer_payload_has_image_asset_only_when_supplied(self):
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {"data": {"createPost": {"post": {"id": "fake", "status": "sent"}}}}
        for media in [None, "https://example.org/image.png"]:
            captured = {}
            def fake_post(*args, **kwargs):
                captured.update(kwargs)
                return Response()
            with patch.dict(p.os.environ, {"BUFFER_API_KEY": "fake"}), patch.object(p.SESSION, "post", side_effect=fake_post):
                p.send("test post", image_url=media)
            assets = captured["json"]["variables"]["input"]["assets"]
            self.assertEqual(assets, [{"image":{"url":media}}] if media else [])

if __name__ == "__main__":
    unittest.main()
