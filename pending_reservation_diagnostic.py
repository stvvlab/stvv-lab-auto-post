"""Read-only investigation of unknown Buffer reservation outcome; NEVER resubmit."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import stvv_post as publisher
from buffer_reservations import BufferReservations

def same_time(a, b):
    try:
        x = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        y = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
        return x.tzinfo is not None and y.tzinfo is not None and x == y
    except (TypeError, ValueError):
        return False

def diagnose(history, posts):
    report = {"checked_at": datetime.now(publisher.JST).isoformat(),
              "mode": "read_only_no_mutations_no_retries",
              "pending_count": len(history.get("pending_posts", {})),
              "results": []}
    for key, record in history.get("pending_posts", {}).items():
        if record.get("delivery_mode") != "customScheduled":
            continue
        matches = [p for p in posts if p.get("channelId") == publisher.CHANNEL
                   and p.get("text") == record.get("text")]
        entries = []
        for post in matches:
            assets = post.get("assets")
            ids = [a.get("id") for a in assets if isinstance(a, dict)] if isinstance(assets, list) else []
            entries.append({"buffer_id": post.get("id"),
                            "status": post.get("status"),
                            "due_at_matches": same_time(post.get("dueAt"), record.get("due_at")),
                            "due_at": post.get("dueAt"),
                            "asset_count": len(assets) if isinstance(assets, list) else None,
                            "asset_ids_present": len(ids) == 1 and bool(ids[0]),
                            "asset_ids": ids if len(ids) == 1 and bool(ids[0]) else []})
        exact = [e for e in entries if e["due_at_matches"] and e["asset_ids_present"]
                 and e["status"] in ("scheduled", "sending", "sent")]
        report["results"].append({"pending_key": key, "caption_matched_posts": len(matches),
                                  "exact_remote_matches": len(exact), "matches": entries,
                                  "status": "unique_remote_reservation_found" if len(exact) == 1
                                  and len(matches) == 1 else "unresolved_do_not_retry"})
    return report

def main():
    result = {"checked_at": datetime.now(publisher.JST).isoformat(),
              "status": "not_checked", "mutation_count": 0,
              "mode": "read_only_no_mutations_no_retries"}
    try:
        history = publisher.load()
        snapshot = BufferReservations().preflight()
        result.update(diagnose(history, snapshot["posts"]))
        result["status"] = "read_only_completed"
    except Exception as exc:
        result.update(status="read_only_failed", error_type=type(exc).__name__)
        raise
    finally:
        path = Path("reports/pending-reservation-diagnostic-latest.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("PENDING_RESERVATION_DIAGNOSIS " + json.dumps(
            {"status": result["status"], "pending_count": result.get("pending_count"),
             "results": [{k: v for k, v in x.items() if k != "matches"}
                         for x in result.get("results", [])]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
