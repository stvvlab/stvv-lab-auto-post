import hashlib
import tempfile
import unittest
from pathlib import Path
from player_artwork import prepare_player_artwork, prepare_player_preview_brief

class PlayerArtworkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "source.png").write_bytes(b"photo")
        (root / "approved.png").write_bytes(b"approved")
        self.root = root
        self.manifest = {
            "player_name": "Taiga Hata",
            "profile_url": "https://stvv.jp/team-member/taiga-hata/",
            "reference_photo": "source.png",
            "approved_portrait": "approved.png",
            "approved_portrait_sha256": hashlib.sha256(b"approved").hexdigest(),
            "likeness_approved": True,
            "jersey_number": 3,
        }
    def tearDown(self):
        self.tmp.cleanup()
    def test_approved_draft_is_never_publishable(self):
        result = prepare_player_artwork(self.manifest, root=self.root)
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(result["verified_jersey_number"], 3)
        self.assertIn("2-head-tall", result["prompt"])
        self.assertIn("as shown in the approved portrait", result["prompt"])
        self.assertNotIn("curly hair", result["prompt"])
    def test_unapproved_fails_closed(self):
        self.manifest["likeness_approved"] = False
        with self.assertRaises(ValueError):
            prepare_player_artwork(self.manifest, root=self.root)
    def test_changed_portrait_fails_closed(self):
        (self.root / "approved.png").write_bytes(b"different")
        with self.assertRaises(ValueError):
            prepare_player_artwork(self.manifest, root=self.root)
    def test_official_profile_required(self):
        self.manifest["profile_url"] = "https://example.com/taiga-hata"
        with self.assertRaises(ValueError):
            prepare_player_artwork(self.manifest, root=self.root)
    def test_path_traversal_fails(self):
        self.manifest["reference_photo"] = "../file.png"
        with self.assertRaises(ValueError):
            prepare_player_artwork(self.manifest, root=self.root)

    def test_first_pass_brief_does_not_require_approved_portrait(self):
        preview = {
            "player_name": "Taiga Hata",
            "profile_url": "https://stvv.jp/team-member/taiga-hata/",
            "reference_photo": "source.png",
        }
        result = prepare_player_preview_brief(preview, root=self.root)
        self.assertEqual(result["status"], "unapproved_first_pass_brief")
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["image_generation_performed"])
        self.assertFalse(result["likeness_approved"])
        self.assertEqual(result["reference_photo_sha256"], hashlib.sha256(b"photo").hexdigest())
        self.assertIn("two-heads-tall", result["prompt"])
        self.assertIn("actual image-to-image input", result["prompt"])
        self.assertIn("lawfully", result["required_review"][0])
        self.assertNotIn("approved_portrait", result)

    def test_first_pass_brief_rejects_bad_reference_or_profile(self):
        preview = {
            "player_name": "Taiga Hata",
            "profile_url": "https://stvv.jp/team-member/taiga-hata/",
            "reference_photo": "source.png",
        }
        for path in ("../source.png", "missing.png", "source.txt"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    prepare_player_preview_brief({**preview, "reference_photo": path}, root=self.root)
        with self.assertRaises(ValueError):
            prepare_player_preview_brief({**preview, "profile_url": "https://example.com/player"}, root=self.root)
        with self.assertRaises(ValueError):
            prepare_player_preview_brief({**preview, "player_name": ""}, root=self.root)

if __name__ == "__main__":
    unittest.main()
