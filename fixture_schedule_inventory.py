"""Discover imminent STVV fixtures from the Japanese club's official schedule.

Read-only preparation evidence. A schedule row is not an approved post, and
this module never edits posting history, renders images, or calls Buffer.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))


def schedule_url(now):
    year = now.astimezone(JST).year
    if now.astimezone(JST).month < 7:
        year -= 1
    return f'https://stvv.jp/game/{year}-{year + 1}/'


def parse_fixtures(markup, now):
    """Require explicit JST notice, league section, fixture and broadcaster.

    Parsing is intentionally conservative: a layout change produces no draft
    rather than a potentially incorrect opponent or kickoff.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Timezone-aware now required')
    soup = BeautifulSoup(markup, 'html.parser')
    for tag in soup.select('script, style, noscript'):
        tag.decompose()
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()
    if '試合時間は日本時間の表記' not in text:
        raise ValueError('Official schedule JST notice missing')
    if 'BELGIAN PRO LEAGUE' not in text or 'UEFAカンファレンスリーグ' not in text:
        raise ValueError('Official competition sections not found')
    league = text.split('BELGIAN PRO LEAGUE', 1)[1].split('UEFAカンファレンスリーグ', 1)[0]
    pattern = re.compile(
        r'第(?P<round>\d{1,2})節\s+(?P<year>20\d{2})\s+'
        r'(?P<month>\d{1,2})\.(?P<day>\d{1,2})\s+'
        r'(?P<hour>\d{1,2}):(?P<minute>[0-5]\d)\s+KICKOFF\s+'
        r'(?P<venue>HOME|AWAY)\s+VS\.?\s*(?P<opponent>.+?)\s+'
        r'(?:DAZN|BS10)\b', re.I)
    results = []
    for match in pattern.finditer(league):
        data = match.groupdict()
        opponent = data['opponent'].strip()
        if (not 2 <= len(opponent) <= 45 or 'VS.' in opponent or
                any(token in opponent for token in ('KICKOFF', 'シント＝トロイデンVV', '第'))):
            continue
        try:
            kickoff = datetime(int(data['year']), int(data['month']), int(data['day']),
                               int(data['hour']), int(data['minute']), tzinfo=JST)
        except ValueError:
            continue
        if not now.astimezone(JST) < kickoff <= now.astimezone(JST) + timedelta(days=7):
            continue
        key = (f"jpl|{data['round']}|{kickoff.isoformat()}|"
               f"{data['venue'].upper()}|{opponent}")
        results.append({
            'fixture_id': hashlib.sha256(key.encode()).hexdigest()[:24],
            'competition': 'Belgian Pro League',
            'round': int(data['round']), 'kickoff_jst': kickoff.isoformat(),
            'venue': data['venue'].upper(), 'opponent': opponent,
        })
    return results


def build_inventory(history, now, session=requests, *, url=None):
    if not isinstance(history, dict) or not isinstance(history.get('publication_log'), list):
        raise ValueError('Publication history is required')
    url = url or schedule_url(now)
    response = session.get(url, timeout=20)
    response.raise_for_status()
    final = urlparse(getattr(response, 'url', url))
    if final.scheme != 'https' or final.netloc != 'stvv.jp' or final.path != urlparse(url).path:
        raise ValueError('Official fixture schedule redirected or changed path')
    fixtures = parse_fixtures(response.text, now)
    known = (history['publication_log'] +
             list(history.get('pending_posts', {}).values()) +
             list(history.get('reserved_posts', {}).values()))
    items = []
    for fixture in fixtures:
        already = any(isinstance(p, dict) and p.get('fixture_id') == fixture['fixture_id']
                      for p in known)
        if already:
            continue
        items.append({**fixture, 'source_url': url,
                      'evidence': 'Official Japanese STVV match schedule; kickoff displayed in JST',
                      'reviewed': False, 'status': 'fixture_evidence_only', 'can_publish': False,
                      'remaining': ['Check official schedule again before publishing',
                                    'Reconcile earlier articles and X/Buffer for this fixture',
                                    'Approve a unique factual caption and rights-safe original image',
                                    'Implement and test a separate strict fixture publishing gate'],
                      'design_direction': 'Navy/yellow editorial fixture card; varied composition, no score or invented lineup. A caricatured real player requires verified reference, rights review and explicit visual approval.'})
    return {'checked_at': now.astimezone(JST).isoformat(),
            'status': 'fixture_evidence_available' if items else 'no_upcoming_unrecorded_league_fixture',
            'source_url': url, 'candidates': items,
            'image_generation_performed': False, 'publication_performed': False,
            'note': 'Draft-only evidence; does not bypass used-source, image approval, duplicate or reservation gates.'}


def main():
    root = Path(__file__).resolve().parent
    history = json.loads((root / 'posted.json').read_text(encoding='utf-8'))
    report = build_inventory(history, datetime.now(JST))
    output = root / 'reports/fixture-schedule-latest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['status'], 'candidates:', len(report['candidates']), 'publication: false')


if __name__ == '__main__':
    main()
