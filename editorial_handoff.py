"""Deterministic read-only handoff from verified candidate inventory to editorial review.

A handoff is not approval and never queues Buffer/X publication.
"""
import json
import hashlib
from editorial_draft_suggestions import suggest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def build_handoff(preparation, *, now=None):
    now = now or datetime.now(JST)
    candidates = preparation.get("candidates", [])
    drafts = preparation.get("unapproved_draft_suggestions", [])
    if not isinstance(candidates, list) or not isinstance(drafts, list):
        raise ValueError("Malformed preparation inventory")
    eligible = [c for c in candidates
                if c.get("status") == "needs_editorial_review"
                and isinstance(c.get("source_body"), str)
                and c.get("body_sha256")]
    by_url = {d.get("source_url"): d for d in drafts
              if isinstance(d, dict) and d.get("status") == "draft_unapproved"}
    queue = []
    seen_urls = set()
    for item in eligible:
        url = item.get("source_url")
        body = item["source_body"]
        if not isinstance(url, str) or url in seen_urls:
            continue
        # Reject stale or tampered source bodies even when a cached draft exists.
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != item["body_sha256"]:
            continue
        seen_urls.add(url)
        # Recompute from the verified body when the inventory has no suggestion.
        # This keeps stage 03 -> 04 moving without granting approval.
        draft = by_url.get(item.get("source_url"))
        if draft and (draft.get("source_body_sha256") != item.get("body_sha256")
                      or not isinstance(draft.get("text"), str)
                      or not draft["text"].strip()
                      or len(draft["text"]) > 270):
            draft = None
        if draft is None:
            draft = suggest(item)
        queue.append({
            "source_url": item["source_url"],
            "official_heading": item.get("official_heading"),
            "date_jst": item.get("date_jst"),
            "source_body_sha256": item["body_sha256"],
            "caption": draft.get("text") if draft else None,
            "status": "draft_needs_review" if draft else "caption_needed",
            "next_step": "editorial_fact_check" if draft else "write_caption",
            "approved": False,
            "image_generated": False,
            "buffer_sent": False,
        })
    return {
        "checked_at": now.isoformat(),
        "status": "review_required" if queue else "no_verified_candidates",
        "items": queue,
        "skipped_count": len(preparation.get("skipped", [])),
        "publication_performed": False,
        "approval_performed": False,
    }


def main():
    root = Path(__file__).resolve().parent
    inventory = json.loads((root / "reports/preparation-latest.json").read_text(encoding="utf-8"))
    report = build_handoff(inventory)
    target = root / "reports/editorial-handoff-latest.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Editorial handoff: {len(report['items'])} candidates; no publishing")


if __name__ == "__main__":
    main()
