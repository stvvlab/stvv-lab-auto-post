"""One editorial PNG; no people, invented fixtures, charts or paid services."""
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 1500
NAVY, YELLOW, WHITE = '#071329', '#ffe100', '#ffffff'


def face(size):
    candidates = [os.getenv('STVV_CARD_FONT', ''),
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
                  '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    raise RuntimeError('Japanese font required; refusing missing-glyph output')


def validate(data):
    required = {'key', 'source_url', 'verified_at', 'home', 'away',
                'home_score', 'away_score', 'headline', 'details', 'text'}
    if not required <= data.keys():
        raise ValueError('Missing verified editorial fields')
    if not data['source_url'].startswith('https://stvv.jp/'):
        raise ValueError('Official STVV source required')
    if data['home'] != 'STVV' or not data['away'].strip():
        raise ValueError('Explicit verified teams required')
    for field in ['home_score', 'away_score']:
        if type(data[field]) is not int or not 0 <= data[field] <= 30:
            raise ValueError('Explicit integer scores required')
    if len(data['details']) != 2 or not all(data['details']):
        raise ValueError('Exactly two verified detail lines required')
    return data


def render(data, destination):
    validate(data)
    im = Image.new('RGB', (WIDTH, HEIGHT), NAVY)
    d = ImageDraw.Draw(im)
    for y in range(HEIGHT):
        t = y / HEIGHT
        d.line((0, y, WIDTH, y), fill=(int(10+5*(1-t)), int(20+20*(1-t)), int(36+30*(1-t))))
    # Code-native adaptation of PR21's navy/yellow diagonal editorial motif.
    for x in range(0, WIDTH, 80):
        d.line((x, 0, x, HEIGHT), fill='#1a304a')
    d.polygon([(0, 530), (1200, 190), (1200, 300), (0, 640)], fill='#153d63')
    d.polygon([(1090, 840), (1200, 808), (1200, 834), (1090, 866)], fill=YELLOW)
    d.rectangle((0, 0, WIDTH, 18), fill=YELLOW)

    def text(x, y, value, size, color=WHITE, max_width=1060):
        f = face(size)
        box = d.textbbox((0, 0), value, font=f)
        if box[2] - box[0] > max_width:
            raise ValueError('Text does not fit; edit copy before publication: ' + value)
        d.text((x, y), value, font=f, fill=color)

    text(64, 49, 'STVV LAB', 52)
    text(66, 130, 'INDEPENDENT FOOTBALL MEDIA', 22, YELLOW)
    text(65, 220, 'MATCH', 103)
    text(63, 337, 'REVIEW.', 124, YELLOW)
    d.line((65, 520, 1135, 520), fill=YELLOW, width=5)
    text(66, 551, 'CROKY CUP  /  ROUND OF 32', 32, YELLOW)
    text(66, 619, data['home'], 48)
    text(450, 630, f"{data['home_score']}–{data['away_score']}", 170, YELLOW, 560)
    away_size = 48
    while away_size > 24 and d.textbbox((0, 0), data['away'], font=face(away_size))[2] > 270:
        away_size -= 1
    text(880, 640, data['away'], away_size, max_width=270)
    text(66, 900, data['headline'], 70)

    d.rectangle((64, 1040, 1136, 1280), fill='#071423')
    d.rectangle((64, 1040, 77, 1280), fill=YELLOW)
    text(106, 1073, data['details'][0], 41)
    text(106, 1153, data['details'][1], 41)
    d.line((65, 1350, 1135, 1350), fill=YELLOW, width=4)
    text(66, 1380, '出典：STVV日本公式サイト', 26)
    text(765, 1380, 'STVV LAB / 非公式', 26, YELLOW, 370)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination, format='PNG', optimize=True)
    return destination


if __name__ == '__main__':
    render(json.loads(Path('editorial/first_verified_card.json').read_text()),
           'generated/first_verified_card.png')
