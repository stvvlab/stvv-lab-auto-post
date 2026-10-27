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
    def test_shared_schedule_url_needs_unique_identity(self):
        self.assertEqual(self.check({**BASE,"fixture_identity":"shared"}),"missing_unique_fixture_identity")
    def test_image_required(self):
        self.assertEqual(self.check({**BASE,"asset_path":None}),"reviewed_image_missing")
if __name__ == "__main__": unittest.main()
