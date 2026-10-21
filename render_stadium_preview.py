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
    # Offline design evidence only. Publication still revalidates the live
    # official article and passes the independent content repetition gate.
    facts = json.loads(Path('editorial/official_match_facts.json').read_text())
    scorer_message = '\n'.join(['公式記録で振り返る得点時間',
        f"STVV {facts['score'].replace('-', '–')} {facts['opponent']}",
        *[f'{name}：{minute}分' for name, minute in facts['goals']]])
    render_content_card('data', scorer_message, 'generated/scorer_alignment_preview.jpg',
                        source=facts['source_url'])
    print('STADIUM_PREVIEW_OK: no Buffer or X request sent')


if __name__ == '__main__':
    main()
