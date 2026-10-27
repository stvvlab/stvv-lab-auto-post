"""Strict opt-in evidence for a pre-announced upcoming fixture.

An older official event article may support one timely preview, but it must
never become a generic freshness bypass. This module cannot approve an image,
send a post, or waive the normal duplicate and Buffer checks.
"""
import hashlib
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

SHA256 = re.compile(r"[a-f0-9]{64}\Z")
ARTICLE = re.compile(r"/news/(?:event|game)/(\d{8})_[^/]+/\Z")
CLOCK = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?!\d)")


def reviewed_fixture_date(card, now, body=None):
    """Return upcoming fixture date only when ALL review evidence is valid.

    When body is supplied, require byte-for-byte normalized article-body
    identity and the specific reviewed excerpt. None means not eligible.
    """
    if not isinstance(card, dict) or card.get("status") != "ready" or card.get("reviewed") is not True:
        return None
    meta = card.get("fixture_preview")
    if not isinstance(meta, dict) or meta.get("kickoff_omitted") is not True:
        return None
    source = card.get("source_url", "")
    parsed = urlparse(source)
    match = ARTICLE.fullmatch(parsed.path)
    if (parsed.scheme != "https" or parsed.netloc != "stvv.jp" or not match
            or parsed.query or parsed.fragment):
        return None
    try:
        published = date.fromisoformat(card["date_jst"])
        fixture = date.fromisoformat(meta["fixture_date_jst"])
        today = now.date() if isinstance(now, datetime) else now
    except (KeyError, TypeError, ValueError):
        return None
    if (not isinstance(today, date)
            or published.strftime("%Y%m%d") != match.group(1)
            or published > today or not today <= fixture <= today + timedelta(days=7)):
        return None
    caption = card.get("text")
    opponent = meta.get("opponent")
    date_label = meta.get("date_label")
    excerpt = meta.get("evidence_excerpt")
    digest = meta.get("source_body_sha256")
    if (not isinstance(caption, str) or not isinstance(opponent, str)
            or not isinstance(date_label, str) or not isinstance(excerpt, str)
            or not isinstance(digest, str) or not SHA256.fullmatch(digest)
            or len(opponent.strip()) < 3 or len(excerpt.strip()) < 15
            or len(date_label.strip()) < 4 or source not in caption
            or "STVV" not in caption or opponent not in caption
            or date_label not in caption or CLOCK.search(caption)
            or "キックオフ" in caption or "開始時刻" in caption):
        return None
    # Require a human-reviewed date label with the exact fixture month/day.
    if date_label != f"{fixture.month}月{fixture.day}日":
        return None
    if body is not None:
        if (not isinstance(body, str) or excerpt not in body
                or opponent not in body
                or hashlib.sha256(body.encode("utf-8")).hexdigest() != digest):
            return None
    return fixture
