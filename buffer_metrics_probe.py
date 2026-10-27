"""Read-only Buffer engagement snapshot for existing sent STVV LAB posts.

Never sends, schedules, edits or deletes posts. Metrics are not X display proof.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

QUERY = '''query GetPostMetrics($id: PostId!) {
  post(input: { id: $id }) {
    id
    status
    metrics { type name value unit }
    metricsUpdatedAt
  }
}'''
MAX_REQUESTS = 5
MIN_AGE = timedelta(hours=48)
MAX_AGE = timedelta(days=14)


def eligible_posts(history, now, limit=MAX_REQUESTS):
    """Select recent sent posts; never query pending or unknown outcomes."""
    candidates = []
    for item in history.get('publication_log', []):
        if item.get('buffer_status') != 'sent' or not item.get('buffer_id'):
            continue
        try:
            submitted = datetime.fromisoformat(item['submitted_at'])
            if submitted.tzinfo is None:
                continue
            age = now - submitted.astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError):
            continue
        if MIN_AGE <= age <= MAX_AGE:
            candidates.append((submitted, item))
    candidates.sort(key=lambda p: p[0], reverse=True)
    seen = set()
    result = []
    for _, item in candidates:
        if item['buffer_id'] in seen:
            continue
        seen.add(item['buffer_id'])
        result.append(item)
        if len(result) == min(MAX_REQUESTS, max(0, limit)):
            break
    return result[:max(0, min(limit, MAX_REQUESTS))]


def read_metrics(session, key, post_id):
    response = session.post('https://api.buffer.com',
                            json={'query': QUERY, 'variables': {'id': post_id}},
                            headers={'Authorization': 'Bearer ' + key,
                                     'Content-Type': 'application/json'}, timeout=25)
    response.raise_for_status()
    body = response.json()
    if body.get('errors'):
        raise ValueError('buffer_graphql_rejected')
    post = (body.get('data') or {}).get('post')
    if not isinstance(post, dict) or post.get('id') != post_id:
        raise ValueError('buffer_post_id_mismatch_or_missing')
    if post.get('status') != 'sent':
        raise ValueError('buffer_post_not_sent')
    metrics = post.get('metrics')
    if metrics is not None and not isinstance(metrics, list):
        raise ValueError('buffer_metrics_malformed')
    clean = {}
    for m in metrics or []:
        if not isinstance(m, dict) or not isinstance(m.get('type'), str):
            continue
        value = m.get('value')
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        unit = m.get('unit')
        if unit not in ('count', 'percentage'):
            continue
        clean[m['type']] = {'value': value, 'unit': unit}
    return {'buffer_status': post.get('status'),
            'metrics_updated_at': post.get('metricsUpdatedAt'),
            'metrics': clean if metrics is not None else None,
            'metrics_state': 'available' if metrics is not None and post.get('metricsUpdatedAt')
                             else 'not_yet_available'}


def collect(history, now, session, key, limit=MAX_REQUESTS):
    selected = eligible_posts(history, now, limit)
    result = {'observed_at': now.isoformat(), 'source': 'Buffer GraphQL read-only post metrics',
              'x_display_verified': False, 'x_metrics_verified': False,
              'post_count': len(selected), 'api_requests': 0, 'posts_with_metrics': 0,
              'posts': [], 'status': 'no_eligible_sent_posts' if not selected else 'pending'}
    if not selected:
        return result
    if not key:
        result['status'] = 'missing_personal_api_key'
        return result
    for item in selected:
        entry = {'key': item.get('key'), 'slot': item.get('slot'),
                 'buffer_id': item['buffer_id'], 'submitted_at': item.get('submitted_at'),
                 'source_url': item.get('source'), 'x_display_verified': False}
        try:
            result['api_requests'] += 1
            entry.update(read_metrics(session, key, item['buffer_id']))
            if entry['metrics_state'] == 'available':
                result['posts_with_metrics'] += 1
        except Exception as exc:
            # No raw API body or credentials in artifacts. Never retry a failed request.
            entry.update(metrics_state='query_failed', error_type=type(exc).__name__)
        result['posts'].append(entry)
    result['status'] = ('metrics_collected' if result['posts_with_metrics'] == len(selected)
                        else 'partial_metrics' if result['posts_with_metrics']
                        else 'no_metrics_collected')
    return result


def main():
    import requests
    now = datetime.now(timezone.utc)
    history = json.loads(Path('posted.json').read_text(encoding='utf-8'))
    report = collect(history, now, requests.Session(), os.getenv('BUFFER_API_KEY'))
    target = Path('reports/buffer-metrics-latest.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('BUFFER_METRICS', json.dumps({k: report[k] for k in
          ('status', 'post_count', 'api_requests', 'posts_with_metrics')}, ensure_ascii=False))
    if report['status'] in ('missing_personal_api_key', 'no_metrics_collected'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
