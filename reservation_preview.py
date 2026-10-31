"""Offline proposal for advance Buffer reservations. This module never sends.

The live advance-reservation runner separately rechecks every proposal.
A proposal is not publication approval: network evidence must be rechecked
and a persistent reservation lifecycle implemented before enabling delivery.
"""
import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from prepared_media import prepared_candidates, prepared_duplicate_reason, exact_card
from quality_gate import audit, CRITICAL
from stvv_post import HASHTAGS, JST, SLOTS

ROOT = Path(__file__).resolve().parent

# Reduced pilot: three publication times per day. Legacy slots remain
# identifiable for existing reservations and historical reconciliation.
ACTIVE_RESERVATION_SLOTS = frozenset({'player', 'news', 'recap'})


def future_slots(now, *, lead_minutes=30, horizon_hours=36):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('An aware current time is required')
    if lead_minutes < 30 or not 0 < horizon_hours <= 36:
        raise ValueError('Use at least 30 minutes lead and at most 36 hours horizon')
    now = now.astimezone(JST)
    earliest = now + timedelta(minutes=lead_minutes)
    latest = now + timedelta(hours=horizon_hours)
    slots = []
    for offset in (0, 1, 2):
        for slot, hour, minute in SLOTS.values():
            if slot not in ACTIVE_RESERVATION_SLOTS:
                continue
            due = (now + timedelta(days=offset)).replace(
                hour=hour, minute=minute, second=0, microsecond=0)
            if earliest <= due <= latest:
                slots.append((due, slot))
    return sorted(slots)


def plan(history, now):
    # Fail closed on unreadable/malformed state, rather than assuming no sends.
    if (not isinstance(history, dict)
            or not isinstance(history.get('used_posts'), list)
            or not isinstance(history.get('pending_posts'), dict)
            or not isinstance(history.get('publication_log'), list)):
        raise ValueError('Complete publication history is required')
    slots = future_slots(now)
    report = {'checked_at': now.astimezone(JST).isoformat(),
              'mode': 'offline_preview_only', 'can_publish': False,
              'live_transport_changed': False, 'proposals': [], 'blocked': [],
              'remaining_before_activation': [
                  'Recheck official body, reviewed asset metadata and immutable public image bytes',
                  'Reconcile Buffer capacity and remote duplicates without paid API use',
                  'Persist pending before one send; reconcile unknown outcomes without resending',
                  'Keep scheduled acceptance separate from sent and X display verification']}
    # Read-only fixture draft diagnostic: never adds proposals or sends.
    draft_path = ROOT / 'editorial/drafts/brann_20261106.json'
    if draft_path.exists():
        from fixture_schedule_gate import review_fixture_candidate
        try:
            draft = json.loads(draft_path.read_text(encoding='utf-8'))
            reason = review_fixture_candidate(draft, now.astimezone(JST), history,
                                               official_text=None)
            report['fixture_draft'] = {
                'source_url': draft.get('source_url'),
                'status': 'blocked',
                'reason': reason or 'official_schedule_live_recheck_required',
                'included_in_proposals': False,
            }
        except (ValueError, TypeError, KeyError) as error:
            report['fixture_draft'] = {'status': 'blocked',
                                      'reason': 'invalid_fixture_draft',
                                      'included_in_proposals': False}
    occupied = (set(history['used_posts']) | set(history['pending_posts'])
                | set(history.get('reserved_posts', {})))
    occupied.update(p.get('key') for p in history['publication_log'])
    for due, slot in slots:
        key = f'daily_{due.date()}_{slot}'
        if key in occupied:
            report['blocked'].append({'key': key, 'reason': 'processed_or_pending'})
            continue
        # Reuse the publisher's exact reviewed caption and strict fact policy.
        # Freshness is evaluated at publication time, not preparation time.
        for text, source in prepared_candidates(slot, due):
            message = text + HASHTAGS
            problems = set(audit({'type': 'news', 'text': message,
                                  'source_url': source}, max_length=270)) & CRITICAL
            reason = (','.join(sorted(problems)) if problems else
                      prepared_duplicate_reason(history, message, source, slot, due))
            card = exact_card(slot, text, source)
            if card and date.fromisoformat(card['date_jst']) > now.astimezone(JST).date():
                reason = 'future_article_date'
            if reason or card is None:
                report['blocked'].append({'key': key, 'source_url': source,
                                          'reason': reason or 'ambiguous_reviewed_card'})
                continue
            media_identity = ('text_only:' + card['source_body_sha256']
                              if card.get('media_type') == 'text_only'
                              else str(card.get('sha256')))
            identity = hashlib.sha256((key + '\n' + source + '\n' + message + '\n'
                                       + media_identity).encode()).hexdigest()
            report['proposals'].append({
                'key': key, 'preview_key': identity, 'slot': slot,
                'source_url': source, 'text': message,
                'asset_path': card.get('asset_path'), 'sha256': card.get('sha256'),
                'media_type': 'text_only' if card.get('media_type') == 'text_only' else 'image',
                'due_jst': due.isoformat(),
                'due_utc': due.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'buffer_mode': 'customScheduled',
                'asset_and_official_body_recheck_required': True})
            return report  # At most one proposal, never fill empty slots.
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--now', help='Timezone-aware ISO date; default is now')
    parser.add_argument('--output', default='reports/reservation-preview-latest.json')
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(JST)
    history = json.loads((ROOT / 'posted.json').read_text())
    report = plan(history, now)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Offline reservation proposals: {len(report['proposals'])}; publishing disabled")


if __name__ == '__main__':
    main()
