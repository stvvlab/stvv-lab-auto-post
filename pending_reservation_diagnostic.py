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

def scan_all_channel_posts(client):
    """Read all statuses (including drafts) without any mutation."""
    account = client.query("query { account { organizations { id } } }").get("account")
    orgs = account.get("organizations") if isinstance(account, dict) else None
    if not isinstance(orgs, list):
        raise RuntimeError("Buffer organizations unavailable")
    found = []
    for org in orgs:
        oid = org.get("id")
        if not oid:
            continue
        cursor = None
        for _ in range(5):
            after = ", after: " + json.dumps(cursor) if cursor else ""
            query = ("query { posts(first: 100" + after + ", input: {organizationId: "
                     + json.dumps(oid) + "}) { edges { node { id text channelId status dueAt assets { id } } } "
                     "pageInfo { hasNextPage endCursor } } }")
            response = client.query(query).get("posts")
            if not isinstance(response, dict) or not isinstance(response.get("edges"), list):
                raise RuntimeError("Unfiltered Buffer listing unavailable")
            for edge in response["edges"]:
                node = edge.get("node") if isinstance(edge, dict) else None
                if isinstance(node, dict) and node.get("channelId") == publisher.CHANNEL:
                    found.append(node)
            page = response.get("pageInfo") or {}
            if page.get("hasNextPage") is False:
                return found
            cursor = page.get("endCursor")
            if not cursor:
                raise RuntimeError("Buffer pagination cursor missing")
    return found

def main():
    result = {"checked_at": datetime.now(publisher.JST).isoformat(),
              "status": "not_checked", "mutation_count": 0,
              "mode": "read_only_no_mutations_no_retries"}
    try:
        history = publisher.load()
        client = BufferReservations()
        snapshot = client.preflight()
        result.update(diagnose(history, snapshot["posts"]))
        result["filtered_statuses_checked"] = ["scheduled", "sending", "needs_approval", "error", "sent"]
        try:
            all_posts = scan_all_channel_posts(client)
            all_result = diagnose(history, all_posts)
            result["unfiltered_scan"] = {"channel_posts_seen": len(all_posts),
                                         "results": all_result["results"]}
        except Exception as exc:
            result["unfiltered_scan"] = {"status": "unavailable",
                                         "error_type": type(exc).__name__}
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
