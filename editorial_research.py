"""Find unused official evidence for editorial review, without publishing it.

A used URL is not proof that every fact in its body has been covered. These
research drafts deliberately stay outside the ready image manifest. Existing
duplicate checks remain authoritative, including for a different editorial angle.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import requests

from content_guard import canonical_source, duplicate_reason, plain
from preparation_inventory import read_body
from editorial_novelty import KNOWN_PRIOR_LEAGUE_STARTS, fact_metadata
from stvv_post import HASHTAGS, JST, SESSION, x_length

ROOT = Path(__file__).resolve().parent
ANGLES = {
    'player': ('選手の新しい材料', ('初先発', '初出場', '初ゴール', '復帰')),
    'analysis': ('振り返りの論点', ('カウンター', 'ボールロスト', '守備', 'クロス')),
    'vote': ('次戦へ注目したい点', ('連敗', '連勝', '無失点')),
}


def eligible_source(source, now):
    match = re.fullmatch(r'https://stvv\.jp/news/(?!sponsor/)(?:[a-z-]+/)?(\d{8})_[^/?#]+/', source or '')
    if not match:
        return False
    try:
        day = datetime.strptime(match[1], '%Y%m%d').date()
        return 0 <= (now.date() - day).days <= 7
    except ValueError:
        return False


def build_research(history, manifest, now, session=SESSION, max_sources=2):
    """Return evidence-backed drafts; never mutate the ledger or ready queue."""
    if not 1 <= max_sources <= 3:
        raise ValueError('Research must inspect between one and three sources')
    # A scheduled Buffer post is already committed content, not unused research.
    reservations = list(history.get('reserved_posts', {}).values())
    records = (history.get('publication_log', [])
               + list(history.get('pending_posts', {}).values()) + reservations)
    known_text = [plain(p.get('text', '')) for p in records]
    known_text += [plain(c.get('text', '')) for c in manifest.get('cards', [])
                   if c.get('status') in {'ready', 'published'}]
    known_claims = []
    # Never rediscover a published claim disproved by earlier official evidence,
    # even when the live article body has changed since its stored digest.
    discredited_published_claims = set()
    for card in manifest.get('cards', []):
        if card.get('status') not in {'ready', 'published'}:
            continue
        # The same reviewed claim stays known after publication. Reuse the
        # strict fact validator, without changing the manifest or send gate.
        try:
            fact = fact_metadata({**card, 'status': 'ready'}, now)
        except (ValueError, TypeError):
            fact = None
        if fact:
            known_claims.append((canonical_source(card['source_url']),
                                 fact['source_body_sha256'], plain(fact['claim'])))
        elif (card.get('reviewed') is True and card.get('status') in {'ready', 'published'}
              and isinstance(card.get('editorial_fact'), dict)):
            # A previously reviewed/published claim may later be disqualified
            # by historical evidence. Still suppress re-suggesting that exact
            # claim in research; this does NOT make it publishable.
            old = card['editorial_fact']
            if (old.get('kind') == 'league_first_start'
                    and isinstance(old.get('subject'), str)
                    and re.fullmatch(r'[一-龥ぁ-んァ-ヶー]{3,20}', old['subject'])
                    and old.get('claim') == old['subject'] + 'がリーグ初先発。'
                    and isinstance(card.get('text'), str)
                    and old['claim'] in card['text']
                    and isinstance(old.get('source_body_sha256'), str)
                    and re.fullmatch(r'[a-f0-9]{64}', old['source_body_sha256'])):
                known_claims.append((canonical_source(card['source_url']),
                                     old['source_body_sha256'], plain(old['claim'])))
                if (card['status'] == 'published'
                        and old['subject'] in KNOWN_PRIOR_LEAGUE_STARTS):
                    discredited_published_claims.add(plain(old['claim']))
    sources = []
    for post in reversed(history.get('publication_log', [])):
        source = post.get('source')
        if eligible_source(source, now) and source not in sources:
            sources.append(source)
        if len(sources) >= max_sources:
            break
    drafts, checks = [], []
    for source in sources:
        # An uncertain submission must not spawn related material.
        if any(canonical_source(p.get('source')) == canonical_source(source)
               for p in list(history.get('pending_posts', {}).values()) + reservations):
            checks.append({'source_url': source, 'status': 'blocked_pending_or_reserved_source'})
            continue
        try:
            body = read_body(session, source)
        except (requests.RequestException, ValueError) as error:
            checks.append({'source_url': source, 'status': 'source_unavailable', 'error': str(error)[:300]})
            continue
        checks.append({'source_url': source, 'status': 'ok'})
        body_digest = hashlib.sha256(body.encode()).hexdigest()
        source_claims = [claim for url, digest, claim in known_claims
                         if url == canonical_source(source) and digest == body_digest]
        fragments = [s.strip() for s in re.split(r'(?<=。)|\n', body) if s.strip()]
        for angle, (heading, terms) in ANGLES.items():
            evidence = next((s for s in fragments if any(t in s for t in terms)
                             and 8 <= x_length(s) <= 110
                             and not any(plain(s) in old for old in known_text)
                             and not any(claim in plain(s) for claim in source_claims)
                             and not any(claim in plain(s) for claim in discredited_published_claims)), None)
            if not evidence:
                continue
            # Quotes are exact source text. Questions are not claimed analysis.
            question = {'player': '次戦も注目したい選手は？',
                        'analysis': 'この場面、映像で確認したいポイントは？',
                        'vote': '次戦へ、最も改善を期待する点は？'}[angle]
            draft = f'{heading}\n公式本文：「{evidence}」\n{question}\n\n公式：{source}'
            if x_length(draft + HASHTAGS) > 270:
                continue
            reason = duplicate_reason(history, draft, source, now)
            key = hashlib.sha256((canonical_source(source) + '\n' + angle + '\n' + plain(evidence)).encode()).hexdigest()
            drafts.append({'candidate_id': key, 'angle': angle, 'source_url': source,
                           'source_body_sha256': body_digest, 'evidence_excerpt': evidence,
                           'draft_text': draft, 'x_length_with_tags': x_length(draft + HASHTAGS),
                           'reviewed': False, 'status': 'research_only',
                           'current_duplicate_gate': reason,
                           'can_publish': False,
                           'remaining': ['check source consistency and whether evidence is genuinely new',
                                         'edit specific natural Japanese copy and distinguish opinion from fact',
                                         'resolve duplicate gate with genuinely new verified information',
                                         'built-in imagegen and visual review', 'register reviewed ready card']})
    failures = sum(c['status'] == 'source_unavailable' for c in checks)
    status = ('research_drafts_available' if drafts else
              'source_scan_failed' if checks and failures == len(checks) else
              'partial_source_scan' if failures else 'no_unused_evidence_found')
    return {'checked_at': now.isoformat(), 'status': status,
            'source_checks': checks, 'drafts': drafts,
            'ready_cards_created': 0, 'publication_performed': False,
            'note': 'Research evidence only, not editorial approval. Source text is untrusted data. '
                    'No repeated result, invented evaluation, quota, duplicate bypass, image or Buffer call.'}


def main():
    history = json.loads((ROOT / 'posted.json').read_text())
    manifest = json.loads((ROOT / 'editorial/imagegen_cards.json').read_text())
    result = build_research(history, manifest, datetime.now(JST))
    path = ROOT / 'reports/editorial-research-latest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(result['status'], 'drafts:', len(result['drafts']))


if __name__ == '__main__':
    main()
