"""Conservative local repetition checks; no paid API or generated claims."""
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit


def canonical_source(source):
    if not isinstance(source, str):
        return ''
    if source.startswith('thesportsdb:'):
        return source
    parsed = urlsplit(source)
    return (parsed.netloc.lower() + parsed.path.rstrip('/')) if parsed.netloc else ''


def plain(text):
    text = unicodedata.normalize('NFKC', text or '')
    text = re.sub(r'https?://\S+|(?<!\w)#[^\s#]+', '', text)
    return re.sub(r'[^\w]', '', text).lower()


def context_keys(text, source):
    keys = set()
    src = canonical_source(source)
    if src:
        keys.add('source:' + src)
    text = unicodedata.normalize('NFKC', text or '')
    score = re.search(r'STVV[、\s]*(\d{1,2})[–−-](\d{1,2})', text, re.I)
    if score:
        pair = '-'.join(score.groups())
        # Saved aliases bind official/Japanese captions to the public event
        # source. These identifiers are internal, never new published facts.
        try:
            facts = json.loads((Path(__file__).resolve().parent /
                               'editorial/official_match_facts.json').read_text())
            aliases = facts.get('opponent_aliases', [facts['opponent']])
            if any(alias.lower() in text.lower() for alias in aliases):
                keys.add('match:' + facts['opponent'] + ':' + pair)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        direct = re.search(r'STVV\s+\d{1,2}[–−-]\d{1,2}\s+([^\n]+)', text, re.I)
        if direct:
            keys.add('match:' + plain(direct[1]) + ':' + pair)
    return keys


def measured_facts(text):
    """Only actual shot/possession comparisons count as a new data angle.

    A score, scorer or goal minute alone does not make a second recap useful.
    This recognizes the structured formats produced by match_post, rather
    than claiming general semantic understanding of arbitrary prose.
    """
    text = unicodedata.normalize('NFKC', text or '')
    facts = set()
    for label, names in [('shots', 'シュート'), ('target', '枠内'), ('possession', '支配率')]:
        for a, b in re.findall(names + r'[：:]?\s*(\d+(?:\.\d+)?)%?\s*(?:対|/|／)\s*(\d+(?:\.\d+)?)%?', text):
            facts.add((label, float(a), float(b)))
    if 'シュート数比較' in text:
        for a, b in re.findall(r'STVV\s+(\d+)\s*[/／]\s*相手\s*(\d+)', text):
            facts.add(('shots', float(a), float(b)))
    return facts


def duplicate_reason(history, message, source, now):
    """Check actual account publications separately from unresolved send intents.

    An official article appearing in history['news'] is *not* evidence that
    this account published it. Exact repeated captions are blocked for all
    time. Unknown sends and user-cancelled reservations never age out and
    cannot be bypassed by a new statistics angle. Only confirmed historical
    publications use the seven-day topical comparison window.
    """
    keys = context_keys(message, source)
    publications = history.get('publication_log', [])
    pending = list(history.get('pending_posts', {}).values())
    reserved = list(history.get('reserved_posts', {}).values())
    records = publications + pending + reserved

    # Do not permit a verbatim repeat merely because the previous X post
    # is more than seven days old. News inventory alone is not consulted.
    normalized = plain(message)
    if normalized and any(normalized == plain(p.get('text', '')) for p in records):
        return '同じ内容の本文が投稿済み／確認待ち'

    # A pending Buffer request can be older than seven days and still have an
    # unknown outcome. A draft moved by the user must not be auto-resubmitted.
    for previous in pending + reserved:
        if not isinstance(previous, dict):
            return '送信待ち履歴が不正のため確認待ち'
        if previous.get('buffer_status') == 'sent' and any(
                p.get('buffer_id') == previous.get('buffer_id')
                and previous.get('buffer_id') for p in publications):
            continue  # The same confirmed publication is handled below.
        if keys & context_keys(previous.get('text', ''), previous.get('source')):
            if previous.get('buffer_status') == 'cancelled_by_user':
                return 'ユーザー取消済み予約が存在するため自動再送不可'
            return '同じ出典／試合の送信待ち・結果不明が存在'

    matched = []
    for previous in publications:
        if not isinstance(previous, dict):
            return '公開履歴が不正のため確認待ち'
        stamp = previous.get('submitted_at') or previous.get('created_at')
        if stamp:
            try:
                when = datetime.fromisoformat(stamp)
                if when.tzinfo and now - when > timedelta(days=7):
                    continue
            except (TypeError, ValueError):
                pass
        if keys & context_keys(previous.get('text', ''), previous.get('source')):
            matched.append(previous)
    if not matched:
        return None
    known = set().union(*(measured_facts(item.get('text', '')) for item in matched))
    if measured_facts(message) - known:
        return None
    return '同じ出典／試合の内容で、新しい比較データがないため見送り'
