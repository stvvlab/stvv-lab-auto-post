"""Reproducible preview from the already verified editorial manifest. No posts."""
import json
from pathlib import Path
from content_card import render_content_card


def main():
    data = json.loads(Path('editorial/first_verified_card.json').read_text())
    message = '\n'.join([data['headline'],
        f"STVV {data['home_score']}–{data['away_score']} {data['away']}",
        *data['details']])
    render_content_card('recap', message, 'generated/auto_stadium_preview.jpg',
                        source=data['source_url'])
    print('STADIUM_PREVIEW_OK: no Buffer or X request sent')


if __name__ == '__main__':
    main()
