"""Produce conservative, unapproved copy suggestions from verified official bodies.

Offline only. No manifest registration, image generation, Buffer, or publishing.
"""
import hashlib
import re


def suggest(item):
    if item.get('status') != 'needs_editorial_review':
        return None
    body, url = item.get('source_body'), item.get('source_url')
    if not isinstance(body, str) or not isinstance(url, str):
        return None
    if not re.fullmatch(r'https://stvv\.jp/news/(?:team|event)/[0-9]{8}_[^/?#]+/', url):
        return None
    if hashlib.sha256(body.encode()).hexdigest() != item.get('body_sha256'):
        return None
    text = None
    if '/team/' in url:
        # Only extract the exact official termination statement. Do not infer
        # the next coach, reasons, or a match outcome.
        m = re.search(r'(フレデリック・デ・メイヤー[^。]{0,100}監督との契約を解除いたしました)', body)
        if m:
            text = '📢 STVV公式発表：' + m.group(1).replace('いたしました', 'した') + '。'
    elif '/event/' in url:
        if all(term in body for term in ('観戦会', 'ゲンク', '2026年11月29日（日）', '無料')):
            text = '📣 STVV公式観戦会が11月29日（日）に開催予定！ゲンク戦を日本から応援。参加費は無料です。'
    if text is None:
        return None
    text += '\n\n公式：' + url
    if len(text) > 270:
        return None
    return {'status': 'draft_unapproved', 'reviewed': False, 'auto_publish': False,
            'source_url': url, 'source_body_sha256': item['body_sha256'],
            'text': text, 'requires': ['editorial_fact_check', 'duplicate_check',
                                      'visual_review', 'explicit_approval']}


def suggestions(report):
    return [draft for item in report.get('candidates', [])
            if (draft := suggest(item)) is not None]
