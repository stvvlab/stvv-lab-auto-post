"""Narrow reviewed fact policy; never treat an angle label as new evidence."""
import hashlib
import re
from datetime import date

from content_guard import canonical_source, plain


def fact_metadata(card, now):
    fact = card.get('editorial_fact')
    if not isinstance(fact, dict) or fact.get('kind') != 'league_first_start':
        return None
    subject = fact.get('subject', '')
    claim = fact.get('claim', '')
    source = card.get('source_url', '')
    if (not re.fullmatch(r'[一-龥ぁ-んァ-ヶー]{3,20}', subject)
            or claim != subject + 'がリーグ初先発。'
            or claim not in card.get('text', '')
            or not re.fullmatch(r'https://stvv\.jp/news/(?:game|team)/\d{8}_[^/?#]+/', source)
            or source not in card.get('text', '')
            or re.search(r'\d\s*[–−-]\s*\d', card.get('text', ''))
            or not re.fullmatch(r'[a-f0-9]{64}', fact.get('source_body_sha256', ''))
            or card.get('reviewed') is not True or card.get('status') != 'ready'):
        return None
    try:
        day = date.fromisoformat(card['date_jst'])
        if (day.strftime('%Y%m%d') not in source
                or not 0 <= (now.date() - day).days <= 7):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    identity = hashlib.sha256(('stvv:league_first_start:' + subject).encode()).hexdigest()
    return {**fact, 'fact_id': identity}


def distinct_fact_reason(history, card, now):
    fact = fact_metadata(card, now)
    if not fact:
        return '新しい事実の審査情報が不正／未確認'
    source = canonical_source(card['source_url'])
    reservations = list(history.get('reserved_posts', {}).values())
    records = (history.get('publication_log', [])
               + list(history.get('pending_posts', {}).values()) + reservations)
    if any(canonical_source(p.get('source')) == source
           for p in list(history.get('pending_posts', {}).values())
           + [r for r in reservations if r.get('buffer_status') != 'sent']):
        return '同じ出典の送信結果が確認待ち'
    for previous in records:
        old = previous.get('editorial_fact') or {}
        text = plain(previous.get('text', ''))
        same_source = canonical_source(previous.get('source')) == source
        if plain(card['text']) == text or old.get('fact_id') == fact['fact_id']:
            return '同じ事実が投稿済み／確認待ち'
        if plain(fact['subject']) in text and any(plain(k) in text for k in ('初先発', '初スタメン', '初めて先発')):
            return '同じ選手の初先発が投稿済み／確認待ち'
        # At most one reviewed non-result fact per source. No slot filling.
        if same_source and (old or any(k in text for k in ('初先発', '初スタメン', '初めて先発'))):
            return '同じ出典の別事実は既に投稿済み／確認待ち'
    return None
