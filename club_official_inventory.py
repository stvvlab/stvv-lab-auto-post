"""Read-only Belgian STVV official news inventory for editorial review.

This does not authorize posting: production manifest sources remain stvv.jp-only.
Do not infer kickoff times from one club article.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from content_guard import canonical_source
from stvv_post import JST, SESSION

ROOT = Path(__file__).resolve().parent
LISTING = 'https://stvv.com/nl/nieuws'
MONTHS = dict(zip(('januari februari maart april mei juni juli augustus september '
                   'oktober november december').split(), range(1, 13)))
PROMOTIONAL = ('sponsor', 'partner', 'ticketinfo', 'ticketverkoop', 'webshop',
               'abonnement', 'korting', 'winactie', 'merchandise')
ARTICLE_PATH = re.compile(r'/nl/nieuws/artikel/[a-z0-9%_-]+/?$', re.I)
DATE = re.compile(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', re.I)


def approved_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.netloc == 'stvv.com'
            and bool(ARTICLE_PATH.fullmatch(parsed.path)) and not parsed.query
            and not parsed.fragment and not parsed.username and not parsed.password)


def listing_links(markup):
    soup = BeautifulSoup(markup, 'html.parser')
    found = {}
    for a in soup.select('a[href]'):
        url = urljoin(LISTING, a['href'])
        if not approved_url(url):
            continue
        title = re.sub(r'\s+', ' ', a.get_text(' ', strip=True)).strip()
        if not title or any(word in title.lower() for word in PROMOTIONAL):
            continue
        found.setdefault(url, title[:180])
    return list(found.items())


def article_evidence(markup, now):
    soup = BeautifulSoup(markup, 'html.parser')
    # STVV's current article pages may use a div-based layout without
    # semantic <main>/<article>. Require an H1 and an immediately following
    # publication date before treating any body text as evidence.
    node = soup.select_one('main') or soup.select_one('article') or soup.body or soup
    for child in node.select('script, style, iframe, noscript'):
        child.decompose()
    heading = node.find('h1')
    if heading is None:
        raise ValueError('Official article heading not found')
    title = heading.get_text(' ', strip=True)
    text = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
    start = text.find(title)
    if start < 0:
        raise ValueError('Heading not in article body')
    text = text[start:]
    # Avoid accidentally hashing site navigation/footer as article evidence.
    footer = re.search(r'\bContact\s+Tiensesteenweg\b', text)
    if footer:
        text = text[:footer.start()].strip()
    # The article date must follow its heading; never infer it from the listing.
    match = DATE.search(text[len(title):len(title) + 180])
    if not match:
        raise ValueError('Official article publication date not found')
    day = datetime(int(match[3]), MONTHS[match[2].lower()], int(match[1])).date()
    if not 0 <= (now.date() - day).days <= 7:
        return None
    if len(text) < 180 or len(text) > 30000:
        raise ValueError('Official article body too short or long')
    return {'date_jst': day.isoformat(), 'official_heading': title,
            'source_body': text, 'body_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'kickoff_time_requires_cross_source_check': bool(re.search(r'\b\d{1,2}(?::|u)\d{2}\b', text))}


def build_inventory(history, manifest, now, session=SESSION, max_articles=4):
    if not 1 <= max_articles <= 6:
        raise ValueError('Limit official source requests')
    known = {canonical_source(x) for x in history.get('news', [])}
    for entry in history.get('publication_log', []):
        known.add(canonical_source(entry.get('source')))
    for group in ('pending_posts', 'reserved_posts'):
        for entry in history.get(group, {}).values():
            known.add(canonical_source(entry.get('source') or entry.get('source_url')))
    for card in manifest.get('cards', []):
        if card.get('status') in ('ready', 'published'):
            known.add(canonical_source(card.get('source_url')))
    report = {'checked_at': now.isoformat(), 'listing_url': LISTING,
              'status': 'source_scan_failed', 'candidates': [], 'skipped': [],
              'publication_performed': False, 'image_generation_performed': False,
              'can_publish': False,
              'note': 'Research only. stvv.com is not enabled in the production manifest. '
                      'No kickoff time is approved without cross-source resolution.'}
    try:
        response = session.get(LISTING, timeout=20)
        response.raise_for_status()
        if urlparse(response.url).scheme != 'https' or urlparse(response.url).netloc != 'stvv.com':
            raise ValueError('Listing redirected outside approved host')
        links = listing_links(response.text)
        if not links:
            raise ValueError('No valid article links in official listing')
        # A known article must not consume the bounded fetch budget. Otherwise
        # the first N previously published links can starve newer unseen news.
        unseen_checked = 0
        for url, listing_title in links:
            if canonical_source(url) in known:
                report['skipped'].append({'source_url': url, 'reason': 'already registered or pending'})
                continue
            if unseen_checked >= max_articles:
                break
            unseen_checked += 1
            item = {'source_url': url, 'listing_heading': listing_title,
                    'reviewed': False, 'can_publish': False}
            try:
                page = session.get(url, timeout=20)
                page.raise_for_status()
                if not approved_url(page.url):
                    raise ValueError('Article redirected outside approved host')
                evidence = article_evidence(page.text, now)
                if evidence is None:
                    report['skipped'].append({'source_url': url, 'reason': 'outside seven days'})
                    continue
                item.update(evidence, status='needs_editorial_review')
            except (requests.RequestException, ValueError) as error:
                item.update(status='source_unavailable', error_type=type(error).__name__)
            report['candidates'].append(item)
        report['status'] = 'candidates_need_review' if report['candidates'] else 'no_new_club_articles'
    except (requests.RequestException, ValueError) as error:
        report['error_type'] = type(error).__name__
    return report


def main():
    history = json.loads((ROOT / 'posted.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'editorial/imagegen_cards.json').read_text(encoding='utf-8'))
    result = build_inventory(history, manifest, datetime.now(JST))
    path = ROOT / 'reports/club-official-latest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Belgian club official inventory:', result['status'], len(result['candidates']))
    if result['status'] == 'source_scan_failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
