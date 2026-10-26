"""Generate an unapproved, Adobe-free fixture preview from checked official listings.

No approval, Buffer send, X publication, or manifest/ledger write is possible here.
"""
import argparse
import hashlib
import json
from datetime import date, datetime, timezone
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


def render(fixture_date, destination):
    """Fact-free geometric artwork; never render conflicting kickoff time."""
    im = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(im)
    variant = fixture_date.toordinal() % 3
    colors = ['#142f51', '#173c61', '#122946']
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(7 + int(7*t), 21 + int(13*t), 43 + int(20*t)))
    if variant == 0:
        for x in range(-300, 1500, 170):
            d.polygon([(x, 0), (x+85, 0), (x+500, H), (x+415, H)], fill=colors[0])
    elif variant == 1:
        for r in (210, 330, 455, 600, 750):
            d.ellipse((780-r, 760-r, 780+r, 760+r), outline=colors[1], width=16)
        d.polygon([(0, 810), (1200, 390), (1200, 680), (0, 1100)], fill=colors[2])
    else:
        for y in range(150, 1450, 140):
            d.line((0, y, 1200, y-110), fill=colors[1], width=14)
        d.polygon([(570, 0), (1200, 0), (1200, 1020), (930, 1170)], fill=colors[0])
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
    date_label = fixture_date.strftime('%d %b %Y').upper()
    d.text((96, 1259), date_label, font=font(62), fill=NAVY)
    d.text((65, 1412), 'PREVIEW  /  KICKOFF TIME OMITTED', font=font(25), fill='#b8c8da')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination, 'PNG', optimize=True)
    return destination


def prepare(report, output, metadata, today):
    fixture_date = validate(report, today)
    path = render(fixture_date, output)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = {
        'status': 'unreviewed_artwork_draft', 'reviewed': False, 'can_publish': False,
        'source_fixture': report['fixture'], 'fixture_date_local': fixture_date.isoformat(),
        'kickoff_omitted': True, 'source_conflict': report['status'] == 'official_sources_disagree_block_kickoff',
        'source_urls': [x['url'] for x in report['source_checks']],
        'image_path': str(path), 'sha256': digest, 'dimensions': [W, H],
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
        result = prepare(report, args.output, args.metadata, datetime.now(timezone.utc).date())
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
