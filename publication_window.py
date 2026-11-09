"""A small shared timing gate for reviewed scheduled copy.

Exact-time posts stay exact by default. Reviewers may explicitly approve a
bounded delivery window for content that remains accurate after a delayed cron.
Never extend an old match reminder automatically.
"""
from datetime import datetime, timedelta


def due_block_reason(card, now):
    due_raw = card.get("publish_due_jst")
    end_raw = card.get("publish_window_end_jst")
    if due_raw is None:
        return "invalid_publish_window_without_due" if end_raw is not None else None
    try:
        due = datetime.fromisoformat(due_raw)
        if due.tzinfo is None or due.utcoffset() is None:
            return "invalid_fixed_publish_due"
        if now.tzinfo is None or now.utcoffset() is None:
            return "invalid_fixed_publish_due"
        if end_raw is None:
            # Preserve exact-time behavior for existing user-reviewed reminders.
            return None if due == now else (
                "fixed_publish_due_not_reached" if now < due
                else "fixed_publish_due_missed")
        end = datetime.fromisoformat(end_raw)
        if end.tzinfo is None or end.utcoffset() is None:
            return "invalid_publish_window"
        if card.get("publish_window_reviewed") is not True:
            return "unreviewed_publish_window"
        # A bounded grace period cannot turn a stale fixture into evergreen copy.
        if not due < end <= due + timedelta(hours=6):
            return "invalid_publish_window"
        if now < due:
            return "fixed_publish_due_not_reached"
        if now > end:
            return "publish_window_expired"
        return None
    except (TypeError, ValueError, OverflowError):
        return "invalid_publish_window"
