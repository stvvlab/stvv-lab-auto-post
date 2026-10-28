import unittest
from datetime import datetime, timezone
from fixture_schedule_gate import review_fixture_candidate

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
URL = "https://stvv.jp/game/2026-2027/"
BASE = {"status":"ready","reviewed":True,"auto_publish":True,
        "kind":"fixture_schedule","source_url":URL,"fixture_date_jst":"2026-11-06",
        "fixture_identity":"fixture:2026-11-06:skブラン","opponent":"SKブラン",
        "text":"STVV 対 SKブラン 11月6日 "+URL, "asset_path":"generated/review.png",
        "sha256":"0"*64, "kickoff_verified":False,
        "schedule_evidence_excerpt":"11月6日 STVV SKブラン"}
HISTORY={"used_posts":[],"publication_log":[],"pending_posts":{},"reserved_posts":{}}
class FixtureScheduleGateTest(unittest.TestCase):
    def check(self,c=None,h=None,e="11月6日 STVV SKブラン"):
        return review_fixture_candidate(c or BASE,NOW,h or HISTORY,e)
    def test_reviewed_fixture_may_be_eligible_offline(self):
        self.assertIsNone(self.check())
    def test_draft_blocked(self):
        self.assertEqual(self.check({**BASE,"reviewed":False}),"not_approved")
    def test_official_schedule_must_contain_match(self):
        self.assertEqual(self.check(e="11月6日 STVV unrelated team"),"match_specific_schedule_evidence_missing")
    def test_opponent_and_date_in_different_rows_are_not_enough(self):
        self.assertEqual(self.check(e="11月6日 another club\\n11月9日 STVV SKブラン"),
                         "match_specific_schedule_evidence_missing")
    def test_same_match_previously_used(self):
        self.assertEqual(self.check(h={**HISTORY,"used_posts":[BASE["fixture_identity"]]}),"fixture_already_used")
    def test_pending_duplicate(self):
        self.assertEqual(self.check(h={**HISTORY,"pending_posts":{"x":{"fixture_identity":BASE["fixture_identity"]}}}),"fixture_already_sent_or_pending")
    def test_kickoff_conflict_blocked(self):
        self.assertEqual(self.check({**BASE,"text":BASE["text"]+" キックオフ午前5時"}),"unverified_kickoff")
    def test_unverified_numeric_and_fullwidth_times_are_blocked(self):
        for time in ("16:00", "１６：００", "午後4時", "16時00分"):
            with self.subTest(time=time):
                self.assertEqual(
                    self.check({**BASE, "text": BASE["text"] + " " + time}),
                    "unverified_kickoff"
                )

    def test_verified_flag_alone_cannot_authorize_time(self):
        self.assertEqual(
            self.check({**BASE, "text": BASE["text"] + " 16:00",
                        "kickoff_verified": True}),
            "kickoff_evidence_missing"
        )

    def test_verified_time_requires_exact_source_excerpt(self):
        card = {**BASE, "text": BASE["text"] + " 16:00",
                "kickoff_verified": True,
                "kickoff_evidence_excerpt": "11月6日 STVV SKブラン 16:00",
                "schedule_evidence_excerpt": "11月6日 STVV SKブラン 16:00"}
        self.assertEqual(
            self.check(card, e="11月6日 STVV SKブラン 15:00"),
            "kickoff_evidence_missing"
        )
        self.assertIsNone(self.check(card, e="11月6日 STVV SKブラン 16:00"))

    def test_every_caption_clock_must_match_reviewed_evidence(self):
        card = {**BASE, "text": BASE["text"] + " 16:00 / 15:00",
                "kickoff_verified": True,
                "kickoff_evidence_excerpt": "11月6日 STVV SKブラン 16:00",
                "schedule_evidence_excerpt": "11月6日 STVV SKブラン 16:00"}
        self.assertEqual(
            self.check(card, e="11月6日 STVV SKブラン 16:00"),
            "kickoff_evidence_missing"
        )

    def test_matching_time_from_another_fixture_row_is_not_proof(self):
        card = {**BASE, "text": BASE["text"] + " 16:00",
                "kickoff_verified": True,
                "kickoff_evidence_excerpt": "11月7日 STVV OTHER 16:00"}
        official = "11月6日 STVV SKブラン 15:00\\n11月7日 STVV OTHER 16:00"
        self.assertEqual(
            self.check(card, e=official),
            "kickoff_evidence_not_match_specific"
        )

    def test_conflicting_official_kickoff_blocks_even_reviewed_time(self):
        card = {**BASE, "text": BASE["text"] + " 16:00",
                "kickoff_verified": True, "kickoff_conflict": True,
                "kickoff_evidence_excerpt": "11月6日 STVV SKブラン 16:00"}
        self.assertEqual(
            self.check(card, e="11月6日 STVV SKブラン 16:00"),
            "conflicting_kickoff_sources"
        )
        # The same fixture without a clock claim is still eligible offline.
        self.assertIsNone(self.check({**card, "text": BASE["text"]}))

    def test_shared_schedule_url_needs_unique_identity(self):
        self.assertEqual(self.check({**BASE,"fixture_identity":"shared"}),"missing_unique_fixture_identity")
    def test_image_required(self):
        self.assertEqual(self.check({**BASE,"asset_path":None}),"reviewed_image_missing")
if __name__ == "__main__": unittest.main()
