"""Approved stadium template with deterministic, source-text-only typography.

The background and brush font are stored in Git. Rendering never calls an
image-generation API, and never invents a score, opponent or statistic.
"""
import os
import re
import random
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1374, 1145
YELLOW, WHITE = '#ffe100', '#ffffff'
LABELS = {
    'player': ('PLAYER', 'LAB'), 'compare': ('MATCH', 'COMPARE'),
    'data': ('MATCH', 'DATA'), 'analysis': ('TACTICAL', 'LAB'),
    'news': ('STVV', 'NEWS'), 'vote': ('FAN', 'VOICE'),
    'recap': ('MATCH', 'REVIEW'),
}
BACKGROUND = ROOT / 'assets/stadium_background.jpg'
BRUSH = ROOT / 'assets/fonts/PermanentMarker-Regular.ttf'


@lru_cache(maxsize=200)
def font(size, brush=False):
    paths = [BRUSH] if brush else [
        os.getenv('STVV_CARD_FONT', ''),
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
    ]
    for path in paths:
        if path and Path(path).is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError('Required editorial font missing')


def clean(message):
    message = re.sub(r'https?://\S+', '', message)
    message = re.sub(r'(?<!\w)#[^\s#]+', '', message)
    # Emoji are decoration in the caption, not Japanese font glyphs.
    message = re.sub('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]', '', message)
    return message.strip()


def wrap(draw, value, face, width):
    result = []
    for paragraph in value.splitlines():
        current = ''
        for char in paragraph:
            if current and draw.textlength(current + char, font=face) > width:
                result.append(current)
                current = char
            else:
                current += char
        if current:
            result.append(current)
    return result


def fitted(draw, value, box, maximum=64, minimum=22, color=WHITE, brush=False):
    if not value:
        return
    x, y, width, height = box
    for size in range(maximum, minimum - 1, -1):
        face = font(size, brush)
        lines = wrap(draw, value, face, width)
        # anchor='lt' removes language-dependent ascender offsets.
        step = size + max(4, size // 10)
        if len(lines) * step <= height:
            for index, line in enumerate(lines):
                if brush:
                    mask = Image.new('L', (width, step), 0)
                    md = ImageDraw.Draw(mask)
                    md.text((0, 0), line, font=face, fill=255, anchor='lt')
                    rng = random.Random(line + str(size))
                    for _ in range(width * step // 100):
                        px, py = rng.randrange(width), rng.randrange(step)
                        md.line((px, py, px + rng.randrange(1, 5), py - 1), fill=0)
                    draw.bitmap((x, y + index * step), mask, fill=color)
                else:
                    draw.text((x, y + index * step), line, font=face,
                              fill=color, anchor='lt', stroke_width=0)
            return
    raise ValueError('Editorial text does not fit; refusing clipped or truncated image')


def story(message):
    paragraphs = [p.strip(' ｜|') for p in clean(message).splitlines() if p.strip(' ｜|')]
    if not paragraphs:
        raise ValueError('No publishable card text')
    headline = paragraphs.pop(0)
    if headline in {'STVV公式ニュース', 'STVV LAB'} and paragraphs:
        headline = paragraphs.pop(0)
    if not paragraphs:
        # Only split at an existing semantic boundary, never rewrite the claim.
        chunks = re.split(r'(?<=[。！？])|[｜|]', headline, maxsplit=1)
        if len(chunks) > 1 and chunks[1].strip():
            headline, tail = chunks
            paragraphs = [tail.strip()]
    match = None
    rest = []
    for line in paragraphs:
        found = re.fullmatch(r'STVV\s+(\d{1,2})[–−-](\d{1,2})\s+(.+)', line)
        if found and match is None:
            match = found.groups()
        else:
            rest.append(line)
    # Spread the verbatim paragraphs across three columns without adding data.
    groups = ['', '', '']
    for line in rest:
        index = min(range(3), key=lambda i: len(groups[i]))
        groups[index] += ('\n' if groups[index] else '') + line
    return headline, match, groups


def render_content_card(slot, message, destination, source=None):
    if slot not in LABELS:
        raise ValueError('Unknown slot')
    if len(clean(message)) > 600:
        raise ValueError('Caption exceeds supported card length')
    headline, match, groups = story(message)
    with Image.open(BACKGROUND) as background:
        if background.size != (W, H):
            raise ValueError('Approved stadium template dimensions changed')
        im = background.convert('RGB')
    d = ImageDraw.Draw(im)
    fitted(d, 'STVV LAB', (109, 28, 300, 46), 42, 30)
    fitted(d, '非公式ファンメディア', (112, 79, 300, 26), 20, 18)
    first, second = LABELS[slot]
    fitted(d, first, (395, 12, 755, 170), 155, 65, YELLOW, True)
    fitted(d, second, (392, 177, 790, 185), 158, 65, WHITE, True)
    if match:
        own, other, opponent = match
        fitted(d, 'STVV', (365, 424, 290, 65), 52, 30, YELLOW)
        fitted(d, opponent, (755, 425, 250, 88), 43, 23)
        fitted(d, own + '–' + other, (540, 505, 470, 155), 142, 85, YELLOW)
        fitted(d, headline, (365, 678, 650, 70), 46, 23)
    else:
        fitted(d, headline, (368, 440, 632, 267), 70, 24)
    for index, value in enumerate(groups):
        left = 68 + index * 433
        if value:
            d.rectangle((left, 823, left + 51, 830), fill=YELLOW)
            fitted(d, value.replace('、', '、\n'), (left, 854, 371, 194), 40, 22)
    urls = re.findall(r'https?://[^\s]+', message)
    original = source or (urls[0] if urls else '')
    if original.startswith('https://stvv.jp/'):
        attribution = '出典：STVV日本公式'
    elif original.startswith('thesportsdb:'):
        attribution = '出典：TheSportsDB'
    else:
        attribution = 'STVV LAB'
    fitted(d, attribution, (80, 1094, 560, 30), 23, 20)
    fitted(d, 'STVV LAB / 非公式', (958, 1094, 345, 30), 23, 20, YELLOW)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() in {'.jpg', '.jpeg'}:
        im.save(destination, format='JPEG', quality=94, subsampling=0, optimize=True)
    else:
        im.save(destination, format='PNG', optimize=True)
    return destination
