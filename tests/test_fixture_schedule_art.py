import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from fixture_schedule_art import prepare, validated_fixture, SOURCE

NOW = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
CANDIDATE = {
    "fixture_id": "4d838512b1a84f78180c0196",
    "competition": "Belgian Pro League",
    "round": 10,
    "kickoff_jst": "2026-11-02T00:00:00+09:00",
    "venue": "HOME",
    "opponent": "OHルーベン",
    "source_url": SOURCE,
    "status": "fixture_evidence_only",
    "reviewed": False,
    "can_publish": False,
}
REPORT = {"source_url": SOURCE, "status": "fixture_evidence_available",
          "candidates": [CANDIDATE]}


class DynamicFixtureArtTests(unittest.TestCase):
    def test_three_actual_distinct_japanese_artworks_and_caption(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = prepare(REPORT, tmp, NOW)
            self.assertEqual(packet["status"], "unapproved_fixture_review_packet")
            self.assertEqual(len(packet["variants"]), 3)
            self.assertEqual(len({v["sha256"] for v in packet["variants"]}), 3)
            self.assertEqual(packet["fixture_id"], CANDIDATE["fixture_id"])
            self.assertEqual(packet["fixture_date_local_evidence_only"], "2026-11-01")
            self.assertIn("OHルーベン", packet["caption_draft"])
            self.assertIn("第10節", packet["caption_draft"])
            self.assertNotIn("00:00", packet["caption_draft"])
            self.assertNotIn("キックオフ", packet["caption_draft"])
            self.assertFalse(packet["auto_publish"])
            self.assertFalse(packet["reviewed"])
            self.assertFalse(packet["buffer_called"])
            self.assertFalse(packet["x_publication_performed"])
            for variant in packet["variants"]:
                with Image.open(variant["path"]) as image:
                    self.assertEqual(image.size, (1200, 1500))
                    image.verify()
            with Image.open(packet["contact_sheet"]) as sheet:
                self.assertEqual(sheet.size, (1180, 565))

    def test_no_fixture_produces_no_image_and_no_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare({"source_url": SOURCE, "status": "no_upcoming_unrecorded_league_fixture", "candidates": []}, tmp, NOW)
            self.assertFalse(result["image_generation_performed"])
            self.assertFalse(result["buffer_called"])
            self.assertFalse(list(Path(tmp).glob("*.png")))

    def test_published_or_approved_items_are_not_draft_sources(self):
        for changed in ({"status": "published"}, {"reviewed": True},
                        {"can_publish": True}, {"source_url": "https://example.com"}):
            candidate = dict(CANDIDATE, **changed)
            self.assertIsNone(validated_fixture(
                {"source_url": SOURCE, "status": "fixture_evidence_available", "candidates": [candidate]}, NOW))

    def test_untrusted_or_expired_source_is_not_rendered(self):
        with self.assertRaises(ValueError):
            validated_fixture({"source_url": "https://example.com",
                               "status": "fixture_evidence_available", "candidates": [CANDIDATE]}, NOW)
        self.assertIsNone(validated_fixture(
            REPORT, datetime(2026, 11, 3, tzinfo=timezone.utc)))

    def test_japanese_long_opponent_name_stays_renderable(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"source_url": SOURCE, "status": "fixture_evidence_available", "candidates": [
                dict(CANDIDATE, opponent="サンプル長い日本語対戦相手名テストクラブ")]}
            result = prepare(data, tmp, NOW)
            self.assertEqual(len(result["variants"]), 3)


if __name__ == "__main__":
    unittest.main()
