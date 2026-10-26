"""Buffer scheduling transport. One mutation per call, no automatic retries.

Read-only queries establish the connected account, scheduling permission,
capacity and remote duplicate evidence before a reservation can be attempted.
"""
import json
import os
import re
from urllib.parse import urlparse

import stvv_post as publisher

POST_FIELDS = 'id text channelId status dueAt assets { id }'


class ReservationRejected(RuntimeError):
    """Provider explicitly rejected creation; do not retry automatically."""


class BufferReservations:
    def __init__(self, session=None):
        self.session = session or publisher.SESSION

    def query(self, query, variables=None):
        key = os.getenv('BUFFER_API_KEY')
        if not key:
            raise RuntimeError('Buffer configuration missing')
        response = self.session.post(publisher.BUFFER,
            json={'query': query, 'variables': variables or {}}, timeout=25,
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get('errors') or not isinstance(data.get('data'), dict):
            # Provider errors may contain private payloads; do not log them.
            raise RuntimeError('Buffer query rejected or incomplete')
        return data['data']

    def posts(self, organization, statuses, *, channel=None):
        records, cursor = [], None
        for _ in range(5):
            filters = 'status: [' + ','.join(statuses) + ']'
            if channel:
                filters += ', channelIds: [' + json.dumps(channel) + ']'
            after = ', after: ' + json.dumps(cursor) if cursor else ''
            result = self.query('query { posts(first: 100' + after + ', input: {organizationId: '
                + json.dumps(organization) + ', filter: {' + filters + '}}) { edges { node { '
                + POST_FIELDS + ' } } pageInfo { hasNextPage endCursor } } }').get('posts')
            if not isinstance(result, dict) or not isinstance(result.get('edges'), list):
                raise RuntimeError('Buffer queue could not be enumerated')
            for edge in result['edges']:
                post = edge.get('node') if isinstance(edge, dict) else None
                if not isinstance(post, dict) or not all(post.get(k) for k in ('id', 'text', 'channelId', 'status')):
                    raise RuntimeError('Incomplete Buffer queue entry')
                records.append(post)
            page = result.get('pageInfo')
            if not isinstance(page, dict) or not isinstance(page.get('hasNextPage'), bool):
                raise RuntimeError('Buffer queue pagination is incomplete')
            if not page['hasNextPage']:
                return records
            next_cursor = page.get('endCursor')
            if not next_cursor or next_cursor == cursor:
                raise RuntimeError('Buffer queue cursor is incomplete')
            cursor = next_cursor
        raise RuntimeError('Buffer queue exceeds safe enumeration bound')

    def preflight(self):
        account = self.query('query { account { organizations { id limits { scheduledPosts } } } }').get('account')
        organizations = account.get('organizations') if isinstance(account, dict) else None
        if not isinstance(organizations, list):
            raise RuntimeError('Buffer organization could not be verified')
        matches = []
        for organization in organizations:
            oid = organization.get('id')
            if not oid:
                raise RuntimeError('Invalid Buffer organization')
            channels = self.query('query { channels(input: {organizationId: ' + json.dumps(oid)
                + '}) { id name service externalLink isDisconnected isLocked isQueuePaused allowedActions } }').get('channels')
            if not isinstance(channels, list):
                raise RuntimeError('Buffer channels could not be verified')
            matches.extend((organization, channel) for channel in channels
                           if channel.get('id') == publisher.CHANNEL)
        if len(matches) != 1:
            raise RuntimeError('Buffer target channel is absent or ambiguous')
        organization, channel = matches[0]
        link = urlparse(channel.get('externalLink') or '')
        handle = str(channel.get('name', '')).lstrip('@').lower()
        if (channel.get('service') != 'twitter' or handle != 'stvvlabo'
                or link.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}
                or link.path.rstrip('/').lower() != '/stvvlabo'
                or any(channel.get(k) is not False for k in ('isDisconnected', 'isLocked', 'isQueuePaused'))
                or 'scheduleUpdates' not in channel.get('allowedActions', [])):
            raise RuntimeError('Connected @stvvlabo scheduling permission is not verified')
        limit = (organization.get('limits') or {}).get('scheduledPosts')
        # Do not guess the meaning of undocumented negative/unlimited sentinels.
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise RuntimeError('Buffer scheduling capacity is not verified')
        active = self.posts(organization['id'], ['scheduled', 'sending', 'needs_approval', 'error'])
        if len(active) >= limit:
            raise RuntimeError('Buffer scheduling capacity exhausted; no upgrade attempted')
        sent = self.posts(organization['id'], ['sent'], channel=publisher.CHANNEL)
        return {'channel_id': publisher.CHANNEL, 'scheduled_limit': limit,
                'active_count': len(active), 'remaining_capacity': limit - len(active),
                'posts': [p for p in active + sent if p['channelId'] == publisher.CHANNEL]}

    def get_post(self, post_id):
        post = self.query('query { post(input: {id: ' + json.dumps(post_id) + '}) { '
                          + POST_FIELDS + ' } }').get('post')
        if not isinstance(post, dict):
            raise RuntimeError('Reservation status is unavailable; do not resend')
        return post

    def schedule(self, text, image_url, due_utc):
        if publisher.x_length(text) > 270 or not image_url:
            raise ValueError('A valid exact caption and reviewed image are required')
        data = self.query('''mutation ReservePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id text channelId status dueAt assets { id } } }
            ... on MutationError { message }
          }
        }''', {'input': {'text': text, 'channelId': publisher.CHANNEL,
            'schedulingType': 'automatic', 'mode': 'customScheduled', 'dueAt': due_utc,
            'assets': [{'image': {'url': image_url}}]}})
        post = (data.get('createPost') or {}).get('post')
        if not isinstance(post, dict) or not post.get('id'):
            if (data.get('createPost') or {}).get('message'):
                raise ReservationRejected('Buffer rejected reservation; no automatic retry')
            raise RuntimeError('Buffer reservation outcome unknown; do not resend')
        return post


def probe():
    """Read-only capability measurement; never creates a post or accesses X API."""
    from datetime import datetime
    from pathlib import Path
    result = {'checked_at': datetime.now(publisher.JST).isoformat(),
              'status': 'not_verified', 'mutations_attempted': 0,
              'paid_api_or_contract_change': False}
    try:
        client = BufferReservations()
        snapshot = client.preflight()
        result.update({k: v for k, v in snapshot.items() if k != 'posts'})
        history = publisher.load()
        known = [p for p in history['publication_log'] if p.get('buffer_id')]
        if known:
            post = client.get_post(known[-1]['buffer_id'])
            if post.get('channelId') != publisher.CHANNEL or post.get('text') != known[-1]['text']:
                raise RuntimeError('Read-only post binding differs from ledger')
            result['known_post_status_query_verified'] = True
        else:
            raise RuntimeError('No known post to verify the status query')
        result['status'] = 'read_permission_capacity_and_status_query_verified'
    except Exception as error:
        result['error_type'] = type(error).__name__
        # Only our sanitized local reasons are exposed, never HTTP bodies/keys.
        if type(error) is RuntimeError:
            result['reason'] = str(error)
        raise
    finally:
        path = Path('reports/reservation-capability.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print('RESERVATION_CAPABILITY ' + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    probe()
