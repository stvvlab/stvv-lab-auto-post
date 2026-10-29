"""Value-based repetition review for explicitly approved editorial cards.

An official source being reused does not mean an X post was repeated.
This narrow opt-in never authorizes unreviewed cards or bypasses send/media gates.
"""
from datetime import datetime, timedelta
from content_guard import plain

KINDS = {'fixture', 'result', 'lineup', 'analysis', 'player', 'news'}
PHASES = {'initial', 'reminder', 'matchday', 'lineup', 'final', 'review', 'update'}


def value_based_repeat_reason(history, card, now):
    """Return a blocking reason or None for a reviewed editorial purpose.

    Only exact approved cards with a stable event key and explicitly selected
    phase may use this policy. Legacy cards retain legacy duplicate checks.
    """
    purpose = card.get('editorial_purpose')
    if (card.get('reviewed') is not True or card.get('status') != 'ready'
            or not isinstance(purpose, dict)
            or purpose.get('kind') not in KINDS
            or purpose.get('phase') not in PHASES
            or not isinstance(purpose.get('event_id'), str)
            or not 5 <= len(purpose['event_id']) <= 120
            or not purpose['event_id'].isascii()
            or not all(c.isalnum() or c in '-_:' for c in purpose['event_id'])
            or not isinstance(card.get('text'), str) or not card['text'].strip()):
        return 'invalid_reviewed_editorial_purpose'
    if not isinstance(history.get('publication_log'), list) or not isinstance(history.get('pending_posts'), dict) or not isinstance(history.get('reserved_posts'), dict):
        return 'incomplete_publication_history'
    entries = (
        [('published', p) for p in history['publication_log']]
        + [('pending', p) for p in history['pending_posts'].values()]
        + [('reserved', p) for p in history['reserved_posts'].values()]
    )
    for state, old in entries:
        if not isinstance(old, dict):
            return 'incomplete_publication_history'
        # An identical caption is not a new publication purpose.
        if plain(card['text']) == plain(old.get('text', '')):
            return 'identical_caption_already_sent_or_pending'
        prior = old.get('editorial_purpose')
        if not isinstance(prior, dict) or prior.get('event_id') != purpose['event_id']:
            continue
        if prior.get('kind') != purpose['kind'] or prior.get('phase') != purpose['phase']:
            continue
        if state != 'published':
            return 'same_purpose_pending_or_reserved'
        stamp = old.get('submitted_at') or old.get('created_at')
        if not isinstance(stamp, str):
            return 'same_purpose_publication_time_unknown'
        try:
            when = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if when.tzinfo is None or now.tzinfo is None:
                return 'same_purpose_publication_time_unknown'
            if now - when < timedelta(hours=24):
                return 'same_purpose_published_within_24h'
        except (ValueError, TypeError):
            return 'same_purpose_publication_time_unknown'
    return None
