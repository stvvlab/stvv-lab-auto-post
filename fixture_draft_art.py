"""Generate an unapproved, Adobe-free fixture preview from checked official listings.

No approval, Buffer send, X publication, or manifest/ledger write is possible here.
"""
import argparse
import hashlib
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SOURCES = {'stvv', 'ohl', 'stvv_jp'}
W, H = 1200, 1500
NAVY, YELLOW = '#07152b', '#ffdb28'


def validate(report, today):
    if not isinstance(report, dict) or report.get('fixture') != 'STVV - OH Leuven':
        raise ValueError('Unknown fixture; do not invent a match')
    try:
        fixture_date = date.fromisoformat(report['fixture_date_local'])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('Invalid fixture date') from exc
    if not today <= fixture_date <= date.fromordinal(today.toordinal() + 14):
        raise ValueError('Fixture expired or outside 14-day review window')
    if report.get('status') not in {
        'official_sources_disagree_block_kickoff', 'sources_agree_manual_review_required'
    }:
        raise ValueError('Official fixture source verification incomplete')
    checks = report.get('source_checks')
    if not isinstance(checks, list) or len(checks) != len(SOURCES):
        raise ValueError('Exactly three official sources required')
    checked = {x.get('source') for x in checks if isinstance(x, dict) and x.get('status') == 'ok'}
    if checked != SOURCES:
        raise ValueError('Unverified fixture source')
    times = report.get('source_times_local')
    if not isinstance(times, dict) or set(times) != SOURCES:
        raise ValueError('Missing source evidence')
    if not all(isinstance(t, str) and len(t) == 5 and t[2] == ':' and
               t[:2].isdigit() and t[3:].isdigit() and
               0 <= int(t[:2]) < 24 and 0 <= int(t[3:]) < 60 for t in times.values()):
        raise ValueError('Malformed kickoff evidence')
    if report['status'] == 'sources_agree_manual_review_required' and len(set(times.values())) != 1:
        raise ValueError('Status/evidence mismatch')
    if report['status'] == 'official_sources_disagree_block_kickoff' and len(set(times.values())) <= 1:
        raise ValueError('Status/evidence mismatch')
    return fixture_date


def font(size, bold=True):
    return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size)


def render(fixture_date, destination, variant=0):
    """Render one of three distinct, fact-safe concepts; never include kickoff."""
    if variant not in (0, 1, 2):
        raise ValueError('Unknown artwork variant')
    im = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(7 + int(7*t), 21 + int(13*t), 43 + int(20*t)))
    if variant == 0:  # Editorial type poster
        for x in range(-300, 1500, 170):
            d.polygon([(x, 0), (x+85, 0), (x+500, H), (x+415, H)], fill='#142f51')
        d.rectangle((0, 0, W, 18), fill=YELLOW)
        d.rounded_rectangle((65, 65, 540, 142), radius=13, fill=YELLOW)
        d.text((90, 78), 'STVV LAB', font=font(48), fill=NAVY)
        d.text((65, 175), 'INDEPENDENT FOOTBALL MEDIA', font=font(23, False), fill='#b8c8da')
        d.text((65, 320), 'NEXT', font=font(118), fill='#ffffff')
        d.text((60, 460), 'FIXTURE', font=font(134), fill=YELLOW)
        d.line((65, 650, 1135, 650), fill=YELLOW, width=7)
        d.text((65, 730), 'STVV', font=font(151), fill='#ffffff')
        d.text((70, 925), 'VS', font=font(75), fill=YELLOW)
        d.text((65, 1050), 'OH LEUVEN', font=font(88), fill='#ffffff')
        d.rectangle((65, 1240, 1135, 1360), fill=YELLOW)
        d.text((96, 1259), fixture_date.strftime('%d %b %Y').upper(),
               font=font(62), fill=NAVY)
    elif variant == 1:  # Split duel, with a different text hierarchy
        d.polygon([(640, 0), (W, 0), (W, H), (390, H)], fill=YELLOW)
        d.polygon([(0, 1080), (540, 860), (640, 1030), (0, 1310)], fill='#173c61')
        d.text((65, 75), 'STVV LAB', font=font(49), fill='#ffffff')
        d.text((65, 165), 'MATCH', font=font(104), fill='#ffffff')
        d.text((65, 285), 'PREVIEW', font=font(104), fill='#ffffff')
        d.line((65, 440, 1135, 440), fill='#ffffff', width=5)
        d.text((55, 570), 'STVV', font=font(132), fill='#ffffff')
        d.text((640, 615), 'OH', font=font(110), fill=NAVY)
        d.text((625, 750), 'LEUVEN', font=font(80), fill=NAVY)
        d.ellipse((476, 830, 728, 1082), fill=NAVY, outline='#ffffff', width=8)
        d.text((505, 883), 'VS', font=font(88), fill=YELLOW)
        d.rectangle((65, 1270, 1135, 1370), fill=NAVY)
        d.text((96, 1283), fixture_date.strftime('%d %b %Y').upper(),
               font=font(59), fill='#ffffff')
    else:  # Stadium-lines, symmetrical versus composition
        for r in (210, 330, 455, 600, 750):
            d.ellipse((600-r, 770-r, 600+r, 770+r), outline='#173c61', width=17)
        for x in (90, 270, 930, 1110):
            d.line((x, 0, 600, 800), fill='#122946', width=25)
        d.rectangle((0, 0, W, 22), fill=YELLOW)
        d.text((65, 75), 'STVV LAB', font=font(54), fill=YELLOW)
        d.text((65, 235), 'THE NEXT', font=font(86), fill='#ffffff')
        d.text((65, 360), 'MATCH', font=font(146), fill=YELLOW)
        d.rounded_rectangle((60, 605, 1140, 1170), radius=38, fill='#07152b',
                            outline=YELLOW, width=7)
        d.text((100, 635), 'STVV', font=font(154), fill='#ffffff')
        d.text((100, 820), 'VS', font=font(81), fill=YELLOW)
        d.text((100, 940), 'OH LEUVEN', font=font(91), fill='#ffffff')
        d.line((65, 1230, 1135, 1230), fill=YELLOW, width=8)
        d.text((65, 1270), fixture_date.strftime('%d %b %Y').upper(),
               font=font(72), fill='#ffffff')
    d.text((65, 1430), 'UNAPPROVED DRAFT  /  NO KICKOFF TIME',
           font=font(23), fill='#b8c8da')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination, 'PNG', optimize=True)
    return destination


def render_gallery(paths, destination):
    """Side-by-side review contact sheet; not a publishable asset."""
    concepts = ('EDITORIAL POSTER', 'SPLIT DUEL', 'STADIUM LINES')
    gallery = Image.new('RGB', (1180, 560), '#07152b')
    draw = ImageDraw.Draw(gallery)
    for i, path in enumerate(paths):
        with Image.open(path) as source:
            thumb = source.convert('RGB').resize((352, 440))
        gallery.paste(thumb, (20 + i * 390, 24))
        draw.text((20 + i * 390, 485), concepts[i], font=font(24), fill=YELLOW)
    draw.text((20, 525), 'REVIEW ONLY  -  NOT APPROVED FOR PUBLICATION',
              font=font(19), fill='#ffffff')
    destination = Path(destination)
    gallery.save(destination, 'PNG', optimize=True)
    return destination


def prepare(report, output, metadata, today):
    fixture_date = validate(report, today)
    variants = []
    paths = []
    for i, concept in enumerate(('editorial-poster', 'split-duel', 'stadium-lines')):
        target = Path(output) if i == 0 else Path(output).with_name(
            Path(output).stem + f'_alt_{i}' + Path(output).suffix)
        path = render(fixture_date, target, variant=i)
        paths.append(path)
        variants.append({
            'concept': concept, 'image_path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'dimensions': [W, H], 'reviewed': False, 'can_publish': False,
        })
    gallery = render_gallery(paths, Path(output).with_name(
        Path(output).stem + '_contact_sheet.png'))
    path = paths[0]
    digest = variants[0]['sha256']
    sidecar = {
        'status': 'unreviewed_artwork_draft', 'reviewed': False, 'can_publish': False,
        'source_fixture': report['fixture'], 'fixture_date_local': fixture_date.isoformat(),
        'kickoff_omitted': True, 'source_conflict': report['status'] == 'official_sources_disagree_block_kickoff',
        'source_urls': [x['url'] for x in report['source_checks']],
        'image_path': str(path), 'sha256': digest, 'dimensions': [W, H],
        'variants': variants, 'contact_sheet': str(gallery),
        'adobe_api_used': False, 'buffer_called': False, 'x_publication_performed': False,
        'remaining': ['editorial fact and novelty review', 'visual design approval',
                      'confirm fixture details', 'register reviewed asset separately if approved'],
    }
    metadata = Path(metadata)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return sidecar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='reports/fixture-watch-latest.json')
    parser.add_argument('--output', default='generated/fixture_draft_preview.png')
    parser.add_argument('--metadata', default='reports/fixture-draft-preview.json')
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding='utf-8'))
    try:
        result = prepare(report, args.output, args.metadata, datetime.now(ZoneInfo('Asia/Tokyo')).date())
    except ValueError as exc:
        # This fixture-specific pilot should stop creating art after the match,
        # rather than fail daily or fall back to unverified information.
        target = Path(args.metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            'status': 'skipped_unverified_or_expired',
            'reviewed': False, 'can_publish': False,
            'reason': str(exc), 'buffer_called': False,
            'x_publication_performed': False,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Fixture artwork skipped:', exc)
        return
    print('Fixture artwork generated for review only:', result['image_path'])


if __name__ == '__main__':
    main()
