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
        if parsed.scheme != 'https' or parsed.netloc != 'stvv.jp' or not parsed.path.startswith('/news/'):
            continue
        day = date.fromisoformat(card['date_jst'])
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
