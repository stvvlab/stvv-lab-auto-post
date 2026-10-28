"""Reserve one reviewed image for an existing future slot; never shareNow.

Only the existing scheduled delivery wrapper enables live execution. A saved
pending intent survives every unknown result. Scheduled != sent != X verified.
"""
import copy
import hashlib
import json
import os
import re
from datetime import datetime, timedelta

import stvv_post as publisher
from buffer_reservations import BufferReservations, ReservationRejected
from content_guard import canonical_source, plain
from editorial_novelty import fact_metadata
from preparation_inventory import read_body
from prepared_media import exact_card, prepared_media, prepared_duplicate_reason, reviewed_official_body
from urllib.parse import urlparse
from reservation_preview import plan, future_slots


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timezone required')
    return result


def verify_echo(post, record):
    """Buffer asset.id is nullable; verify the immutable image URL when absent."""
    if (str(post.get('id', '')) != str(record.get('buffer_id', post.get('id', '')))
            or not post.get('id') or post.get('text') != record['text']
            or post.get('channelId') != publisher.CHANNEL
            or stamp(post.get('dueAt', '')) != stamp(record['due_at'])
            or not isinstance(post.get('assets'), list) or len(post['assets']) != 1
            or not isinstance(post['assets'][0], dict)):
        raise RuntimeError('Buffer reservation identity changed; do not resend')
    asset = post['assets'][0]
    aid = asset.get('id')
    dimensions = asset.get('image')
    source_ok = (
        asset.get('source') == record.get('image_url')
        and asset.get('type') == 'image'
        and asset.get('mimeType') == ({'.png': 'image/png', '.jpg': 'image/jpeg'}.get(
            os.path.splitext(str(record.get('asset_path', '')))[1].lower()))
        and isinstance(dimensions, dict)
        and [dimensions.get('width'), dimensions.get('height')] == record.get('dimensions'))
    # Buffer may return a null image ID, but its immutable source and image
    # metadata must always match. A non-null ID must not mask a wrong image.
    if not source_ok:
        raise RuntimeError('Buffer image identity changed (source/type/dimensions); do not resend')
    if record.get('buffer_asset_ids') and [aid] != record['buffer_asset_ids']:
        raise RuntimeError('Buffer image identity changed (asset ID); do not resend')
    if record.get('buffer_asset_sources') and (
            not source_ok or [asset.get('source')] != record['buffer_asset_sources']):
        raise RuntimeError('Buffer image identity changed (asset source); do not resend')


def remote_block(snapshot, proposal, history):
    known = {str(p.get('buffer_id')) for p in history['publication_log']}
    for post in snapshot['posts']:
        if plain(post['text']) == plain(proposal['text']):
            return 'remote_duplicate_caption'
        if post.get('dueAt') and stamp(post['dueAt']) == stamp(proposal['due_utc']):
            return 'remote_slot_occupied'
        urls = re.findall(r'https://(?:stvv\.jp/news/|stvv\.com/nl/nieuws/artikel/)[^\s]+', post['text'])
        if any(canonical_source(url) == canonical_source(proposal['source_url']) for url in urls):
            # A supported reviewed first-start may follow an already known recap.
            # Unknown remote source use must never be waved through.
            if (str(post['id']) not in known or post['status'] != 'sent'
                    or not proposal.get('editorial_fact')):
                return 'remote_source_used_or_pending'
    return None


def reconcile(history, client, now, save):
    updates = []
    for key, record in history.get('reserved_posts', {}).items():
        if record.get('buffer_status') in {'sent', 'error'}:
            continue
        post = client.get_post(record['buffer_id'])
        verify_echo(post, record)
        status = post.get('status')
        if status not in {'scheduled', 'sending', 'sent', 'error'}:
            raise RuntimeError('Unknown reservation status; do not resend')
        if status == 'sent' and now < stamp(record['due_at']):
            raise RuntimeError('Buffer reports an early send; review required')
        record['buffer_status'] = status
        record['status_checked_at'] = now.isoformat()
        if status == 'sent' and not any(p.get('key') == key for p in history['publication_log']):
            history['publication_log'].append({**record, 'key': key,
                'delivery_state': 'buffer_reports_sent_x_unverified', 'x_display_verified': False})
            if record['source'] not in history['news']:
                history['news'].append(record['source'])
        updates.append({'key': key, 'buffer_status': status, 'x_display_verified': False})
    if updates:
        save(history)
    return updates


def run(history, now, client, save, session):
    # plan validates core ledger shape; reservation schema is separately strict.
    reservations = history.setdefault('reserved_posts', {})
    if not isinstance(reservations, dict) or not isinstance(history.get('news'), list):
        raise ValueError('Reservation ledger is malformed')
    for key, record in reservations.items():
        if (not isinstance(record, dict) or not all(record.get(k) for k in
                ('buffer_id', 'due_at', 'text', 'source', 'slot', 'image_url', 'buffer_status'))
                or key not in history['used_posts']
                or not ((isinstance(record.get('buffer_asset_ids'), list)
                          and len(record['buffer_asset_ids']) == 1
                          and isinstance(record['buffer_asset_ids'][0], str)
                          and bool(record['buffer_asset_ids'][0]))
                         or (isinstance(record.get('buffer_asset_sources'), list)
                             and record['buffer_asset_sources'] == [record.get('image_url')]))):
            raise ValueError('Reservation ledger is incomplete; do not resend')
    updates = reconcile(history, client, now, save)
    if history['pending_posts']:
        status = ('blocked_buffer_rejected' if all(p.get('send_state') == 'rejected_no_retry'
                  for p in history['pending_posts'].values()) else 'blocked_pending_outcome_unknown')
        return {'status': status, 'updates': updates,
                'pending_keys': list(history['pending_posts'])}
    if any(r.get('buffer_status') == 'error' for r in reservations.values()):
        return {'status': 'blocked_reservation_error', 'updates': updates}
    preview = plan(history, now)
    if not preview['proposals']:
        return {'status': 'skipped_no_verified_content', 'updates': updates, 'new_reservations': []}
    proposal = preview['proposals'][0]
    slot, message, source = proposal['slot'], proposal['text'], proposal['source_url']
    card = exact_card(slot, message, source)
    due = stamp(proposal['due_utc']).astimezone(publisher.JST)
    if card is None or (due, slot) not in future_slots(now):
        raise RuntimeError('Reviewed card or target slot changed')
    if urlparse(source).netloc == 'stvv.com':
        body = reviewed_official_body(session, card, now)
    else:
        if card['date_jst'].replace('-', '') not in source:
            raise RuntimeError('Official source date does not match reviewed card')
        body = read_body(session, source)
    if not body:
        raise RuntimeError('Official source body could not be verified')
    fact = fact_metadata(card, due) if 'editorial_fact' in card else None
    if 'editorial_fact' in card and (not fact or fact['claim'] not in body
            or hashlib.sha256(body.encode()).hexdigest() != fact['source_body_sha256']):
        raise RuntimeError('Reviewed official fact changed')
    if prepared_duplicate_reason(history, message, source, slot, due):
        raise RuntimeError('Publication duplicate detected')
    enabled, image = prepared_media(session, slot, card['text'], source)
    if not enabled or not image:
        raise RuntimeError('Reviewed immutable public image could not be verified')
    if fact:
        proposal['editorial_fact'] = fact
    snapshot = client.preflight()
    reason = remote_block(snapshot, proposal, history)
    if reason:
        return {'status': 'blocked_' + reason, 'updates': updates}
    # Recheck actual wall time after potentially slow preflight network reads.
    current = datetime.now(publisher.JST)
    if current > due - timedelta(minutes=30):
        return {'status': 'skipped_reservation_lead_expired', 'updates': updates}
    key = proposal['key']
    record = {'slot': slot, 'source': source, 'text': message, 'image_url': image,
              'asset_path': card['asset_path'], 'sha256': card['sha256'],
              'dimensions': card['dimensions'], 'due_at': proposal['due_utc'],
              'official_body_sha256': hashlib.sha256(body.encode()).hexdigest(),
              'reservation_key': proposal['preview_key'], 'created_at': current.isoformat(),
              'delivery_mode': 'customScheduled', 'x_display_verified': False}
    if fact:
        record['editorial_fact'] = fact
    history['pending_posts'][key] = copy.deepcopy(record)
    save(history)  # Must durably reach main before the ONE createPost attempt.
    try:
        post = client.schedule(message, image, proposal['due_utc'])
    except ReservationRejected:
        history['pending_posts'][key]['send_state'] = 'rejected_no_retry'
        save(history)
        raise
    verify_echo(post, record)
    if post.get('status') != 'scheduled':
        raise RuntimeError('Reservation was not confirmed scheduled; do not resend')
    asset = post['assets'][0]
    identity = ({'buffer_asset_ids': [asset['id']]}
                if isinstance(asset.get('id'), str) and asset['id']
                else {'buffer_asset_sources': [asset['source']]})
    record.update(buffer_id=str(post['id']), buffer_status='scheduled',
                  **identity, submitted_at=datetime.now(publisher.JST).isoformat())
    reservations[key] = record
    history['used_posts'].append(key)  # Occupied, not proof of publication.
    del history['pending_posts'][key]
    save(history)  # Unknown persistence failure must never cause a second send.
    return {'status': 'reserved_in_buffer', 'updates': updates,
            'new_reservations': [{'key': key, 'buffer_id': record['buffer_id'],
                                  'due_at': record['due_at'], 'buffer_status': 'scheduled',
                                  'x_display_verified': False}]}


def main():
    if (os.getenv('GITHUB_EVENT_NAME') != 'schedule'
            or os.getenv('GITHUB_SCHEDULE') not in publisher.SLOTS
            or os.getenv('STVV_ADVANCE_RESERVATIONS') != 'true'):
        raise RuntimeError('Live reservations require the existing scheduled delivery step')
    result = run(publisher.load(), datetime.now(publisher.JST), BufferReservations(),
                 publisher.save, publisher.SESSION)
    publisher.log('RESERVATION_RESULT ' + json.dumps(result, ensure_ascii=False))
    return result['status']
