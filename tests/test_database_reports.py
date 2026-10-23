import copy
from dataclasses import replace
import unittest

from test_database import cell, fixture, match
from stvv_database.backfill import enrich, inventory
from stvv_database.engine import Snapshot, TABS, verify
from stvv_database.reports import collect_reports, parse_report, player

URL = 'https://stvv.jp/news/uefa-news/20261016_1/'
HTML = '''<p class="day">2026.10.16</p><div class="article_content">
<h3>UEFAカンファレンスリーグ イベリア1999トビリシ戦（H）</h3>
<p>10月16日(金) 4時00分</p><p>結果：2-0</p><p>得点</p>
<p>STVV：選手A（12分）、選手B（88分）</p>
<h4>【先発】</h4><p>GK/選手GK</p><p>DF/畑、選手DF1、選手DF2、選手DF3</p>
<p>MF/選手MF1、選手MF2、選手MF3</p><p>FW/選手A（新川 79分）、選手B、選手FW</p>
<h4>トピック</h4><p>90分に選手Bの得点を振り返る。</p></div>'''


def snapshot():
    raw = fixture()
    row = raw['sheets'][0]['data'][0]['rowData'][1]['values']
    row[6], row[7] = cell(2), cell(0)
    row[10] = cell(URL)
    goals = raw['sheets'][1]['data'][0]['rowData']
    for i, tm in enumerate([12, 88]):
        values = [cell(f'2627-E03-GF0{i+1}'), cell('2627-E03'), cell('2026-10-16'), cell('イベリア1999トビリシ'), cell(tm)]
        values += [{} for _ in range(10)] + [cell('得点')]
        goals.append({'values': values})
    raw['sheets'][3]['data'][0]['rowData'].append({'values': [cell('2627-E03'), cell('畑大雅')]})
    return Snapshot(raw)


class ReportTests(unittest.TestCase):
    def test_reviewed_player_labels_only(self):
        self.assertEqual(player('ヴァンウェセマール（背番号60）'),player('ヴァンウェセマール'))
        self.assertEqual(player('セヴァウィ'),player('セヴァウイ'))
        self.assertEqual(player('OG'),player('オウンゴール'))
        self.assertNotEqual(player('別選手（主将）'),player('別選手'))
    def test_explicit_list_only_and_no_inferred_minutes(self):
        r = parse_report(HTML, match(), URL)
        self.assertEqual(r.goals, (('得点', '12', '選手A'), ('得点', '88', '選手B')))
        self.assertIn(('新川', '途中出場（公式交代時刻79分）'), r.appearances)
        self.assertEqual(len([a for a in r.appearances if a[1] == '先発']), 11)

    def test_wrong_identity_score_year_and_incomplete_goals_rejected(self):
        for html in [HTML.replace('戦（H）', '戦（A）'), HTML.replace('結果：2-0', '結果：3-0'),
                     HTML.replace('2026.10.16', '2025.10.16'), HTML.replace('10月16日', '10月15日'),
                     HTML.replace('選手B（88分）', '不明')]:
            with self.subTest(html=html):
                with self.assertRaises(ValueError):
                    parse_report(html, match(), URL)

    def test_away_score_retains_stvv_perspective(self):
        r = parse_report(HTML.replace('戦（H）', '戦（A）').replace('結果：2-0', '結果：0-2'), replace(match(), venue='AWAY'), URL)
        self.assertEqual(r.goals[0][0], '得点')

    def test_multiple_goals_in_one_name_and_zero_goal_blank(self):
        html = HTML.replace('選手A（12分）、選手B（88分）', '選手A（12分、88分）').replace('<h4>【先発】', '<p>イベリア1999トビリシ：</p><h4>【先発】')
        self.assertEqual(parse_report(html, match(), URL).goals,
                         (('得点','12','選手A'),('得点','88','選手A')))

    def test_minute_before_substitute_name(self):
        r = parse_report(HTML.replace('新川 79分', '79分 新川'), match(), URL)
        self.assertIn(('新川','途中出場（公式交代時刻79分）'),r.appearances)

    def test_legacy_br_separated_summary_and_pk_annotation(self):
        html = HTML.replace('</p><p>結果', '<br>結果').replace('</p><p>得点', '<br>得点')
        html = html.replace('</p>\n<p>STVV', '<br>STVV').replace('選手A（12分）', '選手A（12分 PK）')
        self.assertEqual(parse_report(html, match(), URL).goals[0], ('得点', '12', '選手A'))

    def test_blank_result_requires_complete_scorer_lists(self):
        html = HTML.replace('結果：2-0', '結果：')
        self.assertEqual(len(parse_report(html, match(), URL).goals), 2)
        with self.assertRaises(ValueError):
            parse_report(html.replace('選手A（12分）、', ''), match(), URL)

    def test_pk_result_preserves_regulation_goal_lists(self):
        html = HTML.replace('結果：2-0','結果：2-2（PK4-3）').replace('<h4>【先発】',
            '<p>イベリア1999トビリシ：相手A（20分）、相手B（40分）</p><h4>【先発】')
        self.assertEqual(len(parse_report(html, match(2,2), URL).goals), 4)

    def test_bad_lineup_is_reported_without_discarding_valid_goals(self):
        for html in [HTML.replace('選手DF3','畑'),HTML.replace('新川 79分','新川⇒別選手 79分')]:
            r=parse_report(html,match(),URL)
            self.assertTrue(r.lineup_issue)
            self.assertEqual(r.appearances,())
            self.assertEqual(len(r.goals),2)

    def test_legacy_away_stvv_first_result_requires_labelled_goal_totals(self):
        html=HTML.replace('戦（H）','戦（A）')
        self.assertEqual(len(parse_report(html,replace(match(),venue='AWAY'),URL).goals),2)
        with self.assertRaises(ValueError):
            parse_report(html.replace('選手B（88分）','不明'),replace(match(),venue='AWAY'),URL)

    def test_minutes_with_repeated_unit_and_pk_prefix(self):
        html = HTML.replace('12分','45分+6分').replace('88分','PK88分')
        self.assertEqual([g[1] for g in parse_report(html, match(), URL).goals], ['45+6','88'])

    def test_discovers_registered_goal_source_without_master_url(self):
        before = snapshot()
        before.sheets[TABS[0]][1,10] = cell('https://stvv.jp/')
        before.sheets[TABS[1]][1,13] = cell(URL)
        reports, issues = collect_reports(before, [match()], read=lambda u: HTML)
        self.assertEqual(len(reports),1)
        self.assertEqual(issues,[])

    def test_single_url_format_is_kept_and_note_remains_discoverable(self):
        before=snapshot()
        before.sheets[TABS[0]][1,10]=cell('https://stvv.jp/')
        before.sheets[TABS[1]][1,13]={**cell('https://www.proleague.be/old/'),
            'userEnteredFormat':{'textFormat':{'link':{'uri':'https://www.proleague.be/old/'}}}}
        report=parse_report(HTML,match(),URL)
        changes,_=enrich(before,[report])
        self.assertFalse(any(c.tab==TABS[1] and c.row==1 and c.col==13 for c in changes))
        proof=next(c for c in changes if c.tab==TABS[1] and c.row==1 and c.field=='note')
        before.sheets[TABS[1]][1,5]={'note':proof.after}
        reports,_=collect_reports(before,[match()],read=lambda u:HTML)
        self.assertEqual(len(reports),1)

    def test_google_link_canonicalisation_requires_same_url_and_effective_link(self):
        from test_database import fixture
        raw=fixture();uri='https://stvv.jp/'
        target=raw['sheets'][0]['data'][0]['rowData'][1]['values'][10]
        target['userEnteredValue']={'stringValue':uri}
        target['userEnteredFormat']={'textFormat':{'link':{'uri':uri}}}
        before=Snapshot(copy.deepcopy(raw))
        del target['userEnteredFormat']
        target['hyperlink']=uri
        target['effectiveFormat']={'textFormat':{'link':{'uri':uri}}}
        verify(before,Snapshot(raw),[])
        target['hyperlink']='https://wrong.example/'
        with self.assertRaises(ValueError):verify(before,Snapshot(raw),[])

    def test_fill_missing_scorer_preserve_formulas_and_no_cards_or_minutes(self):
        before = snapshot()
        changes, info = enrich(before, [parse_report(HTML, match(), URL)])
        scorers = [c.after for c in changes if c.tab == TABS[1] and c.col == 5 and c.field == 'userEnteredValue']
        self.assertEqual(scorers, ['選手A', '選手B'])
        self.assertFalse(any(c.tab == TABS[3] and c.col in (2, 3, 4) for c in changes))
        self.assertTrue(info['report_pending'])  # missing appearances remain explicit
        self.assertTrue(all(c.request(before)['updateCells']['fields'] in ('note','userEnteredValue') for c in changes))
        raw = copy.deepcopy(before.raw)
        for c in changes:
            target = next(s for s in raw['sheets'] if s['properties']['title'] == c.tab)['data'][0]['rowData'][c.row]
            while len(target['values']) <= c.col:
                target['values'].append({})
            target['values'][c.col][c.field] = cell(c.after)['userEnteredValue'] if c.field == 'userEnteredValue' else c.after
        self.assertEqual(enrich(Snapshot(raw), [parse_report(HTML, match(), URL)])[0], [])

    def test_conflicting_name_and_time_never_overwritten(self):
        before = snapshot()
        before.sheets[TABS[1]][1,5] = cell('既存の別選手')
        changes, info = enrich(before, [parse_report(HTML.replace('88分', '89分'), match(), URL)])
        self.assertFalse(any(c.tab == TABS[1] for c in changes))
        self.assertEqual(len([p for p in info['report_pending'] if p['reason'] in
                            ('existing_scorer_conflicts','goal_row_or_time_requires_review')]), 2)

    def test_multiple_official_reports_must_agree(self):
        a = parse_report(HTML, match(), URL)
        b = parse_report(HTML.replace('88分','89分'), match(), URL)
        changes, info = enrich(snapshot(), [a,b])
        self.assertEqual(changes, [])
        self.assertEqual(info['report_pending'][0]['reason'], 'official_reports_disagree')

    def test_collection_failure_is_reported_and_not_empty_success(self):
        def unavailable(url):
            raise TimeoutError()
        reports, issues = collect_reports(snapshot(), [match()], read=unavailable)
        self.assertEqual(reports, [])
        self.assertEqual(issues[0]['reason'], 'TimeoutError')

    def test_inventory_excludes_unplayed_matches(self):
        result = inventory(snapshot())
        self.assertEqual(result['finished_matches'], 1)
        self.assertEqual(result['tabs'][TABS[1]]['missing_cells']['scorer'], 2)


if __name__ == '__main__':
    unittest.main()
