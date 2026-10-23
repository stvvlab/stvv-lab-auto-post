"""Conservative, idempotent enrichment of existing records with cell-level evidence."""
from collections import defaultdict

from .engine import Change, TABS, minute, value
from .reports import player
from .source import competition, opponent


def inventory(snapshot):
    finished = {r[0] for _, r in snapshot.rows(TABS[0]) if type(r[6]) in (int, float)
                and type(r[7]) in (int, float)}
    sections = {}
    for tab_i, fields in [(1, {5: 'scorer'}), (3, {2: 'shirt_number', 3: 'minutes', 4: 'cards'}),
                           (4, {5: 'shots', 6: 'shots_on_target', 7: 'passes', 8: 'completed_passes',
                                10: 'possession', 11: 'corners', 12: 'fouls'})]:
        rows = [r for _, r in snapshot.rows(TABS[tab_i]) if r[1 if tab_i == 1 else 0] in finished]
        sections[TABS[tab_i]] = {'recorded_rows': len(rows), 'missing_cells': {
            name: sum(r[col] in (None, '') for r in rows) for col, name in fields.items()},
            'missing_match_rows': len(finished - {r[1 if tab_i == 1 else 0] for r in rows})}
    return {'finished_matches': len(finished), 'tabs': sections}


def enrich(snapshot, reports):
    grouped = defaultdict(list)
    for report in reports:
        grouped[report.key].append(report)
    planned, pending, matched = {}, [], 0

    def change(tab, row, col, field, after, reason):
        key = tab, row, col, field
        cell = snapshot.cell(tab, row, col)
        before = value(cell) if field == 'userEnteredValue' else cell.get(field)
        if before == after:
            return
        if field == 'userEnteredValue':
            if cell.get('chipRuns') or cell.get('userEnteredValue', {}).get('formulaValue'):
                raise ValueError('Enrichment target contains formula or chip')
            condition = cell.get('dataValidation', {}).get('condition', {})
            if condition and (condition.get('type') != 'ONE_OF_LIST' or
                    str(after) not in [v.get('userEnteredValue') for v in condition.get('values', [])]):
                raise ValueError('Enrichment violates live cell validation')
        if key in planned and planned[key].after != after:
            raise ValueError('Conflicting enrichment cell proposals')
        planned[key] = Change(tab, row, col, field, before, after, reason)

    def evidence(tab, row, col, report):
        old = snapshot.cell(tab, row, col).get('note', '')
        marker = f'STVV公式戦評：{report.url}\n取得内容SHA256：{report.digest}'
        if marker not in old:
            change(tab, row, col, 'note', '\n'.join(filter(None, [old, marker])), 'club_report_evidence')

    for _, master in snapshot.rows(TABS[0]):
        match_id = master[0]
        key = master[1], master[2], opponent(master[4]), master[5], competition(master[3])
        candidates = grouped.get(key, [])
        if not candidates:
            continue
        # Different articles must agree; narrative never resolves a discrepancy.
        signatures = {(r.goals, r.appearances) for r in candidates}
        if len(signatures) != 1:
            pending.append({'match_id': match_id, 'reason': 'official_reports_disagree'})
            continue
        report = candidates[0]
        if [sum(g[0] == side for g in report.goals) for side in ('得点', '失点')] != master[6:8]:
            pending.append({'match_id': match_id, 'reason': 'report_conflicts_with_workbook_score'})
            continue
        matched += 1
        rows = [(row, r) for row, r in snapshot.rows(TABS[1]) if r[1] == match_id]
        for side, tm, scorer in report.goals:
            possible = [(row, r) for row, r in rows if r[15] == side and minute(r[4]) == minute(tm)]
            # A repeated same-minute score cannot be assigned to one row safely.
            if len(possible) != 1 or sum(g[0] == side and minute(g[1]) == minute(tm)
                                          for g in report.goals) != 1:
                pending.append({'match_id': match_id, 'reason': 'goal_row_or_time_requires_review',
                                'side': side, 'minute': tm})
                continue
            row, r = possible[0]
            if r[5] not in (None, ''):
                if player(r[5]) != player(scorer):
                    pending.append({'match_id': match_id, 'reason': 'existing_scorer_conflicts', 'row': row+1})
                continue
            change(TABS[1], row, 5, 'userEnteredValue', scorer, 'official_scorer')
            urls = list(filter(None, str(r[13] or '').splitlines()))
            if report.url not in urls:
                change(TABS[1], row, 13, 'userEnteredValue', '\n'.join(urls+[report.url]), 'source_url')
            evidence(TABS[1], row, 5, report)
        personal = [(row, r) for row, r in snapshot.rows(TABS[3]) if r[0] == match_id]
        for name, role in report.appearances:
            possible = [(row, r) for row, r in personal if player(r[1]) == player(name)]
            if len(possible) != 1:
                pending.append({'match_id': match_id, 'reason': 'appearance_row_requires_registration', 'player': name})
                continue
            row, r = possible[0]
            marker = f'公式メンバー表：{role}。出場分数・警告数は推定しない。'
            if marker not in str(r[6] or ''):
                change(TABS[3], row, 6, 'userEnteredValue', '\n'.join(filter(None, [r[6], marker])), 'official_appearance')
                urls = list(filter(None, str(r[5] or '').splitlines()))
                if report.url not in urls:
                    change(TABS[3], row, 5, 'userEnteredValue', '\n'.join(urls+[report.url]), 'source_url')
                evidence(TABS[3], row, 6, report)
    return list(planned.values()), {'report_matches': matched, 'report_pending': pending}
