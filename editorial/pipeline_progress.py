"""Read-only progress snapshot for the STVV editorial-to-publication pipeline.

Never approves, schedules, or publishes content. This is a diagnostic, not a
claim that external Buffer/X publication has been verified.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"read_error": str(exc)}


def snapshot(root=ROOT, now=None):
    now = now or datetime.now(JST)
    preparation = load_json(root / "reports/preparation-latest.json")
    delivery = load_json(root / "reports/delivery-latest.json")
    manifest = load_json(root / "editorial/imagegen_cards.json")
    history = load_json(root / "posted.json")
    cards = manifest.get("cards", [])
    candidates = preparation.get("candidates", [])
    if not isinstance(cards, list):
        cards = []
    if not isinstance(candidates, list):
        candidates = []
    approved = [c for c in cards if c.get("status") == "ready" and c.get("reviewed") is True]
    historical_sources = {
        c.get("source_url") for c in cards
        if c.get("status") in ("published", "buffer_sent_x_unverified",
                               "cancelled", "expired")
    }
    historical_sources.discard(None)
    # Include both the legacy used-URL ledger and recorded Buffer publications.
    # A manifest-only check can mistakenly classify already-sent stories as fresh.
    if isinstance(history, dict):
        historical_sources.update(url for url in history.get("news", []) if isinstance(url, str))
        historical_sources.update(
            entry.get("source") for entry in history.get("publication_log", [])
            if isinstance(entry, dict) and isinstance(entry.get("source"), str)
        )
    # Reject repeated URLs within the same batch as well as historical posts.
    # Missing source URLs must never be classified as fresh publishable stories.
    seen_sources = set(historical_sources)
    fresh_candidates = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("source_url")
        if not isinstance(source, str) or not source.strip():
            continue
        source = source.strip()
        if source in seen_sources:
            continue
        seen_sources.add(source)
        fresh_candidates.append(candidate)
    duplicate_source_candidates = len(candidates) - len(fresh_candidates)
    blocked_drafts = [
        {"source_url": c.get("source_url"), "status": c.get("status")}
        for c in cards
        if c.get("status") in ("draft_needs_asset_and_reapproval",
                               "draft_needs_review")
    ]
    return {
        "checked_at": now.isoformat(),
        "stages": {
            "01_source_collection": preparation.get("status", "unknown"),
            "02_duplicate_check": "local_history_only_remote_x_unverified",
            "03_candidate_selection": "needs_review" if fresh_candidates else "no_new_candidate",
            "04_caption": "requires_editorial_review",
            "05_image": "not_generated" if not preparation.get("image_generation_performed") else "generated",
            "06_chat_preview": "not_integrated",
            "07_chat_approval": "not_integrated",
            "08_buffer_reservation": delivery.get("status", "unknown"),
            "09_x_verification": "not_verified",
            "10_audit": "local_reports_available",
        },
        "counts": {
            "candidates": len(candidates),
            "fresh_local_candidates": len(fresh_candidates),
            "duplicate_source_candidates": duplicate_source_candidates,
            "blocked_manifest_drafts": len(blocked_drafts),
            "approved_ready_cards": len(approved),
            "new_reservations": len(delivery.get("new_reservations", [])),
            "local_publication_records": len(history.get("publication_log", [])),
        },
        "blocked_drafts": blocked_drafts,
        "fresh_candidate_sources": [c.get("source_url") for c in fresh_candidates],
        "next_action": (
            "Review locally fresh candidates against remote Buffer/X history; "
            "skip duplicate topics, then prepare a review bundle"
            if fresh_candidates else
            "Refresh official sources and seek a new nonduplicate candidate"
        ),
        "remote_x_checked": False,
        "buffer_checked": False,
        "posting_performed": False,
    }


if __name__ == "__main__":
    report = snapshot()
    print(json.dumps(report, ensure_ascii=False, indent=2))
