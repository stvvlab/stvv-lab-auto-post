"""Read-only handoff for correcting a verified @stvvlabo post in X's own UI.

This script NEVER sends, schedules, stages pending, or marks a reply published.
It intentionally leaves a human to review and click Reply in the parent thread.
"""
import argparse
import copy
import json
from pathlib import Path

import supplemental_replies as replies
from preparation_inventory import read_body
from stvv_post import HASHTAGS, SESSION, x_length

ROOT = Path(__file__).resolve().parent


def prepare_manual_handoff(history, queue, parent_key, official_body):
    if not isinstance(history, dict) or not isinstance(queue, dict):
        raise ValueError('Publication history and reply queue are required')
    if queue.get('enabled') is not False or queue.get('transport') is not None:
        raise ValueError('This manual-only handoff requires a disabled reply transport')
    matches = [r for r in queue.get('replies', [])
               if isinstance(r, dict) and r.get('parent_key') == parent_key
               and r.get('kind') == 'correction']
    if len(matches) != 1:
        raise ValueError('Exactly one correction draft must match the parent')
    draft = matches[0]
    if draft.get('status') != 'draft' or draft.get('reviewed') is not False:
        raise ValueError('Handoff is for an unapproved correction draft only')
    if '訂正' not in draft.get('text', '') or 'リーグ初先発' not in draft.get('text', ''):
        raise ValueError('The proposed correction is not explicit')
    if not isinstance(official_body, str) or not draft.get('evidence_excerpt') or draft['evidence_excerpt'] not in official_body:
        raise ValueError('The earlier official match evidence was not verified')
    # Reuse the production parent/source binding validator on an ephemeral copy.
    # Never save or return the ephemeral reviewed/ready status.
    probe = {**draft, 'status': 'ready', 'reviewed': True}
    checked = replies.validate_candidate(probe, history)
    if x_length(checked['text']) > 270:
        raise ValueError('Correction exceeds the conservative X text limit')
    originals = [p for p in history.get('publication_log', [])
                 if p.get('key') == parent_key]
    if len(originals) != 1 or 'リーグ初先発' not in originals[0].get('text', ''):
        raise ValueError('The parent does not contain the claim being corrected')
    return {'status': 'manual_review_required', 'auto_send': False,
            'parent_x_url': checked['parent_x_url'], 'text_to_review': checked['text'],
            'official_source': checked['source_url'],
            'note': 'Open the verified parent in X, review the correction, and reply manually. '
                    'This does not prove a reply was sent or publicly displayed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-key', default='daily_2026-10-26_vote')
    args = parser.parse_args()
    history = json.loads((ROOT / 'posted.json').read_text(encoding='utf-8'))
    queue = json.loads((ROOT / 'editorial/supplemental_replies.json').read_text(encoding='utf-8'))
    candidates = [r for r in queue.get('replies', [])
                  if r.get('parent_key') == args.parent_key and r.get('kind') == 'correction']
    if len(candidates) != 1:
        raise SystemExit('Correction draft unavailable or ambiguous')
    source = replies.canonical_source(candidates[0]['source_url'])
    body = read_body(SESSION, source)
    result = prepare_manual_handoff(history, queue, args.parent_key, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
