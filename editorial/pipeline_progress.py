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
    return {
        "checked_at": now.isoformat(),
        "stages": {
            "01_source_collection": preparation.get("status", "unknown"),
            "02_duplicate_check": "local_history_only_remote_x_unverified",
            "03_candidate_selection": "needs_review" if candidates else "no_candidate",
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
            "approved_ready_cards": len(approved),
            "new_reservations": len(delivery.get("new_reservations", [])),
            "local_publication_records": len(history.get("publication_log", [])),
        },
        "next_action": (
            "Reconcile candidate topics with X posts before drafting; "
            "skip duplicates and continue scanning"
        ),
        "remote_x_checked": False,
        "buffer_checked": False,
        "posting_performed": False,
    }


if __name__ == "__main__":
    report = snapshot()
    print(json.dumps(report, ensure_ascii=False, indent=2))
