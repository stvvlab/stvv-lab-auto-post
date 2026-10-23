"""Official sources only. Unknown layouts and ambiguous results fail closed."""
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import re
import unicodedata
from urllib.parse import urlsplit, urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

JST = ZoneInfo('Asia/Tokyo')
HOSTS = {'stvv.jp', 'www.uefa.com', 'www.proleague.be'}


def fetch(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.port not in (None, 443):
        raise ValueError('Unapproved source URL')
    # Validate every redirect before contacting the next host.
    for _ in range(4):
        response = requests.get(url, timeout=(10, 35), allow_redirects=False,
                                headers={'User-Agent': 'STVV-LAB-Database/1.0'})
        if response.is_redirect:
            from urllib.parse import urljoin
            url = urljoin(url, response.headers['Location'])
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
                raise ValueError('Unapproved source redirect')
            continue
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Source exceeds size limit')
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text
    raise ValueError('Too many source redirects')


def clean(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


ALIASES = {'OHルーヴェン': 'OHルーベン', 'ヘンク': 'ゲンク',
           'FCイベリア1999': 'イベリア1999トビリシ', 'ウェステルロ―': 'ウェステルロー',
           'ユニオン・サン・ジロワーズ': 'ユニオン'}


def opponent(text):
    return ALIASES.get(clean(text), clean(text))


@dataclass(frozen=True)
class Match:
    season: str
    day: str
    competition: str
    opponent: str
    venue: str
    goals_for: int | None
    goals_against: int | None
    url: str
    digest: str
    report_urls: tuple[str, ...] = ()

    @property
    def key(self):
        return self.season, self.day, opponent(self.opponent), self.venue, self.competition


def competition(text):
    value = clean(text).upper()
    if 'FRIENDLY' in value or '親善' in value:
        return 'friendly'
    if 'CUP' in value or 'カップ' in value:
        return 'cup'
    if 'カンファレンス' in value or 'CONFERENCE' in value:
        return 'conference'
    if 'EL予選' in value or 'ヨーロッパリーグ' in value:
        return 'europa'
    if 'プレーオフ' in value or '優勝PO' in value:
        return 'playoff'
    if 'リーグ' in value or 'PROLEAGUE' in value:
        return 'league'
    raise ValueError('Unrecognised competition')


def parse_schedule(html, season, url, today=None):
    today = today or datetime.now(JST).date()
    soup = BeautifulSoup(html, 'html.parser')
    digest = sha256(html.encode()).hexdigest()
    output = []
    for group in soup.select('.container--content'):
        heading = group.select_one('.game__title')
        if not heading:
            continue
        kind = competition(heading.get_text())
        if kind == 'friendly':
            continue
        for block in group.select('.game__body-contents'):
            parts = block.select('.txt > p')
            if len(parts) != 3:
                raise ValueError('Official date layout changed')
            first = BeautifulSoup(str(parts[0]), 'html.parser')
            for tag in first.select('span'):
                tag.decompose()
            year = clean(first.get_text())
            md = clean(parts[1].get_text()).split('.')
            if not re.fullmatch(r'20\d{2}', year) or len(md) != 2:
                raise ValueError('Ambiguous official date')
            day = date(int(year), int(md[0]), int(md[1]))
            if not int(season[:4]) <= day.year <= int(season[:4]) + 1:
                raise ValueError('Date outside requested season')
            vs = block.select_one('.vs')
            hw = vs.select_one('.hw') if vs else None
            if not hw or hw.get_text(strip=True) not in ('HOME', 'AWAY'):
                raise ValueError('Missing official venue')
            venue = hw.get_text(strip=True)
            other = clean(vs.get_text()).split('VS.', 1)
            if len(other) != 2 or not other[1]:
                raise ValueError('Missing opponent')
            teams = [li for li in block.select('.vs-team > li') if li.select_one('span')]
            if len(teams) != 2:
                raise ValueError('Official score layout changed')
            names, scores = [], []
            for li in teams:
                name = li.select_one('span')
                names.append(clean(name.get_text()))
                name.extract()
                value = clean(li.get_text())
                if not re.fullmatch(r'\d{1,2}|-', value):
                    raise ValueError('Ambiguous score or penalty notation')
                scores.append(None if value == '-' else int(value))
            own = [i for i, name in enumerate(names) if name == 'シント=トロイデンVV' or name == 'シント＝トロイデンVV']
            if len(own) != 1:
                raise ValueError('STVV team identity not found')
            i = own[0]
            if (venue == 'HOME') != (i == 0) or opponent(names[1-i]) != opponent(other[1]):
                raise ValueError('Home/away or opponent mismatch')
            if (scores[0] is None) != (scores[1] is None):
                raise ValueError('Partial score')
            if scores[0] is not None and day > today:
                raise ValueError('Future match has a result')
            links = tuple(dict.fromkeys(urljoin(url, a['href']) for a in block.select('a[href]')
                if re.fullmatch(r'https://stvv\.jp/news/(?:game|uefa-news)/[^?#]+/', urljoin(url, a['href']))))
            output.append(Match(season, day.isoformat(), kind, other[1], venue,
                                scores[i], scores[1-i], url, digest, links))
    if not output:
        raise ValueError('No official matches parsed; refusing empty-source success')
    if len({m.key for m in output}) != len(output):
        raise ValueError('Duplicate official match identity')
    return output


def parse_uefa_stats(html):
    """Season totals are retained as totals, never silently used as match data."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
    def number(label, pattern=r'\d+(?:\.\d+)?'):
        match = re.search(r'(?<![\d.])(' + pattern + r')\s+' + re.escape(label), text)
        return float(match[1]) if match else None
    return {'matches_played': number('Matches played', r'\d+'),
            'distance_km': number('Distance covered (km)'),
            'shots_on_target_against': number('Attempts conceded on target', r'\d+')}
