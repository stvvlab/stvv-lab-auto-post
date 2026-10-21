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
    """Compare published and pending content before creating or sending media."""
    keys = context_keys(message, source)
    matched = []
    publications = history.get('publication_log', [])
    pending = list(history.get('pending_posts', {}).values())
    for previous in publications + pending:
        stamp = previous.get('submitted_at') or previous.get('created_at')
        if stamp:
            try:
                when = datetime.fromisoformat(stamp)
                if when.tzinfo and now - when > timedelta(days=7):
                    continue
            except (TypeError, ValueError):
                pass
        old_text = previous.get('text', '')
        if plain(message) == plain(old_text):
            return '同じ内容の本文が投稿済み／確認待ち'
        if keys & context_keys(old_text, previous.get('source')):
            matched.append(previous)
    if not matched:
        return None
    known = set().union(*(measured_facts(item.get('text', '')) for item in matched))
    if measured_facts(message) - known:
        return None
    return '同じ出典／試合の内容で、新しい比較データがないため見送り'
