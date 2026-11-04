"""Read-only evidence check after uncertain Buffer Draft mutation.

Never sends/schedules/publishes. Output includes IDs only for matching caption.
"""
import json
from buffer_reservations import BufferReservations
from editorial.manual_reservation.draft_preflight import validate_request
import stvv_post

def main():
    request = validate_request()
    client = BufferReservations()
    account = client.query("query { account { organizations { id } } }").get("account") or {}
    organizations = account.get("organizations", [])
    if not isinstance(organizations, list) or not organizations:
        raise RuntimeError("Buffer organizations unavailable")
    matches = []
    for org in organizations:
        if not org.get("id"):
            raise RuntimeError("Invalid organization")
        for status in ("draft", "scheduled", "sending", "sent", "error", "needs_approval"):
            for post in client.posts(org["id"], [status], channel=stvv_post.CHANNEL):
                if post.get("text") == request["text"]:
                    assets = post.get("assets") or []
                    matches.append({
                        "id": post["id"],
                        "status": post["status"],
                        "channel_match": post["channelId"] == stvv_post.CHANNEL,
                        "assets": [{"type": a.get("type"), "source": a.get("source")}
                                   for a in assets if isinstance(a, dict)],
                    })
    result = {"request_id": request["id"], "matching_posts": matches,
              "matching_count": len(matches), "read_only": True}
    print("DRAFT_AUDIT " + json.dumps(result, ensure_ascii=False))
if __name__ == "__main__":
    main()
