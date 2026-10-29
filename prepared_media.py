"""Deliver reviewed imagegen assets; never generate or silently redraw them."""
import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'editorial/imagegen_cards.json'


def exact_card(slot, message, source):
    from stvv_post import HASHTAGS
    if message.endswith(HASHTAGS):
        message = message[:-len(HASHTAGS)]
    if not MANIFEST.exists():
        return None
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data.get('enabled') is not True:
        return None
    cards = [c for c in data.get('cards', []) if c.get('source_url') == source
             and c.get('text') == message and slot in c.get('slots', [])
             and c.get('status') == 'ready' and c.get('reviewed') is True]
    return cards[0] if len(cards) == 1 else None


def prepared_duplicate_reason(history, message, source, slot, now):
    from content_guard import duplicate_reason
    from editorial_novelty import distinct_fact_reason
    base = duplicate_reason(history, message, source, now)
    card = exact_card(slot, message, source)
    if card is None:
        return base
    # Explicit editorial-purpose approval permits useful reminders and distinct
    # coverage angles without treating a reused official URL as a duplicate.
    # Unknown/invalid purpose metadata fails closed. Other gates remain intact.
    if 'editorial_purpose' in card:
        from editorial_repeat_policy import value_based_repeat_reason
        return value_based_repeat_reason(history, card, now)
    if 'editorial_fact' not in card:
        return base
    # Only an exact reviewed claim of a supported kind may differ from a recap.
    return distinct_fact_reason(history, card, now)


def prepared_fact_metadata(slot, message, source, now):
    from editorial_novelty import fact_metadata
    card = exact_card(slot, message, source)
    return fact_metadata(card, now) if card else None


def prepared_art_direction(slot, message, source):
    """Read design metadata only from the exact reviewed ready card."""
    from design_brief import ART_DIRECTIONS
    if not MANIFEST.exists():
        return None
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data.get('enabled') is not True:
        return None
    cards = [c for c in data.get('cards', []) if c.get('source_url') == source
             and c.get('text') == message and slot in c.get('slots', [])
             and c.get('reviewed') is True and c.get('status') == 'ready']
    if len(cards) != 1:
        return None
    direction = cards[0].get('art_direction')
    return direction if direction in ART_DIRECTIONS else None


def reviewed_official_body(session, card, now):
    """Verify a dated Belgian article's exact body digest before publication."""
    source = card.get('source_url', '')
    parsed = urlparse(source)
    if parsed.netloc == 'stvv.com':
        from club_official_inventory import read_verified_article
        evidence = read_verified_article(session, source, now)
        digest = card.get('source_body_sha256', '')
        if (card.get('editorial_fact') is not None
                or not isinstance(digest, str)
                or not re.fullmatch(r'[a-f0-9]{64}', digest)
                or evidence['date_jst'] != card.get('date_jst')
                or evidence['body_sha256'] != digest):
            raise ValueError('Belgian official body/date differs from reviewed card')
        return evidence['source_body']
    if parsed.netloc != 'stvv.jp' or parsed.scheme != 'https':
        raise ValueError('Unapproved official article source')
    from preparation_inventory import read_body
    return read_body(session, source)


def prepared_candidates(slot, now):
    """Yield fresh reviewed editorial copy, never a headline rewritten on the runner."""
    if not MANIFEST.exists():
        return []
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data.get('enabled') is not True:
        return []
    result = []
    for card in data['cards']:
        if (card.get('reviewed') is not True or card.get('status') != 'ready'
                or slot not in card.get('slots', [])):
            continue
        source = card.get('source_url', '')
        parsed = urlparse(source)
        if parsed.scheme != 'https' or parsed.query or parsed.fragment:
            continue
        japanese = (parsed.netloc == 'stvv.jp'
                    and bool(re.fullmatch(r'/news/(?:game|team|uefa-news)/\d{8}_[^/?#]+/', parsed.path)))
        from club_official_inventory import approved_url
        digest = card.get('source_body_sha256')
        belgian = (approved_url(source) and isinstance(digest, str)
                   and bool(re.fullmatch(r'[a-f0-9]{64}', digest))
                   and 'editorial_fact' not in card)
        if not japanese and not belgian:
            continue
        try:
            day = date.fromisoformat(card['date_jst'])
        except (KeyError, ValueError, TypeError):
            continue
        text = card.get('text')
        if 0 <= (now.date() - day).days <= 7 and isinstance(text, str) and source in text:
            result.append((text, source))
    return result


def prepared_media(session, slot, message, source):
    """Return (enabled, url). Enabled mode fails closed without a matching card."""
    if not MANIFEST.exists():
        return False, None
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data.get('enabled') is not True:
        return False, None
    cards = [card for card in data['cards']
             if card.get('source_url') == source and card.get('text') == message
             and slot in card.get('slots', []) and card.get('reviewed') is True
             and card.get('status') == 'ready']
    if len(cards) != 1:
        return True, None
    card = cards[0]
    if urlparse(source).netloc == 'stvv.com' or 'editorial_fact' in card:
        from datetime import datetime
        from stvv_post import JST
        from editorial_novelty import fact_metadata
        body = reviewed_official_body(session, card, datetime.now(JST))
        if 'editorial_fact' in card:
            fact = fact_metadata(card, datetime.now(JST))
            if (not fact or fact['claim'] not in body
                    or hashlib.sha256(body.encode()).hexdigest() != fact['source_body_sha256']):
                raise ValueError('Official body or reviewed fact changed; re-review required')
    path = Path(card['asset_path'])
    if path.is_absolute() or path.parent != Path('generated') or path.suffix not in {'.png', '.jpg'}:
        raise ValueError('Prepared asset must be directly under generated/')
    local_path = ROOT / path
    if local_path.is_symlink():
        raise ValueError('Prepared asset symlinks are not allowed')
    content = local_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != card['sha256']:
        raise ValueError('Prepared image digest differs from reviewed asset')
    with Image.open(local_path) as image:
        if list(image.size) != card['dimensions'] or image.format not in {'PNG', 'JPEG'}:
            raise ValueError('Prepared image metadata differs')
        image.verify()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Invalid immutable asset revision')
    url = f'https://raw.githubusercontent.com/stvvlab/stvv-lab-auto-post/{revision}/{path.as_posix()}'
    response = session.get(url, timeout=25)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != digest:
        raise ValueError('Public image bytes differ from reviewed asset')
    return True, url
