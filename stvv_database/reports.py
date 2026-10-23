"""Read explicit club report fields. Never calculate minutes or infer absent cards."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import re

from bs4 import BeautifulSoup

from .source import clean, fetch, opponent

REPORT_URL = re.compile(r'https://stvv\.jp/news/(?:game|uefa-news)/[^?#]+/')
PLAYER_ALIASES = {'畑': '畑大雅', '高井': '高井幸大', '谷口': '谷口彰悟',
                  '小久保': '小久保玲央ブライアン', '石渡': '石渡ネルソン',
                  '松澤': '松澤海斗', '新川': '新川志音', '荒木': '荒木遼太郎',
                  '伊藤': '伊藤涼太郎', '山本': '山本理仁', '後藤': '後藤啓介', 'ピュぺ': 'ピュペ',
                  'セヴァウィ': 'セヴァウイ', 'OG': 'オウンゴール'}


def player(name):
    name = re.sub(r'\(背番号\d+\)$', '', clean(name))
    return PLAYER_ALIASES.get(name, name)


@dataclass(frozen=True)
class ClubReport:
    key: tuple
    url: str
    digest: str
    goals: tuple  # (得点/失点, minute string, scorer), explicit score lists only
    appearances: tuple  # (name, role); no derived playing minutes
    lineup_issue: str | None = None


def parse_report(html, match, url):
    if not REPORT_URL.fullmatch(url):
        raise ValueError('Unapproved club report URL')
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('.article_content')
    if not article:
        raise ValueError('Official report article layout changed')
    # Bind identity only within the report summary, before highlights/narrative.
    for br in article.select('br'):
        br.replace_with('\n')
    paragraphs = [clean(line) for p in article.find_all(['h3', 'h4', 'p'])
                  for line in p.get_text('', strip=False).splitlines() if clean(line)]
    # Some older articles put the heading label and the first team on one line.
    paragraphs = [re.sub(r'^得点:', '', text) if text.startswith('得点:') and text != '得点:' else text
                  for text in paragraphs]
    summary = []
    for text in paragraphs:
        if '先発' in text or 'ハイライト' in text or 'トピック' in text:
            break
        summary.append(text)
    heading = [x for x in summary if re.search(r'戦\([HA]\)', x)]
    if len(heading) != 1:
        raise ValueError('Official report identity heading ambiguous')
    side = 'H' if match.venue == 'HOME' else 'A'
    from .source import ALIASES
    labels = {match.opponent, opponent(match.opponent)} | {
        k for k, v in ALIASES.items() if v == opponent(match.opponent)}
    if not any(heading[0].endswith(label + f'戦({side})') for label in labels):
        raise ValueError('Official report opponent or venue mismatch')
    day = date.fromisoformat(match.day)
    if not any(x.startswith(f'{day.month}月{day.day}日') for x in summary):
        raise ValueError('Official report match date mismatch')
    # Publication dates may differ by a day, but the year must be explicit.
    published = soup.select_one('p.day')
    stamp = re.fullmatch(r'(20\d{2})\.(\d{1,2})\.(\d{1,2})', clean(published.get_text()) if published else '')
    if not stamp or abs((date(*map(int, stamp.groups())) - day).days) > 3:
        raise ValueError('Official report publication date missing or inconsistent')
    result = [x for x in summary if x.startswith('結果:')]
    home, away = ((match.goals_for, match.goals_against) if match.venue == 'HOME' else
                  (match.goals_against, match.goals_for))
    # A blank template result is not a conflicting result. In that case BOTH
    # explicit scorer lists must account for the schedule's entire score below.
    # Some legacy reports display STVV-first even for away matches. The labelled
    # scorer lists below independently bind both goal totals to the right teams.
    orientations = {f'{home}-{away}', f'{match.goals_for}-{match.goals_against}'}
    if result != ['結果:'] and not (len(result) == 1 and any(
            result[0] == f'結果:{score}' or (home == away and re.fullmatch(
                rf'結果:{score}\(PK\d{{1,2}}-\d{{1,2}}\)', result[0])) for score in orientations)):
        raise ValueError('Official report result conflicts with schedule')
    goals = []
    for label, count, kind in [('STVV', match.goals_for, '得点'),
                                (match.opponent, match.goals_against, '失点')]:
        rows = [x.split(':', 1)[1] for x in summary if ':' in x and
                (x.split(':', 1)[0] in ('STVV', 'シントトロイデン', 'シント=トロイデンVV') if label == 'STVV' else
                 opponent(x.split(':', 1)[0]) == opponent(label))]
        if count == 0 and (not rows or rows in ([''], ['無し'], ['なし'])):
            continue
        if len(rows) != 1:
            raise ValueError('Official scorer list missing or ambiguous')
        entries = list(re.finditer(r'([^()、]+)\(([^()]+)\)', rows[0]))
        remainder = re.sub(r'([^()、]+)\(([^()]+)\)', '', rows[0]).replace('、', '')
        if remainder or not entries:
            raise ValueError('Official scorer notation unsupported')
        start = len(goals)
        for entry in entries:
            times = re.sub(r'^(?:PK)', '', re.sub(r'(?:、|,|/)?PK$', '', entry[2]))
            times = re.sub(r'(\d+)分\+(\d+)分', r'\1+\2分', times)
            for tm in re.split('[、,]', times):
                m = re.fullmatch(r'(\d{1,3}(?:\+\d{1,2})?)分', tm)
                if not m or not 1 <= int(m[1].split('+')[0]) <= 120:
                    raise ValueError('Official scorer notation unsupported')
                goals.append((kind, m[1], entry[1]))
        if len(goals) - start != count:
            raise ValueError('Official scorer count does not match result')
    try:
        appearances = parse_lineup(paragraphs)
        issue = None
    except ValueError as exc:
        # A complex substitution does not invalidate the separate scorer lists.
        # Retain no partial lineup, and explicitly report the missing section.
        appearances, issue = [], str(exc)
    return ClubReport(match.key, url, sha256(html.encode()).hexdigest(), tuple(goals), tuple(appearances), issue)


def parse_lineup(paragraphs):
    appearances, lineup = [], False
    for text in paragraphs:
        if text == '【先発】' or text == '[先発]':
            lineup = True
            continue
        if not lineup:
            continue
        if not re.match(r'^(GK|DF|MF|FW)/', text):
            if text:
                break
            continue
        for item in text.split('/', 1)[1].rstrip('、').split('、'):
            if any(mark in item for mark in ('⇒', '→')):
                raise ValueError('Chained substitutions require manual review')
            m = re.fullmatch(r'([^()]+)(?:\(([^()]+)\))?', item)
            if not m:
                raise ValueError('Official lineup notation unsupported')
            appearances.append((m[1], '先発'))
            if m[2]:
                subtext = m[2].replace(',', '')
                sub = re.fullmatch(r'([^\d()]+)(\d{1,3}(?:\+\d{1,2})?)分', subtext)
                inverse = re.fullmatch(r'(\d{1,3}(?:\+\d{1,2})?)分([^\d()]+)', subtext)
                if not sub and not inverse:
                    raise ValueError('Official substitution notation unsupported')
                name, tm = (sub[1], sub[2]) if sub else (inverse[2], inverse[1])
                appearances.append((name, '途中出場（公式交代時刻' + tm + '分）'))
    starters = [n for n, role in appearances if role == '先発']
    if appearances and (len(starters) != 11 or len({player(n) for n, _ in appearances}) != len(appearances)):
        raise ValueError('Official lineup is incomplete or duplicate')
    return appearances


def collect_reports(snapshot, matches, read=fetch):
    """URLs come from exact schedule blocks or the matched master row, never guesses."""
    from .engine import TABS
    grouped = {m.key: m for m in matches}
    related = {}
    # Validated article URLs already registered beside goals, players and stats
    # are discovery sources too. Parsing still binds every article to the master.
    for tab, id_col, url_col in [(TABS[1], 1, 13), (TABS[3], 0, 5), (TABS[4], 0, 13)]:
        for _, row in snapshot.rows(tab):
            related.setdefault(row[id_col], []).extend(u for u in str(row[url_col] or '').splitlines()
                                                       if REPORT_URL.fullmatch(u))
        for row_index, row in snapshot.rows(tab):
            # Evidence notes preserve added official URLs when the original
            # URL cell has a single-link format that must remain unchanged.
            for col in range(snapshot.props[tab]['gridProperties']['columnCount']):
                for line in snapshot.cell(tab, row_index, col).get('note', '').splitlines():
                    for prefix in ('STVV公式戦評：', '出典：'):
                        if line.startswith(prefix) and REPORT_URL.fullmatch(line[len(prefix):]):
                            related.setdefault(row[id_col], []).append(line[len(prefix):])
    tasks, pending = [], []
    for _, r in snapshot.rows(TABS[0]):
        from .source import competition
        key = r[1], r[2], opponent(r[4]), r[5], competition(r[3])
        match = grouped.get(key)
        if not match or match.goals_for is None:
            continue
        urls = tuple(dict.fromkeys([*match.report_urls,
            *(u for u in str(r[10] or '').splitlines() if REPORT_URL.fullmatch(u)),
            *related.get(r[0], [])]))
        if not urls:
            pending.append({'match_id': r[0], 'reason': 'club_report_url_not_published_or_registered'})
        for url in urls:
            tasks.append((r[0], match, url))
    if len(tasks) > 160:
        raise ValueError('Club report request bound exceeded')
    def one(task):
        match_id, match, url = task
        try:
            report = parse_report(read(url), match, url)
            return report, ({'match_id': match_id, 'url': url, 'reason': report.lineup_issue}
                            if report.lineup_issue else None)
        except Exception as exc:
            # Do not expose remote payloads or request credentials in CI artifacts.
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            return None, {'match_id': match_id, 'url': url, 'reason': reason}
    reports = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for report, issue in pool.map(one, tasks):
            if report:
                reports.append(report)
            if issue:
                pending.append(issue)
    return reports, pending
