"""Run the existing publisher once and retain honest, per-run delivery evidence.

No retries, dispatches, new schedules or alternative publishing transports.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import stvv_post as publisher

ROOT = Path(__file__).resolve().parent


def read_ledger(path):
    # Failure to read history is an error, never evidence of zero pending sends.
    return json.loads(path.read_text(encoding='utf-8'))


def queue_snapshot(root, history, now, slot):
    from prepared_media import prepared_duplicate_reason
    manifest = json.loads((root / 'editorial/imagegen_cards.json').read_text())
    candidates = []
    for card in manifest.get('cards', []):
        if card.get('status') != 'ready':
            continue
        reason = None
        if card.get('reviewed') is not True:
            reason = 'not_reviewed'
        elif slot not in card.get('slots', []):
            reason = 'different_slot'
        else:
            try:
                day = datetime.fromisoformat(card['date_jst']).date()
                if not 0 <= (now.date() - day).days <= 7:
                    reason = 'outside_freshness_window'
                elif publisher.x_length(card['text'] + publisher.HASHTAGS) > 270:
                    reason = 'over_safe_x_length'
                else:
                    reason = prepared_duplicate_reason(
                        history, card['text'], card['source_url'], slot, now)
            except (KeyError, TypeError, ValueError):
                reason = 'invalid_card_metadata'
        candidates.append({'source_url': card.get('source_url'),
                           'asset_path': card.get('asset_path'),
                           'slots': card.get('slots', []),
                           'selection_block': reason})
    return {'ready_cards': len(candidates), 'candidates': candidates,
            'note': 'Selection diagnosis only; official body and public image bytes '
                    'are checked by the publisher before sending.'}


def delivery_evidence(before, after, day, slot, *, advance=False):
    key = f'daily_{day}_{slot}'
    old_keys = {p.get('key') for p in before.get('publication_log', [])}
    accepted = [p for p in after.get('publication_log', [])
                if (advance or p.get('key') == key) and p.get('key') not in old_keys]
    pending = after.get('pending_posts', {})
    result = {'new_publications': accepted, 'pending_key': key if key in pending else None,
              'x_display_verified': False}
    if key in pending:
        result['delivery_state'] = 'send_outcome_unknown_do_not_retry'
    elif accepted:
        states = {p.get('buffer_status') for p in accepted}
        result['delivery_state'] = ('buffer_reports_sent_x_unverified'
                                    if states == {'sent'} else 'buffer_accepted_x_unverified')
    elif key in before.get('pending_posts', {}):
        result['delivery_state'] = 'previous_pending_requires_review'
    else:
        result['delivery_state'] = 'no_new_buffer_acceptance_recorded'
    if advance:
        old_reserved = before.get('reserved_posts', {})
        reserved = after.get('reserved_posts', {})
        result['new_reservations'] = [dict(r, key=k) for k, r in reserved.items()
                                      if k not in old_reserved]
        result['reservation_states'] = [
            {'key': k, 'buffer_status': r.get('buffer_status'), 'due_at': r.get('due_at'),
             'x_display_verified': False} for k, r in reserved.items()]
        result['pending_reservation_keys'] = list(pending)
        if pending:
            result['delivery_state'] = ('buffer_rejected_not_published'
                if all(p.get('send_state') == 'rejected_no_retry' for p in pending.values())
                else 'send_outcome_unknown_do_not_retry')
        elif any(r.get('buffer_status') == 'error' for r in reserved.values()):
            result['delivery_state'] = 'buffer_reservation_error_do_not_retry'
        elif accepted:
            result['delivery_state'] = 'buffer_reports_sent_x_unverified'
        elif reserved:
            # Drafts are a deliberate cancellation, not a scheduled delivery.
            # An unrecognized state is not evidence that Buffer will publish.
            statuses = {r.get('buffer_status') for r in reserved.values()}
            if not statuses <= {'scheduled', 'sending', 'sent', 'cancelled_by_user'}:
                result['delivery_state'] = 'buffer_reservation_state_unverified_do_not_retry'
            elif statuses & {'scheduled', 'sending'}:
                result['delivery_state'] = 'buffer_scheduled_not_published'
            elif 'cancelled_by_user' in statuses:
                result['delivery_state'] = 'buffer_cancelled_by_user_not_published'
            else:
                result['delivery_state'] = 'no_new_buffer_acceptance_recorded'
    return result


def main():
    # Only Actions' actual posting step opts in. CI test calls cannot create
    # production evidence or touch the real posting history.
    run_id = os.getenv('GITHUB_RUN_ID', '')
    if (os.getenv('STVV_DELIVERY_RECORD') != 'true' or not re.fullmatch(r'\d+', run_id)
            or os.getenv('GITHUB_EVENT_NAME') != 'schedule'):
        raise RuntimeError('Delivery recording requires the scheduled posting step')
    advance = os.getenv('STVV_ADVANCE_RESERVATIONS') == 'true'
    now = datetime.now(publisher.JST)
    slot, day = publisher.slot_for_run(now)
    _, hour, minute = publisher.SLOTS[os.environ['GITHUB_SCHEDULE']]
    scheduled = datetime.fromisoformat(day).replace(
        hour=hour, minute=minute, tzinfo=publisher.JST)
    ledger = ROOT / 'posted.json'
    before = read_ledger(ledger)
    report = {'started_at': now.isoformat(), 'slot': slot, 'date_jst': day,
              'scheduled_at': scheduled.isoformat(),
              'start_delay_seconds': max(0, int((now - scheduled).total_seconds())),
              'run_id': run_id,
              'workflow_url': f'https://github.com/stvvlab/stvv-lab-auto-post/actions/runs/{run_id}',
              'commit': os.getenv('GITHUB_SHA'), 'manual_dispatch_performed': False,
              'status': 'started', 'x_display_verified': False,
              'delivery_mode': 'advance_reservations' if advance else 'shareNow'}
    directory = ROOT / 'reports/delivery-runs'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{run_id}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    try:
        # Diagnosis must not block a valid publication if the diagnostic code fails.
        try:
            report['queue_before'] = queue_snapshot(ROOT, before, now, slot)
        except (OSError, ValueError, KeyError, TypeError) as error:
            report['queue_diagnosis_error'] = type(error).__name__
        if advance:
            from advance_reservations import main as reserve
            report['status'] = reserve()
        else:
            report['status'] = publisher.main()
    except Exception as error:
        # Exception messages may contain transport payloads; record only class.
        report.update(status='execution_failed', error_type=type(error).__name__)
        raise
    finally:
        report['finished_at'] = datetime.now(publisher.JST).isoformat()
        try:
            report.update(delivery_evidence(before, read_ledger(ledger), day, slot, advance=advance))
        except (OSError, ValueError, TypeError) as error:
            report.update(delivery_state='ledger_unreadable_do_not_retry',
                          ledger_error_type=type(error).__name__)
        content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        path.write_text(content)
        (ROOT / 'reports/delivery-latest.json').write_text(content)
        print('DELIVERY_EVIDENCE ' + json.dumps({k: report[k] for k in
              ('status', 'delivery_state', 'workflow_url')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
