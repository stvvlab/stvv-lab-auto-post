"""Prefer explicitly reviewed match-day posts within an existing publication slot.

No fixture inference, new cron triggers, text generation, or publishing here.
The usual approval, source, image, duplicate, and Buffer gates still apply.
"""

# Phase labels are editorial metadata, not live match-status evidence.
MATCHDAY_PURPOSES = frozenset({
    ("fixture", "matchday"),
    ("fixture", "lineup"),
    ("match", "lineup"),
    ("match", "final"),
    ("match", "recap"),
    ("result", "final"),
    ("result", "recap"),
})


def is_matchday_card(card, due):
    """A match-day priority requires explicit review and an exact due time."""
    if not isinstance(card, dict):
        return False
    purpose = card.get("editorial_purpose")
    return (
        card.get("reviewed") is True
        and card.get("status") == "ready"
        and isinstance(purpose, dict)
        and (purpose.get("kind"), purpose.get("phase")) in MATCHDAY_PURPOSES
        and isinstance(purpose.get("event_id"), str)
        and bool(purpose["event_id"].strip())
        and card.get("publish_due_jst") == due.isoformat()
    )


def prioritize(candidates, slot, due, lookup):
    """Stable ordering: approved match-day content before ordinary content.

    If no verified match-day card exists, preserve existing candidate order.
    No candidate is created or auto-approved by this policy.
    """
    decorated = []
    for index, (text, source) in enumerate(candidates):
        card = lookup(slot, text, source)
        decorated.append((0 if is_matchday_card(card, due) else 1,
                          index, (text, source)))
    return [candidate for _, _, candidate in sorted(decorated)]
