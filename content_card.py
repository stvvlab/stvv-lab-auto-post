"""Approved stadium template with deterministic, source-text-only typography.

The background and brush font are stored in Git. Rendering never calls an
image-generation API, and never invents a score, opponent or statistic.
"""
import os
import re
import random
import json
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
TOKENS = re.compile(
    r'[0-9０-９]+(?:[–−:/.-][0-9０-９]+)*(?:分|本|位|人|%|％)?'
    r'|[A-Za-z]+(?:[\x27-][A-Za-z]+)*'
    r'|[ァ-ヺー]+(?:・[ァ-ヺー]+)*|[一-龥々]+|.', re.S)
LINE_START_PROHIBITED = set('、。，．！？!?：:；;）)]｝}」』】〉》ーっゃゅょぁぃぅぇぉッャュョァィゥェォ')
LINE_END_PROHIBITED = set('（([｛{「『【〈《')


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
        tokens = TOKENS.findall(paragraph)
        expanded = []
        for token in tokens:
            # Preserve names, words and number/unit pairs whenever they fit.
            if (expanded and token[0] in LINE_START_PROHIBITED
                    and draw.textlength(expanded[-1], font=face) <= width):
                # Keep punctuation with the preceding intact word. A line may
                # exceed width here: fitted() then shrinks the font instead
                # of tearing the last glyph off a player's name or term.
                expanded[-1] += token
                continue
            expanded.extend([token] if draw.textlength(token, font=face) <= width else list(token))
        for token in expanded:
            if current and draw.textlength(current + token, font=face) > width:
                if token[0] in LINE_START_PROHIBITED:
                    # Move the last glyph with the punctuation to the next line.
                    last = current[-1:]
                    current = current[:-1]
                    result.append(current)
                    current = last + token
                elif current[-1] in LINE_END_PROHIBITED:
                    last = current[-1:]
                    result.append(current[:-1])
                    current = last + token
                else:
                    result.append(current)
                    current = token
            else:
                current += token
        if current:
            result.append(current)
    return result


def brush_title(draw, value, box, color):
    x, y, width, height = box
    for size in range(180, 64, -1):
        face = font(size, True)
        bounds = face.getbbox(value)
        mask = Image.new('L', (bounds[2] - bounds[0] + 12, bounds[3] - bounds[1] + 12), 0)
        md = ImageDraw.Draw(mask)
        md.text((6 - bounds[0], 6 - bounds[1]), value, font=face, fill=255)
        rng = random.Random(value + str(size))
        for _ in range(mask.width * mask.height // 240):
            px, py = rng.randrange(mask.width), rng.randrange(mask.height)
            md.line((px, py, px + rng.randrange(2, 8), py - 1), fill=0)
        tilted = mask.rotate(4, Image.Resampling.BICUBIC, expand=True)
        if tilted.width <= width and tilted.height <= height:
            draw.bitmap((x, y + (height - tilted.height) // 2), tilted, fill=color)
            return {'font_size': size, 'angle': 4, 'box': list(box)}
    raise ValueError('Brush heading does not fit')


def brush_sweep(draw, box, color=WHITE):
    """Add a deterministic paint-brush finish below the editorial heading."""
    x, y, width, height = box
    mask = Image.new('L', (width, height), 0)
    md = ImageDraw.Draw(mask)
    # A tapered main stroke plus broken bristle trails. All marks stay inside
    # the heading area and carry no information of their own.
    md.polygon([(0, 5), (width - 44, 0), (width, 4),
                (width - 86, 11), (22, 17)], fill=220)
    rng = random.Random('stvv-lab-brush-sweep-v1')
    bristles = []
    for index in range(5):
        start = rng.randrange(32, 160)
        end = width - rng.randrange(12, 150)
        row = 18 + index * 5
        thickness = rng.randrange(2, 6)
        md.polygon([(start, row), (end, row - rng.randrange(0, 4)),
                    (end - rng.randrange(12, 46), row + thickness),
                    (start + rng.randrange(8, 36), row + thickness + 1)],
                   fill=rng.randrange(105, 205))
        bristles.append([start, row, end])
    draw.bitmap((x, y), mask, fill=color)
    return {'box': list(box), 'bristles': bristles}


def panel_boxes(groups):
    values = [value for value in groups if value.strip()]
    if not values:
        return []
    gap, left, available = 18, 42, 1290
    width = (available - gap * (len(values) - 1)) // len(values)
    return [(value, (left + index * (width + gap), 807, width, 258))
            for index, value in enumerate(values)]


def panel_parts(value):
    """Promote only an existing short lead; never summarize or add a claim."""
    if '\n' not in value:
        found = re.fullmatch(r'([^、：:]{1,12})([、：:])(.+)', value)
        if found:
            return found.groups()
    return None


def fitted(draw, value, box, maximum=64, minimum=22, color=WHITE, brush=False, dry_run=False):
    if not value:
        return
    x, y, width, height = box
    for size in range(maximum, minimum - 1, -1):
        face = font(size, brush)
        lines = wrap(draw, value, face, width)
        # anchor='lt' removes language-dependent ascender offsets.
        step = size + max(4, size // 10)
        if len(lines) * step <= height and all(draw.textlength(line, font=face) <= width for line in lines):
            if dry_run:
                return {'font_size': size, 'lines': lines, 'box': list(box)}
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
            return {'font_size': size, 'lines': lines, 'box': list(box)}
    raise ValueError('Editorial text does not fit; refusing clipped or truncated image')


def story(message, include_metadata=False):
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
    metadata = []
    if match:
        metadata = [line for line in rest if re.fullmatch(r'\d{4}-\d{2}-\d{2}｜(?:ホーム|アウェイ)', line)]
        rest = [line for line in rest if line not in metadata]
    # Spread the verbatim paragraphs across three columns without adding data.
    groups = ['', '', '']
    for line in rest:
        index = min(range(3), key=lambda i: len(groups[i]))
        groups[index] += ('\n' if groups[index] else '') + line
    result = (headline, match, groups)
    return (*result, metadata) if include_metadata else result


def render_content_card(slot, message, destination, source=None):
    if slot not in LABELS:
        raise ValueError('Unknown slot')
    if len(clean(message)) > 600:
        raise ValueError('Caption exceeds supported card length')
    headline, match, groups, metadata = story(message, include_metadata=True)
    with Image.open(BACKGROUND) as background:
        if background.size != (W, H):
            raise ValueError('Approved stadium template dimensions changed')
        im = background.convert('RGB')
    d = ImageDraw.Draw(im)
    audit = {'schema_version': 1, 'template_version': 4, 'slot': slot,
             'dimensions': [W, H], 'source': source,
             'headline': headline, 'score_from_caption': list(match) if match else None,
             'match_metadata': metadata, 'panels': []}
    fitted(d, 'STVV LAB', (109, 28, 300, 46), 42, 30)
    fitted(d, '非公式ファンメディア', (112, 79, 300, 26), 20, 18)
    first, second = LABELS[slot]
    audit['headings'] = [brush_title(d, first, (388, 8, 760, 170), YELLOW),
                         brush_title(d, second, (382, 169, 790, 193), WHITE)]
    audit['heading_sweep'] = brush_sweep(d, (448, 350, 520, 35))
    if match:
        own, other, opponent = match
        if metadata:
            audit['metadata_layout'] = fitted(d, ' / '.join(metadata), (365, 402, 650, 27), 22, 18)
        team_y = 444 if metadata else 424
        fitted(d, 'STVV', (365, team_y, 290, 65), 52, 30, YELLOW)
        fitted(d, opponent, (755, team_y + 1, 250, 75), 43, 23)
        fitted(d, own + '–' + other, (540, 505, 470, 155), 142, 85, YELLOW)
        audit['headline_layout'] = fitted(d, headline, (365, 678, 650, 70), 46, 23)
    else:
        audit['headline_layout'] = fitted(d, headline, (368, 440, 632, 267), 70, 24)
    for value, (left, top, width, height) in panel_boxes(groups):
        plate = Image.new('RGBA', (width, height), (2, 12, 28, 230))
        pd = ImageDraw.Draw(plate)
        pd.rectangle((0, 0, width - 1, height - 1), outline=(140, 168, 190, 160), width=2)
        im.paste(plate, (left, top), plate)
        d.rectangle((left + 26, top + 25, left + 80, top + 32), fill=YELLOW)
        parts = panel_parts(value)
        if parts:
            lead, _, body = parts
            try:
                fitted(d, lead, (left + 26, top + 61, width - 52, 76), 62, 24, dry_run=True)
                fitted(d, body, (left + 26, top + 149, width - 52, 88), 40, 22, dry_run=True)
            except ValueError:
                # Long copy keeps the proven full-panel layout; no dropped text.
                parts = None
        if parts:
            lead, delimiter, body = parts
            lead_layout = fitted(d, lead, (left + 26, top + 61, width - 52, 76), 62, 24)
            body_layout = fitted(d, body, (left + 26, top + 149, width - 52, 88), 40, 22, YELLOW)
            audit['panels'].append({'text': value, 'hierarchy': 'lead-and-detail',
                                    'delimiter': delimiter, 'parts': [lead, body],
                                    'font_size': min(lead_layout['font_size'], body_layout['font_size']),
                                    'lead_layout': lead_layout, 'body_layout': body_layout})
        else:
            details = fitted(d, value.replace('、', '、\n'),
                             (left + 26, top + 62, width - 52, height - 83), 48, 22)
            audit['panels'].append({'text': value, 'hierarchy': 'body', **details})
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
    destination.with_suffix('.layout.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return destination
