"""Use saved official facts only after checking the live official article."""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

MANIFEST = Path(__file__).resolve().parent / 'editorial/official_match_facts.json'


def scoring_data(session, now):
    facts = json.loads(MANIFEST.read_text(encoding='utf-8'))
    day = date.fromisoformat(facts['match_date_jst'])
    if not 0 <= (now.date() - day).days <= 7:
        return None
    url = facts['source_url']
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != 'stvv.jp':
        return None
    response = session.get(url, timeout=25)
    response.raise_for_status()
    if urlparse(response.url).scheme != 'https' or urlparse(response.url).netloc != 'stvv.jp':
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    text = re.sub(r'\s+', '', soup.get_text())
    score = facts['score']
    if not re.fullmatch(r'\d{1,2}-\d{1,2}', score):
        return None
    own, other = map(int, score.split('-'))
    goals = facts['goals']
    # Bind date, opponent, score and the entire STVV scorer row together.
    # A match result alone is insufficient to authorize individual figures.
    expected = [day.strftime('%Y.%m.%d'), f'{day.month}月{day.day}日',
                f"{facts['opponent']}戦（H）", f'結果：{score}']
    if any(value not in text for value in expected):
        return None
    if len(goals) != own or not goals:
        return None
    if any(not isinstance(name, str) or type(minute) is not int or not 1 <= minute <= 130
           for name, minute in goals):
        return None
    scorer_row = 'STVV：' + '、'.join(f'{name}（{minute}分）' for name, minute in goals)
    if scorer_row not in text:
        return None
    message = '\n'.join([
        '📊 公式記録で振り返る得点時間',
        f"STVV {own}–{other} {facts['opponent']}",
        *[f'{name}：{minute}分' for name, minute in goals],
        f'公式：{url}',
    ])
    return message, url
