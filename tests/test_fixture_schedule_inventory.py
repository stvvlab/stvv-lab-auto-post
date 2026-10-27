import copy
import unittest
from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import fixture_schedule_inventory as inventory

NOW = datetime(2026, 10, 27, 16, tzinfo=inventory.JST)
URL = 'https://stvv.jp/game/2026-2027/'
HTML = '''<p>*試合時間は日本時間の表記</p><h2>BELGIAN PRO LEAGUE</h2>
<div>第9節 2026 10.26 00:00 KICKOFF AWAY VS.クラブ・ブルージュ DAZN BS10</div>
<div>第10節 2026 11.2 00:00 KICKOFF HOME VS.OHルーベン DAZN BS10</div>
<div>第11節 2026 11.9 03:15 KICKOFF HOME VS.ズルテ・ワレヘム DAZN BS10</div>
<h2>UEFAカンファレンスリーグ</h2><div>第3節 2026 11.6 05:00 KICKOFF HOME VS.SKブラン</div>'''


class ScheduleInventoryTests(unittest.TestCase):
    def test_imminent_league_fixture_from_official_jst_schedule(self):
        fixtures = inventory.parse_fixtures(HTML, NOW)
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]['opponent'], 'OHルーベン')
        self.assertEqual(fixtures[0]['kickoff_jst'], '2026-11-02T00:00:00+09:00')
        self.assertEqual(fixtures[0]['venue'], 'HOME')

    def test_reschedule_does_not_create_new_fixture_identity(self):
        original = inventory.parse_fixtures(HTML, NOW)[0]
        updated = HTML.replace('11.2 00:00', '11.3 01:00').replace('OHルーベン', 'OHルーヴェン')
        changed = inventory.parse_fixtures(updated, NOW)[0]
        self.assertEqual(original['fixture_id'], changed['fixture_id'])
        self.assertNotEqual(original['kickoff_jst'], changed['kickoff_jst'])

    def test_competition_navigation_tabs_do_not_hide_real_fixtures(self):
        nav = '<nav>BELGIAN PRO LEAGUE UEFAカンファレンスリーグ BELGIAN CUP</nav>'
        result = inventory.parse_fixtures(
            HTML.replace('<h2>BELGIAN PRO LEAGUE</h2>',
                         nav + '<h2>BELGIAN PRO LEAGUE</h2>'), NOW)
        self.assertEqual([x['opponent'] for x in result], ['OHルーベン'])

    def test_no_timezone_notice_fails_closed(self):
        with self.assertRaises(ValueError):
            inventory.parse_fixtures(HTML.replace('試合時間は日本時間の表記', 'Times TBD'), NOW)

    def test_past_and_distant_fixtures_excluded(self):
        items = inventory.parse_fixtures(HTML, datetime(2026, 11, 3, tzinfo=inventory.JST))
        self.assertEqual([x['opponent'] for x in items], ['ズルテ・ワレヘム'])

    def test_read_only_unapproved_and_no_posting(self):
        history = {'publication_log': [], 'pending_posts': {}, 'reserved_posts': {}}
        original = copy.deepcopy(history)
        response = Mock(text=HTML, url=URL)
        response.raise_for_status.return_value = None
        session = Mock(get=Mock(return_value=response))
        report = inventory.build_inventory(history, NOW, session)
        self.assertEqual(history, original)
        self.assertEqual(report['status'], 'fixture_evidence_available')
        self.assertFalse(report['publication_performed'])
        self.assertFalse(report['candidates'][0]['can_publish'])
        self.assertFalse(report['candidates'][0]['reviewed'])
        self.assertNotIn('asset_path', report['candidates'][0])
        session.get.assert_called_once_with(URL, timeout=20)

    def test_duplicate_fixture_id_excluded(self):
        fixture = inventory.parse_fixtures(HTML, NOW)[0]
        history = {'publication_log': [{'fixture_id': fixture['fixture_id']}]}
        response = Mock(text=HTML, url=URL)
        response.raise_for_status.return_value = None
        report = inventory.build_inventory(history, NOW, Mock(get=Mock(return_value=response)))
        self.assertEqual(report['candidates'], [])

    def test_external_redirect_rejected(self):
        response = Mock(text=HTML, url='https://example.org/game/2026-2027/')
        response.raise_for_status.return_value = None
        with self.assertRaises(ValueError):
            inventory.build_inventory({'publication_log': []}, NOW, Mock(get=Mock(return_value=response)))

    def test_missing_section_rejected(self):
        with self.assertRaises(ValueError):
            inventory.parse_fixtures(HTML.replace('BELGIAN PRO LEAGUE', 'League'), NOW)

    def test_official_belgium_date_matches_jst_fixture(self):
        belgium = datetime(2026, 11, 1, 16, tzinfo=ZoneInfo('Europe/Brussels'))
        self.assertEqual(belgium.astimezone(inventory.JST).isoformat(), '2026-11-02T00:00:00+09:00')


    def test_uefa_fixture_is_discovered_from_actual_section(self):
        # On Nov 1, the Nov 6 European fixture enters the seven-day window.
        now = datetime(2026, 11, 1, 12, tzinfo=inventory.JST)
        fixtures = inventory.parse_uefa_fixtures(HTML, now)
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]['opponent'], 'SKブラン')
        self.assertEqual(fixtures[0]['competition'], 'UEFA Conference League')
        self.assertEqual(fixtures[0]['kickoff_jst'], '2026-11-06T05:00:00+09:00')

    def test_uefa_is_separate_from_league_and_never_approved(self):
        now = datetime(2026, 11, 1, 12, tzinfo=inventory.JST)
        response = Mock(text=HTML, url=URL)
        response.raise_for_status.return_value = None
        history = {'publication_log': [], 'pending_posts': {}, 'reserved_posts': {}}
        report = inventory.build_inventory(history, now, Mock(get=Mock(return_value=response)))
        self.assertEqual({x['competition'] for x in report['candidates']},
                         {'Belgian Pro League', 'UEFA Conference League'})
        self.assertEqual(len({x['fixture_id'] for x in report['candidates']}), 2)
        self.assertTrue(all(not x['can_publish'] and not x['reviewed']
                            for x in report['candidates']))

    def test_uefa_duplicate_identity_and_timezone_notice(self):
        now = datetime(2026, 11, 1, 12, tzinfo=inventory.JST)
        uefa = inventory.parse_uefa_fixtures(HTML, now)[0]
        response = Mock(text=HTML, url=URL)
        response.raise_for_status.return_value = None
        history = {'publication_log': [{'fixture_id': uefa['fixture_id']}]}
        report = inventory.build_inventory(history, now, Mock(get=Mock(return_value=response)))
        self.assertEqual([x['competition'] for x in report['candidates']],
                         ['Belgian Pro League'])
        with self.assertRaises(ValueError):
            inventory.parse_uefa_fixtures(
                HTML.replace('試合時間は日本時間の表記', 'Unspecified timezone'), now)

    def test_malformed_uefa_section_keeps_league_fixture_and_warns(self):
        # A partial official page must not suppress valid league evidence.
        broken = HTML.replace('KICKOFF HOME VS.SKブラン', 'TIME TBC HOME VS.SKブラン')
        now = datetime(2026, 11, 1, 12, tzinfo=inventory.JST)
        response = Mock(text=broken, url=URL)
        response.raise_for_status.return_value = None
        history = {'publication_log': [], 'pending_posts': {}, 'reserved_posts': {}}
        report = inventory.build_inventory(history, now, Mock(get=Mock(return_value=response)))
        self.assertEqual([x['competition'] for x in report['candidates']],
                         ['Belgian Pro League'])
        self.assertEqual(report['source_warnings'][0]['competition'],
                         'UEFA Conference League')
        self.assertEqual(report['source_warnings'][0]['status'], 'section_unavailable')
        self.assertTrue(all(not x['can_publish'] for x in report['candidates']))

    def test_both_competitions_have_no_warnings(self):
        now = datetime(2026, 11, 1, 12, tzinfo=inventory.JST)
        response = Mock(text=HTML, url=URL)
        response.raise_for_status.return_value = None
        history = {'publication_log': [], 'pending_posts': {}, 'reserved_posts': {}}
        report = inventory.build_inventory(history, now, Mock(get=Mock(return_value=response)))
        self.assertEqual(report['source_warnings'], [])
        self.assertEqual({x['competition'] for x in report['candidates']},
                         {'Belgian Pro League', 'UEFA Conference League'})

    def test_season_rollover(self):
        self.assertEqual(inventory.schedule_url(datetime(2027, 1, 2, tzinfo=inventory.JST)), URL)


if __name__ == '__main__':
    unittest.main()
