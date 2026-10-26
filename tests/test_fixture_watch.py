import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

import fixture_watch as watch

NOW = datetime(2026, 10, 27, 0, tzinfo=timezone.utc)
STVV_HTML = """
<section><h2>1 november 2026</h2><p>DAIO WASABI STAYEN STADIUM
STVV 15:00 OH Leuven Ticketinfo</p></section>
"""
OHL_HTML = """
<div>01/11/2026 - 16:00 | A-Team | STVV - OH Leuven
01/11/2026 - 15:00 | Women | OH Leuven - Cercle Brugge</div>
"""

STVV_JP_HTML = """
<div>【対象試合】 ジュピラー・プロ・リーグ 第10節
2026年11月1日(日) 16時00分キックオフ ※ベルギー時間
STVV vs OHルーヴェン</div>
"""


def session_with_pages(stvv=STVV_HTML, ohl=OHL_HTML, stvv_jp=STVV_JP_HTML):
    session = Mock()
    session.get.side_effect = [
        Mock(url=watch.SOURCES["stvv"], text=stvv,
             content=stvv.encode("utf-8")),
        Mock(url=watch.SOURCES["ohl"], text=ohl,
             content=ohl.encode("utf-8")),
        Mock(url=watch.SOURCES["stvv_jp"], text=stvv_jp,
             content=stvv_jp.encode("utf-8")),
    ]
    return session


class FixtureWatchTests(unittest.TestCase):
    def test_two_club_official_times_conflict_and_no_publication(self):
        session = session_with_pages()
        report = watch.build_report(session, NOW)
        self.assertEqual(report["status"], "official_sources_disagree_block_kickoff")
        self.assertEqual(report["source_times_local"], {"stvv": "15:00", "ohl": "16:00", "stvv_jp": "16:00"})
        self.assertFalse(report["can_publish_kickoff_time"])
        self.assertFalse(report["can_publish_fixture_card"])
        self.assertFalse(report["buffer_called"])
        self.assertEqual(session.get.call_count, 3)

    def test_agreement_still_requires_manual_review(self):
        report = watch.build_report(
            session_with_pages(ohl=OHL_HTML.replace("16:00", "15:00"),
                               stvv_jp=STVV_JP_HTML.replace("16時00分", "15時00分")), NOW)
        self.assertEqual(report["status"], "sources_agree_manual_review_required")
        self.assertFalse(report["can_publish_kickoff_time"])

    def test_missing_or_ambiguous_time_does_not_fall_back_to_guess(self):
        report = watch.build_report(session_with_pages(stvv="<a>Unrelated fixtures</a>"), NOW)
        self.assertEqual(report["status"], "source_incomplete_block_kickoff")
        self.assertNotIn("stvv", report["source_times_local"])

    def test_external_redirect_is_not_trusted(self):
        session = session_with_pages()
        session.get.side_effect = [
            Mock(url="https://attacker.invalid/", text=STVV_HTML,
                 content=STVV_HTML.encode("utf-8")),
            Mock(url=watch.SOURCES["ohl"], text=OHL_HTML,
                 content=OHL_HTML.encode("utf-8")),
            Mock(url=watch.SOURCES["stvv_jp"], text=STVV_JP_HTML,
                 content=STVV_JP_HTML.encode("utf-8")),
        ]
        report = watch.build_report(session, NOW)
        self.assertEqual(report["status"], "source_incomplete_block_kickoff")
        self.assertEqual(report["source_checks"][0]["status"], "unverified")

    def test_japanese_official_article_requires_explicit_local_time_and_match(self):
        self.assertEqual(watch.extract_stvv_jp(STVV_JP_HTML), "16:00")
        with self.assertRaises(ValueError):
            watch.extract_stvv_jp(STVV_JP_HTML.replace("ベルギー時間", "日本時間"))

    def test_expired_fixture_does_not_make_network_calls(self):
        session = Mock()
        report = watch.build_report(session, datetime(2026, 11, 2, tzinfo=timezone.utc))
        self.assertEqual(report["status"], "fixture_expired_no_publication")
        session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
