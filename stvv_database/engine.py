"""Plan minimal cell changes, reject ambiguity, and verify a separate read."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from .source import competition, opponent

SHEET_ID = '1ay64m2o495DTfldsiy9ElIyGSBHVSQJy4cDRW2Sxl54'
TABS = ('① 試合一覧', '② 得失点分析', '③ 試合の転換点', '④ 個人スタッツ',
        '⑤ 試合スタッツ', '⑥ 総合評価', '⑦ シーズン比較', '⑧ データ収集方針')
HEADERS = (
    ['試合ID', 'シーズン', '日付', '大会', '対戦相手', 'ホーム/アウェイ', '得点', '失点',
     '基本布陣', '監督', '公式ソースURL', '備考', '勝敗（自動）', '照合状況'],
    ['イベントID', '試合ID', '試合日（日本時間）', '対戦相手', '時間', '得点者'],
    ['試合ID', '時間', '選手・関与者', '分類', '事実・記録'],
    ['試合ID', '選手', '背番号', '出場分', '警告', '評価根拠', 'メモ'],
    ['試合ID', '対戦相手', '試合日', '得点', '失点', 'シュート', '枠内シュート',
     'パス本数', 'パス成功本数', 'パス成功率', '支配率', 'CK', 'ファウル', '出典URL', '確認状況'],
    ['STVV LAB｜総合評価'], ['指標', '2025/26', '2026/27'],
    ['項目', '扱い', '収集方法', '優先度', '備考'])


def value(cell):
    return next(iter(cell.get('userEnteredValue', {}).values()), None)


def effective(cell):
    return next(iter(cell.get('effectiveValue', {}).values()), None)


class Snapshot:
    def __init__(self, raw):
        if raw.get('spreadsheetId') != SHEET_ID:
            raise ValueError('Wrong spreadsheet ID')
        self.raw = raw
        self.sheets = {}
        self.props = {}
        for sheet in raw['sheets']:
            title = sheet['properties']['title']
            self.props[title] = sheet['properties']
            cells = {}
            for block in sheet.get('data', []):
                for row, data in enumerate(block.get('rowData', []), block.get('startRow', 0)):
                    for col, cell in enumerate(data.get('values', []), block.get('startColumn', 0)):
                        if cell:
                            cells[row, col] = cell
            self.sheets[title] = cells

    def cell(self, tab, row, col):
        return self.sheets[tab].get((row, col), {})

    def rows(self, tab):
        cells = self.sheets[tab]
        indexes = sorted({row for (row, col), c in cells.items() if row > 0 and
                          col == 0 and value(c) not in (None, '')})
        width = self.props[tab]['gridProperties']['columnCount']
        return [(row, [value(self.cell(tab, row, col)) for col in range(width)]) for row in indexes]

    def fingerprint(self):
        # Include values, formulas, notes, validation, formatting and structure. Exclude
        # volatile computed values; a fresh read must match before a write is sent.
        data = {t: {'properties': self.props[t], 'cells': [
            [row, col, {k: v for k, v in c.items() if k in
                        ('userEnteredValue', 'note', 'dataValidation', 'userEnteredFormat', 'chipRuns')}]
            for (row, col), c in sorted(self.sheets[t].items())
            if any(k in c for k in ('userEnteredValue', 'note', 'dataValidation', 'userEnteredFormat', 'chipRuns'))
        ]} for t in self.sheets}
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def minute(v):
    if type(v) in (int, float) and v == int(v):
        v = int(v)
    m = re.fullmatch(r'(\d+)(?:\+(\d+))?', str(v).replace(' ', ''))
    return int(m[1]) * 100 + int(m[2] or 0) if m else None


def audit(snapshot):
    if tuple(snapshot.sheets) != TABS:
        raise ValueError('The existing eight-tab structure changed')
    errors, warnings = [], []
    for tab, headers in zip(TABS, HEADERS):
        if [value(snapshot.cell(tab, 0, col)) for col in range(len(headers))] != headers:
            errors.append('Header changed: ' + tab)
        for (row, col), cell in snapshot.sheets[tab].items():
            if 'errorValue' in cell.get('effectiveValue', {}):
                errors.append(f'Formula error: {tab} R{row+1}C{col+1}')
    master = snapshot.rows(TABS[0])
    ids = {r[0] for _, r in master}
    dates = {r[0]: r[2] for _, r in master}
    counts = {}
    for i, tab in enumerate(TABS[:5]):
        rows = snapshot.rows(tab)
        counts[tab] = len(rows)
        keycol = 1 if i == 1 else 0
        seen = set()
        last_date = None
        last_time = {}
        for row, r in rows:
            key = tuple(r[:2]) if i == 3 else tuple(r[:5]) if i == 2 else r[0]
            if key in seen:
                errors.append(f'Duplicate record: {tab} R{row+1}')
            seen.add(key)
            if r[keycol] not in ids:
                errors.append(f'Orphan match ID: {tab} R{row+1}')
            day = r[2] if i in (0, 1) else dates.get(r[0])
            if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
                errors.append(f'Invalid date: {tab} R{row+1}')
            elif last_date and day > last_date:
                warnings.append(f'Date order: {tab} R{row+1}')
            last_date = day
            if i in (1, 2):
                tm = minute(r[4] if i == 1 else r[1])
                if tm is not None:
                    if tm < last_time.get(r[keycol], -1):
                        warnings.append(f'Event time order: {tab} R{row+1}')
                    last_time[r[keycol]] = tm
            if i == 4:
                m = next((rr for _, rr in master if rr[0] == r[0]), None)
                for col, source_col in [(1, 4), (2, 2), (3, 6), (4, 7)]:
                    if not snapshot.cell(tab, row, col).get('userEnteredValue', {}).get('formulaValue'):
                        errors.append(f'Missing lookup formula: {tab} R{row+1}C{col+1}')
                    if m and effective(snapshot.cell(tab, row, col)) != m[source_col]:
                        errors.append(f'Lookup mismatch: {tab} R{row+1}C{col+1}')
    # Independently count results, including the workbook's explicit PK exception.
    selected = value(snapshot.cell(TABS[5], 1, 1))
    results = [effective(snapshot.cell(TABS[0], row, 12)) for row, r in master if r[1] == selected]
    for row, expected in [(4, sum(v in ('勝', '分', '負') for v in results)),
                          (5, results.count('勝')), (6, results.count('分')), (7, results.count('負'))]:
        if effective(snapshot.cell(TABS[5], row, 1)) != expected:
            errors.append(f'Aggregate mismatch: {TABS[5]} R{row+1}C2')
    for season_col, season in [(1, '2025/26'), (2, '2026/27')]:
        expected = sum(effective(snapshot.cell(TABS[0], row, 12)) in ('勝', '分', '負')
                       for row, r in master if r[1] == season)
        if effective(snapshot.cell(TABS[6], 1, season_col)) != expected:
            errors.append(f'Season count mismatch: {season}')
    return {'counts': counts, 'errors': sorted(set(errors)), 'warnings': sorted(set(warnings))}


@dataclass
class Change:
    tab: str
    row: int
    col: int
    field: str
    before: object
    after: object
    reason: str

    def request(self, snapshot):
        if self.field not in ('userEnteredValue', 'note'):
            raise ValueError('Unsupported write field')
        cell = snapshot.cell(self.tab, self.row, self.col)
        if self.field == 'userEnteredValue' and (cell.get('chipRuns') or
                cell.get('userEnteredValue', {}).get('formulaValue')):
            raise ValueError('Refusing to overwrite an existing formula or chip')
        content = self.after
        if self.field == 'userEnteredValue':
            content = {'numberValue': content} if type(content) in (int, float) else {'stringValue': content}
        return {'updateCells': {'range': {
            'sheetId': snapshot.props[self.tab]['sheetId'],
            'startRowIndex': self.row, 'endRowIndex': self.row+1,
            'startColumnIndex': self.col, 'endColumnIndex': self.col+1},
            'rows': [{'values': [{self.field: content}]}], 'fields': self.field}}


def plan(snapshot, matches, heartbeat=False):
    review = audit(snapshot)
    if review['errors']:
        raise ValueError('Workbook preflight failed: ' + '; '.join(review['errors']))
    changes, pending, checked = [], [], 0
    grouped = {}
    for match in matches:
        grouped.setdefault(match.key, []).append(match)
    for row, r in snapshot.rows(TABS[0]):
        if r[1] not in ('2025/26', '2026/27'):
            continue
        key = r[1], r[2], opponent(r[4]), r[5], competition(r[3])
        found = grouped.get(key, [])
        if len(found) != 1:
            pending.append({'match_id': r[0], 'reason': 'official_identity_not_unique_or_not_found'})
            continue
        match = found[0]
        checked += 1
        if match.goals_for is None:
            if r[6] is not None or r[7] is not None:
                pending.append({'match_id': r[0], 'reason': 'source_has_no_result_existing_result_retained'})
            continue
        proposed = []
        for col, target in [(6, match.goals_for), (7, match.goals_against)]:
            current = r[col]
            if current == target:
                continue
            if current is not None:
                pending.append({'match_id': r[0], 'reason': 'official_result_conflicts_with_existing_value'})
                proposed = []
                break
            proposed.append(Change(TABS[0], row, col, 'userEnteredValue', None, target, 'official_result'))
        else:
            if proposed:
                # Do not fill only half of a score when its partner conflicts or is a formula.
                if any(snapshot.cell(TABS[0], row, c).get('userEnteredValue', {}).get('formulaValue') for c in (6, 7)):
                    pending.append({'match_id': r[0], 'reason': 'result_cell_is_formula'})
                    continue
                sources = str(r[10] or '').splitlines()
                if match.url not in sources:
                    new_urls = '\n'.join(filter(None, sources + [match.url]))
                    proposed.append(Change(TABS[0], row, 10, 'userEnteredValue', r[10], new_urls, 'source_url'))
                marker = f'自動照合：{match.day} {match.goals_for}-{match.goals_against}（STVV公式日程）。'
                new_memo = '\n'.join(filter(None, [r[11], marker]))
                proposed.append(Change(TABS[0], row, 11, 'userEnteredValue', r[11], new_memo, 'evidence'))
                if r[13] != '照合済み':
                    allowed = snapshot.cell(TABS[0], row, 13).get('dataValidation', {}).get('condition', {})
                    options = [v.get('userEnteredValue') for v in allowed.get('values', [])]
                    if allowed.get('type') == 'ONE_OF_LIST' and '照合済み' not in options:
                        raise ValueError('Confirmation status violates live validation')
                    proposed.append(Change(TABS[0], row, 13, 'userEnteredValue', r[13], '照合済み', 'status'))
                # A literal PK result is an intentional exception. A new result must
                # have the existing automatic W/D/L formula before it can be filled.
                if not snapshot.cell(TABS[0], row, 12).get('userEnteredValue', {}).get('formulaValue'):
                    pending.append({'match_id': r[0], 'reason': 'new_result_has_no_outcome_formula'})
                    continue
                changes.extend(proposed)
    existing = {(r[1], r[2], opponent(r[4]), r[5], competition(r[3]))
                for _, r in snapshot.rows(TABS[0])}
    for match in matches:
        if match.key not in existing and match.goals_for is not None:
            pending.append({'source_date': match.day, 'reason': 'unregistered_official_match_needs_id_mapping'})
    if heartbeat:
        rows = [(row, r) for row, r in snapshot.rows(TABS[7]) if r[0] == '復旧確認（2026-10-22）']
        if len(rows) != 1:
            raise ValueError('Cannot identify the authorised operations note cell')
        row = rows[0][0]
        stamp = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
        changes.append(Change(TABS[7], row, 4, 'note', snapshot.cell(TABS[7], row, 4).get('note'),
                              f'コード更新エンジンの書込テスト {stamp}。値・数式・書式は維持。成功判定は別読込で実施。',
                              'write_test'))
    return changes, {'checked_matches': checked, 'pending': pending, 'audit': review}


def verify(before, after, changes):
    expected = {(c.tab, c.row, c.col, c.field): c for c in changes}
    for c in changes:
        cell = after.cell(c.tab, c.row, c.col)
        actual = value(cell) if c.field == 'userEnteredValue' else cell.get(c.field)
        if actual != c.after:
            raise ValueError(f'Write not reflected: {c.tab} R{c.row+1}C{c.col+1}')
    # Every unrelated literal, formula, note, format and validation must survive.
    if tuple(before.sheets) != tuple(after.sheets) or before.props != after.props:
        raise ValueError('Unexpected workbook structure change')
    for tab in before.sheets:
        for coord in set(before.sheets[tab]) | set(after.sheets[tab]):
            for field in ('userEnteredValue', 'note', 'dataValidation', 'userEnteredFormat', 'chipRuns'):
                if (tab, *coord, field) in expected:
                    continue
                if before.cell(tab, *coord).get(field) != after.cell(tab, *coord).get(field):
                    # Google may canonicalise an explicit single-URL link into
                    # its automatic hyperlink representation after restoration.
                    # Accept only the exact unchanged URL with the same resolved
                    # link, never the loss of a link or any other format change.
                    old, new = before.cell(tab, *coord), after.cell(tab, *coord)
                    uri = old.get('userEnteredFormat', {}).get('textFormat', {}).get('link', {}).get('uri')
                    if (field == 'userEnteredFormat' and uri and
                            old.get(field) == {'textFormat': {'link': {'uri': uri}}} and not new.get(field) and
                            value(old) == value(new) == uri and new.get('hyperlink') == uri and
                            new.get('effectiveFormat', {}).get('textFormat', {}).get('link', {}).get('uri') == uri):
                        continue
                    raise ValueError(f'Unexpected change: {tab} R{coord[0]+1}C{coord[1]+1} {field}')
    review = audit(after)
    if review['errors']:
        raise ValueError('Post-write validation failed: ' + '; '.join(review['errors']))
    return review
