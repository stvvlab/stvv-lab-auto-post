"""Strict offline eligibility for a manually reviewed fixture on a season schedule.

Never sends, approves assets, or treats a shared season URL as a unique fact.
Live publishing integration requires separate reviewed identity and evidence checks.
"""
import re
import unicodedata
from datetime import date, timedelta
from urllib.parse import urlsplit
from content_guard import canonical_source, plain


# Time claims require exact reviewed evidence; a checked boolean alone cannot
# override conflicting official schedules. NFKC catches full-width clock text.
_TIME = re.compile(
    r'(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)'
    r'|(?:午前|午後)\s*(?:[01]?\d|2[0-3])\s*時(?:[0-5]?\d\s*分)?'
    r'|(?<!\d)(?:[01]?\d|2[0-3])\s*時(?:[0-5]?\d\s*分)?'
)


def _times(text):
    return set(_TIME.findall(unicodedata.normalize('NFKC', text)))


def _mentions_kickoff(text):
    normalized = unicodedata.normalize('NFKC', text)
    return bool(_times(text)) or any(
        term in normalized for term in ('キックオフ', '開始時刻', '試合開始')
    )


def review_fixture_candidate(card, now, history, official_text=None):
    if not isinstance(card, dict) or card.get("status") != "ready" or card.get("reviewed") is not True:
        return "not_approved"
    if card.get("kind") != "fixture_schedule" or card.get("auto_publish") is not True:
        return "not_enabled"
    source = card.get("source_url", "")
    url = urlsplit(source)
    if (url.scheme != "https" or url.netloc != "stvv.jp" or
            url.path != "/game/2026-2027/" or url.query or url.fragment):
        return "untrusted_schedule_url"
    try:
        match_day = date.fromisoformat(card["fixture_date_jst"])
        today = now.date()
    except (KeyError, ValueError, TypeError, AttributeError):
        return "invalid_match_date"
    if not today <= match_day <= today + timedelta(days=7):
        return "outside_fixture_window"
    opponent = card.get("opponent")
    caption = card.get("text")
    if not isinstance(opponent, str) or not isinstance(caption, str) or len(opponent) < 3:
        return "invalid_caption"
    if opponent not in caption or source not in caption or "STVV" not in caption:
        return "unverified_caption"
    if not isinstance(official_text, str):
        return "official_schedule_unverified"
    if _mentions_kickoff(caption):
        if card.get("kickoff_conflict") is True:
            return "conflicting_kickoff_sources"
        if card.get("kickoff_verified") is not True:
            return "unverified_kickoff"
        evidence = card.get("kickoff_evidence_excerpt")
        if (not isinstance(evidence, str) or not evidence
                or evidence not in official_text
                or not _times(caption)
                or not _times(caption).issubset(_times(evidence))):
            return "kickoff_evidence_missing"
    # Reject a season listing where opponent and date only occur in unrelated rows.
    # Evidence must be a reviewed, contiguous match-specific excerpt.
    excerpt = card.get("schedule_evidence_excerpt")
    date_label = f"{match_day.month}月{match_day.day}日"
    if (not isinstance(excerpt, str) or len(excerpt) > 700 or
            opponent not in excerpt or date_label not in excerpt or
            excerpt not in official_text):
        return "match_specific_schedule_evidence_missing"
    # The clock proof must belong to this same reviewed fixture row.
    # A matching clock elsewhere on the season page is not sufficient.
    if _mentions_kickoff(caption) and evidence not in excerpt:
        return "kickoff_evidence_not_match_specific"
    identity = f"fixture:{match_day.isoformat()}:{plain(opponent)}"
    if card.get("fixture_identity") != identity:
        return "missing_unique_fixture_identity"
    if identity in history.get("used_posts", []):
        return "fixture_already_used"
    for row in history.get("publication_log", []) + list(history.get("pending_posts", {}).values()) + list(history.get("reserved_posts", {}).values()):
        if not isinstance(row, dict):
            return "invalid_history"
        if row.get("fixture_identity") == identity:
            return "fixture_already_sent_or_pending"
        if row.get("source") == source and plain(row.get("text", "")) == plain(caption):
            return "identical_caption_already_used"
    if not card.get("asset_path") or not card.get("sha256"):
        return "reviewed_image_missing"
    return None
