import copy
from datetime import date
import unittest
from unittest.mock import patch

from stvv_database.engine import (HEADERS, SHEET_ID, TABS, Change, Snapshot,
                                  audit, plan, verify)
from stvv_database.source import Match, fetch, opponent, parse_schedule, parse_uefa_stats


def cell(v, formula=False):
    return {'userEnteredValue': {'formulaValue' if formula else 'numberValue' if type(v) is int else 'stringValue': v},
            **({} if formula else {'effectiveValue': {'numberValue' if type(v) is int else 'stringValue': v}})}


def fixture():
    raw = {'spreadsheetId': SHEET_ID, 'sheets': []}
    for index, (tab, headers) in enumerate(zip(TABS, HEADERS)):
        raw['sheets'].append({'properties': {'title': tab, 'sheetId': index,
            'gridProperties': {'rowCount': 100, 'columnCount': 27}},
            'data': [{'rowData': [{'values': [cell(v) for v in headers]}]}]})
    def row(i, values):
        raw['sheets'][i]['data'][0]['rowData'].append({'values': values})
    row(0, [cell(v) if v is not None else {} for v in
        ['2627-E03', '2026/27', '2026-10-16', 'UEFAカンファレンスリーグ', 'イベリア1999トビリシ',
         'HOME', None, None, None, None, 'https://stvv.jp/', 'Existing memo', '=IF(G2>H2,"勝","負")', '要照合']])
    r = raw['sheets'][0]['data'][0]['rowData'][1]['values']
    r[12] = cell('=IF(G2>H2,"勝","負")', True)
    r[13]['dataValidation'] = {'condition': {'type': 'ONE_OF_LIST', 'values': [{'userEnteredValue': '照合済み'}]}}
    # Set aggregate cells at their actual positions.
    rows = raw['sheets'][5]['data'][0]['rowData']
    while len(rows) < 8:
        rows.append({'values': []})
    rows[1] = {'values': [cell('評価対象シーズン'), cell('2026/27')]}
    for n in (4, 5, 6, 7):
        rows[n] = {'values': [cell('label'), cell(0)]}
    raw['sheets'][6]['data'][0]['rowData'].append({'values': [cell('記録済み試合数'), cell(0), cell(0)]})
    row(7, [cell('復旧確認（2026-10-22）'), {}, {}, {}, cell('Keep this')])
    return raw


def match(gf=2, ga=0):
    return Match('2026/27', '2026-10-16', 'conference', 'イベリア1999トビリシ',
                 'HOME', gf, ga, 'https://stvv.jp/game/2026-2027/', 'digest')


HTML = '''<div class="container--content"><div class="game__title">UEFAカンファレンスリーグ</div>
<div class="game__body-contents"><div class="txt"><p><span>第1節</span>2026</p><p>10.16</p><p>04:00 KICKOFF</p></div>
<p class="vs"><span class="hw">HOME</span>VS.イベリア1999トビリシ</p>
<ul class="vs-team"><li>2<span>シント＝トロイデンVV</span></li><li>VS</li><li>0<span>イベリア1999トビリシ</span></li></ul>
</div></div>'''


class SourceTests(unittest.TestCase):
    def test_reviewed_club_aliases_only(self):
        self.assertEqual(opponent('ヘンク'), opponent('ゲンク'))
        self.assertNotEqual(opponent('クラブ・ブルージュ'), opponent('サークル・ブルージュ'))

    def test_realistic_home_score(self):
        m = parse_schedule(HTML, '2026/27', 'https://stvv.jp/game/2026-2027/', date(2026, 10, 22))[0]
        self.assertEqual((m.goals_for, m.goals_against, m.venue), (2, 0, 'HOME'))

    def test_away_score_is_from_stvv_perspective(self):
        html = HTML.replace('HOME', 'AWAY').replace('2<span>シント＝トロイデンVV', '3<span>イベリア1999トビリシ').replace('0<span>イベリア1999トビリシ', '4<span>シント＝トロイデンVV')
        m = parse_schedule(html, '2026/27', 'https://stvv.jp/game/2026-2027/', date(2026, 10, 22))[0]
        self.assertEqual((m.goals_for, m.goals_against), (4, 3))

    def test_pending_score_is_not_zero_zero(self):
        html = HTML.replace('2<span>', '-<span>').replace('0<span>', '-<span>')
        self.assertIsNone(parse_schedule(html, '2026/27', 'url', date(2026, 10, 22))[0].goals_for)

    def test_wrong_team_date_layout_and_partial_results_are_rejected(self):
        for html, today in [(HTML.replace('シント＝トロイデンVV', 'Other'), date(2026, 10, 22)),
                            (HTML, date(2026, 10, 15)),
                            (HTML.replace('0<span>', '-<span>'), date(2026, 10, 22)),
                            (HTML.replace('10.16', '10/16'), date(2026, 10, 22)),
                            ('<html>maintenance</html>', date(2026, 10, 22))]:
            with self.subTest(html=html):
                with self.assertRaises(ValueError):
                    parse_schedule(html, '2026/27', 'url', today)

    def test_duplicate_source_blocks_rejected(self):
        with self.assertRaises(ValueError):
            parse_schedule(HTML + HTML, '2026/27', 'url', date(2026, 10, 22))

    def test_no_external_or_redirect_requests(self):
        with patch('stvv_database.source.requests.get') as get:
            with self.assertRaises(ValueError):
                fetch('https://evil.invalid/')
            get.assert_not_called()
            get.return_value.is_redirect = True
            get.return_value.headers = {'Location': 'https://evil.invalid/'}
            with self.assertRaises(ValueError):
                fetch('https://stvv.jp/')
            self.assertEqual(get.call_count, 1)

    def test_uefa_missing_stats_remain_unknown(self):
        stats = parse_uefa_stats('<p>1 Matches played 125.86 Distance covered (km) 1 Attempts conceded on target</p>')
        self.assertEqual(stats['distance_km'], 125.86)
        self.assertIsNone(parse_uefa_stats('<script>1 Matches played</script>')['matches_played'])


class EngineTests(unittest.TestCase):
    def test_missing_result_filled_with_source_and_live_validation(self):
        snap = Snapshot(fixture())
        changes, info = plan(snap, [match()])
        self.assertEqual([c.after for c in changes if c.col in (6, 7)], [2, 0])
        self.assertTrue(all(c.request(snap)['updateCells']['fields'] == 'userEnteredValue' for c in changes))
        self.assertEqual(info['checked_matches'], 1)

    def test_conflicting_half_score_never_partially_writes(self):
        raw = fixture()
        raw['sheets'][0]['data'][0]['rowData'][1]['values'][7] = cell(3)
        changes, info = plan(Snapshot(raw), [match()])
        self.assertEqual(changes, [])
        self.assertTrue(info['pending'])

    def test_no_source_result_does_not_erase_existing(self):
        changes, _ = plan(Snapshot(fixture()), [match(None, None)])
        self.assertEqual(changes, [])

    def test_matched_result_is_idempotent_and_keeps_pk_literal(self):
        raw = fixture()
        r = raw['sheets'][0]['data'][0]['rowData'][1]['values']
        r[6], r[7], r[12] = cell(2), cell(0), cell('負')
        for row, n in [(4, 1), (5, 0), (6, 0), (7, 1)]:
            raw['sheets'][5]['data'][0]['rowData'][row]['values'][1] = cell(n)
        raw['sheets'][6]['data'][0]['rowData'][1]['values'][2] = cell(1)
        self.assertEqual(plan(Snapshot(raw), [match()])[0], [])

    def test_validation_block(self):
        raw = fixture()
        raw['sheets'][0]['data'][0]['rowData'][1]['values'][13]['dataValidation']['condition']['values'] = []
        with self.assertRaises(ValueError):
            plan(Snapshot(raw), [match()])

    def test_duplicate_id_and_missing_tab_prevent_updates(self):
        raw = fixture()
        raw['sheets'][0]['data'][0]['rowData'].append(copy.deepcopy(raw['sheets'][0]['data'][0]['rowData'][1]))
        with self.assertRaises(ValueError):
            plan(Snapshot(raw), [match()])
        raw = fixture()
        raw['sheets'].pop()
        with self.assertRaises(ValueError):
            plan(Snapshot(raw), [match()])

    def test_separate_read_verification_detects_missing_write(self):
        before = Snapshot(fixture())
        changes, _ = plan(before, [], heartbeat=True)
        with self.assertRaises(ValueError):
            verify(before, Snapshot(copy.deepcopy(before.raw)), changes)

    def test_note_test_preserves_values_and_rejects_unrelated_formula_change(self):
        raw = fixture()
        before = Snapshot(copy.deepcopy(raw))
        changes, _ = plan(before, [], heartbeat=True)
        change = changes[0]
        raw['sheets'][7]['data'][0]['rowData'][1]['values'][4]['note'] = change.after
        verify(before, Snapshot(raw), changes)
        raw['sheets'][0]['data'][0]['rowData'][1]['values'][12]['userEnteredValue']['formulaValue'] = '=1'
        with self.assertRaises(ValueError):
            verify(before, Snapshot(raw), changes)

    def test_concurrent_edit_changes_fingerprint(self):
        raw = fixture()
        before = Snapshot(copy.deepcopy(raw))
        raw['sheets'][0]['data'][0]['rowData'][1]['values'][11] = cell('User edit')
        self.assertNotEqual(before.fingerprint(), Snapshot(raw).fingerprint())


if __name__ == '__main__':
    unittest.main()
