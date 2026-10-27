"""Convert a local original image into a time-free fixture review poster.

This is an unapproved design preview only. It never edits the ready-card
manifest, calls Buffer, or authorizes public use of source artwork.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

from fixture_draft_art import validate

W, H = 1200, 1500
YELLOW = '#ffdb28'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font(size):
    return ImageFont.truetype('DejaVuSans-Bold.ttf', size)


def make_preview(report, artwork, output, metadata, today):
    """Create a poster and a review packet, never a publishable manifest."""
    fixture_date = validate(report, today)
    artwork, output, metadata = map(Path, (artwork, output, metadata))
    if artwork.is_symlink() or not artwork.is_file():
        raise ValueError('A real local artwork file is required')
    if artwork.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('Unsupported source artwork type')
    if artwork.stat().st_size > 15_000_000:
        raise ValueError('Source artwork exceeds review limit')
    if artwork.resolve() == output.resolve():
        raise ValueError('Do not overwrite the original artwork')
    with Image.open(artwork) as source:
        source.verify()
    with Image.open(artwork) as source:
        image = ImageOps.fit(source.convert('RGB'), (W, H),
                             method=Image.Resampling.LANCZOS,
                             centering=(0.5, 0.5)).convert('RGBA')
    # Translucent dark bands protect text without flattening the art.
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(0, 290):
        d.line((0, y, W, y), fill=(3, 12, 30, int(224 * (1-y/290))))
    for y in range(1100, H):
        d.line((0, y, W, y), fill=(3, 12, 30, int(215 * ((y-1100)/400))))
    image = Image.alpha_composite(image, overlay)
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((70, 65, 360, 130), radius=11, fill=YELLOW)
    d.text((91, 76), 'STVV LAB', font=font(37), fill='#07152b')
    d.text((70, 165), 'NEXT MATCH', font=font(70), fill='white')
    d.line((70, 1175, 1130, 1175), fill=YELLOW, width=5)
    d.text((70, 1200), 'STVV', font=font(104), fill='white')
    d.text((440, 1241), 'VS', font=font(43), fill=YELLOW)
    d.text((560, 1217), 'OH LEUVEN', font=font(63), fill='white')
    # A Belgian local date differs from the JST calendar date. Do not put
    # an ambiguous date on Japanese-facing review artwork.
    d.text((70, 1350), 'MATCH PREVIEW', font=font(53), fill=YELLOW)
    d.text((70, 1450), 'UNAPPROVED REVIEW ART  /  KICKOFF OMITTED',
           font=font(19), fill='#d4dce8')
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(output, 'PNG', optimize=True)
    result = {
        'status': 'unapproved_creative_preview', 'reviewed': False,
        'can_publish': False, 'buffer_called': False, 'x_publication_performed': False,
        'fixture': report['fixture'], 'fixture_date_local': fixture_date.isoformat(),
        'source_conflict': report['status'] == 'official_sources_disagree_block_kickoff',
        'kickoff_omitted': True, 'date_omitted_from_artwork': True,
        'source_urls': [item['url'] for item in report['source_checks']],
        'original_artwork': str(artwork), 'original_sha256': digest(artwork),
        'preview_image': str(output), 'preview_sha256': digest(output),
        'dimensions': [W, H], 'subject': 'fictional football mascot, not a real player',
        'draft_caption': '⚽ 次戦プレビュー\nSTVV 対 OHルーベン\n注目ポイントは？\n\n公式日程：https://stvv.jp/game/2026-2027/',
        'required_review': [
            'source artwork rights and originality',
            'fictional mascot must not be presented as a real STVV player',
            'fixture still scheduled and kickoff discrepancy resolved or omitted',
            'novelty and prior-post duplicate gate',
            'mobile crop, typography, caption and visual quality',
            'explicit final approval and immutable public asset URL',
        ],
    }
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='reports/fixture-watch-latest.json')
    parser.add_argument('--artwork', required=True)
    parser.add_argument('--output', default='generated/fixture_creative_preview.png')
    parser.add_argument('--metadata', default='reports/fixture-creative-preview.json')
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    result = make_preview(report, args.artwork, args.output, args.metadata,
                          datetime.now(ZoneInfo('Asia/Tokyo')).date())
    print('Review-only creative preview:', result['preview_image'])


if __name__ == '__main__':
    main()
