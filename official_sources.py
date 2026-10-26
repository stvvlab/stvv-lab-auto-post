"""Read-only official news acquisition and parsing; no posting or ledger writes."""
import html
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

NEWS = "https://stvv.jp/news/2026/"

SPONSORS = (
    "スポンサー", "協賛", "パートナー",
    "サプライヤー", "グッズ",
    "キャンペーン", "プレゼント", "抽選",
)

WORDS = (
    "試合", "選手", "監督", "移籍",
    "加入", "退団", "負傷", "復帰",
    "出場", "得点", "代表", "招集",
    "契約", "順位", "勝利", "敗戦", "日程",
    "UEFA", "カンファレンスリーグ", "無観客", "キックオフ",
)

def scan_articles(now, session):
    """Inspect independent official lists; retain failures instead of hiding them."""
    year = now.year
    sources = [f'https://stvv.jp/news/{year}/',
               f'https://stvv.jp/news/game/{year}/',
               f'https://stvv.jp/news/team/{year}/',
               f'https://stvv.jp/news/uefa-news/{year}/']
    found, checks = {}, []
    for url in sources:
        try:
            response = session.get(url, timeout=20)
            response.raise_for_status()
            final_url = getattr(response, 'url', url)
            final = urlparse(final_url if isinstance(final_url, str) else url)
            if final.scheme != 'https' or final.netloc != 'stvv.jp':
                raise ValueError('Official listing redirected outside the approved host')
            if not BeautifulSoup(response.text, 'html.parser').find('a', href=True):
                raise ValueError('Unreadable official listing; no links found')
            parsed = parse_articles(response.text, now)
            found.update(dict(parsed))
            checks.append({'url': url, 'status': 'ok', 'eligible_items': len(parsed)})
        except (requests.RequestException, ValueError) as error:
            checks.append({'url': url, 'status': 'error', 'error': str(error)[:300]})
    return sorted(found.items(), key=lambda item: item[1][0], reverse=True), checks


def parse_articles(markup, now):
    """Parse one official listing with the same source/date/promotional filters."""

    soup = BeautifulSoup(markup, "html.parser")
    found = {}

    for anchor in soup.find_all("a", href=True):
        url = urljoin(NEWS, anchor["href"])
        parsed = urlparse(url)

        if parsed.netloc.lower() != "stvv.jp":
            continue

        path = parsed.path.rstrip("/") + "/"

        match = re.fullmatch(
            r"/news/(game|team|uefa-news)/(20\d{6}[^/]*)/",
            path,
            re.I,
        )
        if not match:
            continue

        try:
            day = datetime.strptime(
                match.group(2)[:8], "%Y%m%d"
            ).date()
        except ValueError:
            continue

        if not 0 <= (now.date() - day).days <= 7:
            continue

        # The official list wraps h3 + date + a long excerpt in one link.
        # Use the heading, not the entire card, without summarizing its claim.
        heading = anchor.find(['h2', 'h3'])
        title_node = BeautifulSoup(str(heading if heading is not None else anchor), 'html.parser')
        for timestamp in title_node.find_all('time'):
            timestamp.decompose()
        title = re.sub(
            r"\s+",
            " ",
            BeautifulSoup(
                html.unescape(
                    title_node.get_text(" ", strip=True)
                ),
                "html.parser",
            ).get_text(" ", strip=True),
        ).strip()

        if (
            len(title) < 8
            or any(word in html.unescape(anchor.get_text(" ", strip=True)) for word in SPONSORS)
            or not any(word in title for word in WORDS)
        ):
            continue

        found["https://stvv.jp" + path] = (day, title)

    return sorted(
        found.items(),
        key=lambda item: item[1][0],
        reverse=True,
    )


