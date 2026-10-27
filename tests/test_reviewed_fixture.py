"""An old official event announcement can support ONE timely reviewed fixture.

Tests are offline. No image approval, Buffer API request or publication occurs.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import advance_reservations
import prepared_media
import stvv_post
from fixture_review import reviewed_fixture_date
from reservation_preview import plan

NOW = datetime.fromisoformat("2026-10-27T14:56:00+09:00")
SOURCE = "https://stvv.jp/news/event/20261002_2/"
BODY = "STVVは2026年11月1日（日）のOHルーヴェン戦にて日本人のお子様をご招待します。次の試合に向けた公式案内です。"
TEXT = "⚽ 11月1日はSTVV対OHルーヴェン！ 次戦の注目ポイントは？\n公式：" + SOURCE


def card():
    return {
        "source_url": SOURCE, "date_jst": "2026-10-02", "text": TEXT,
        "slots": ["news"], "reviewed": True, "status": "ready",
        "asset_path": "generated/reviewed_fixture.png",
        "sha256": "a" * 64, "dimensions": [1200, 1500],
        "fixture_preview": {
            "fixture_date_jst": "2026-11-01", "date_label": "11月1日",
            "opponent": "OHルーヴェン", "kickoff_omitted": True,
            "evidence_excerpt": "2026年11月1日（日）のOHルーヴェン戦",
            "source_body_sha256": hashlib.sha256(BODY.encode()).hexdigest(),
        },
    }


class ReviewedFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manifest = Path(self.temp.name) / "cards.json"
        self.card = card()
        self.patch = patch.object(prepared_media, "MANIFEST", self.manifest)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.write()

    def write(self):
        self.manifest.write_text(json.dumps({"enabled": True, "cards": [self.card]}))

    def test_old_source_is_eligible_only_for_imminent_reviewed_fixture(self):
        self.assertEqual(reviewed_fixture_date(self.card, NOW, BODY).isoformat(), "2026-11-01")
        self.assertEqual(prepared_media.prepared_candidates("news", NOW), [(TEXT, SOURCE)])
        self.assertEqual(prepared_media.prepared_candidates("news", NOW + timedelta(days=6)), [])
        self.assertEqual(prepared_media.prepared_candidates("news", NOW + timedelta(days=1)), [(TEXT, SOURCE)])

    def test_fixture_does_not_bypass_duplicate_gate(self):
        history = {"news": [], "used_posts": [], "pending_posts": {}, "publication_log": []}
        proposal = plan(history, NOW)["proposals"][0]
        self.assertEqual(proposal["slot"], "news")
        self.assertEqual(proposal["due_jst"], "2026-10-27T18:00:00+09:00")
        self.assertEqual(proposal["source_url"], SOURCE)
        history["publication_log"].append({"key": "old", "source": SOURCE, "text": TEXT})
        self.assertEqual(plan(history, NOW)["proposals"], [])

    def test_missing_news_ledger_cannot_be_treated_as_unused(self):
        history = {"used_posts": [], "pending_posts": {}, "publication_log": []}
        result = plan(history, NOW)
        self.assertEqual(result["proposals"], [])
        self.assertIn("fixture_source_ledger_missing",
                      [x.get("reason") for x in result["blocked"]])

    def test_historical_used_source_blocks_even_without_publication_log(self):
        history = {"news": [SOURCE], "used_posts": [], "pending_posts": {},
                   "reserved_posts": {}, "publication_log": []}
        result = plan(history, NOW)
        self.assertEqual(result["proposals"], [])
        self.assertIn("fixture_source_already_marked_used_reconcile_history",
                      [x.get("reason") for x in result["blocked"]])

    def test_fails_closed_on_changed_body_or_metadata(self):
        self.assertIsNone(reviewed_fixture_date(self.card, NOW, BODY + "改訂"))
        for field, value in [
            ("kickoff_omitted", False), ("source_body_sha256", "b" * 64),
            ("fixture_date_jst", "2026-12-01"), ("date_label", "11月2日"),
            ("opponent", "別チーム"),
        ]:
            with self.subTest(field=field):
                modified = copy.deepcopy(self.card)
                modified["fixture_preview"][field] = value
                self.assertIsNone(reviewed_fixture_date(modified, NOW, BODY))
        modified = copy.deepcopy(self.card)
        modified["text"] += " 16:00"
        self.assertIsNone(reviewed_fixture_date(modified, NOW, BODY))
        modified = copy.deepcopy(self.card)
        modified["source_url"] = "https://example.org/news/event/20261002_2/"
        self.assertIsNone(reviewed_fixture_date(modified, NOW, BODY))
        modified = copy.deepcopy(self.card)
        modified["reviewed"] = False
        self.assertIsNone(reviewed_fixture_date(modified, NOW, BODY))

    def test_disputed_kickoff_cannot_leak_through_japanese_or_fullwidth_clock(self):
        # Official sources disagree; kickoff_omitted requires a time-free caption.
        for claim in ("16:00", "１６：００", "午後4時", "16時00分",
                      "午前5時", "試合開始", "キックオフ", "開始時刻"):
            with self.subTest(claim=claim):
                changed = copy.deepcopy(self.card)
                changed["text"] += " " + claim
                self.assertIsNone(reviewed_fixture_date(changed, NOW, BODY))
        # The reviewed date-only wording is still allowed.
        self.assertEqual(reviewed_fixture_date(self.card, NOW, BODY).isoformat(),
                         "2026-11-01")

    def test_live_reservation_checks_body_before_buffer(self):
        history = {"news": [], "used_posts": [], "pending_posts": {},
                   "reserved_posts": {}, "publication_log": []}
        client = Mock()
        client.preflight.return_value = {"posts": [], "remaining_capacity": 10}
        with patch.object(advance_reservations, "read_body", return_value=BODY + "changed"):
            with self.assertRaisesRegex(RuntimeError, "Reviewed fixture evidence changed"):
                advance_reservations.run(history, NOW, client, Mock(), Mock())
        client.preflight.assert_not_called()
        client.schedule.assert_not_called()
        self.assertEqual(history["pending_posts"], {})

    def test_reviewed_fixture_can_reach_buffer_reservation_in_mock_only(self):
        history = {"news": [], "used_posts": [], "pending_posts": {},
                   "reserved_posts": {}, "publication_log": []}
        client = Mock()
        client.preflight.return_value = {"posts": [], "remaining_capacity": 10}
        def schedule(message, image, due):
            return {"id": "mock-reservation", "text": message,
                    "channelId": stvv_post.CHANNEL, "dueAt": due,
                    "status": "scheduled", "assets": [{"id": "mock-asset"}]}
        client.schedule.side_effect = schedule
        saved = []
        with patch.object(advance_reservations, "read_body", return_value=BODY), \
             patch.object(advance_reservations, "prepared_media", return_value=(True, "https://example.org/reviewed.png")), \
             patch.object(advance_reservations, "datetime", wraps=datetime) as clock:
            clock.now.return_value = NOW
            result = advance_reservations.run(history, NOW, client,
                                               lambda h: saved.append(copy.deepcopy(h)), Mock())
        self.assertEqual(result["status"], "reserved_in_buffer")
        self.assertEqual(client.schedule.call_count, 1)
        self.assertEqual(len(saved), 2)
        self.assertTrue(saved[0]["pending_posts"])
        self.assertFalse(history["publication_log"])
        self.assertFalse(history["news"])
        self.assertFalse(history["pending_posts"])
        self.assertFalse(result["new_reservations"][0]["x_display_verified"])


if __name__ == "__main__":
    unittest.main()
