"""One-shot enqueue of approved De Meyer artwork; existing Buffer Draft remains.

A durable remote ledger is created before the only provider mutation.
Never re-run an uncertain response, never call shareNow, never use the draft ID
for mutations. A CI artifact preserves the receipt without Git pushes.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from buffer_reservations import BufferReservations, ReservationRejected, POST_FIELDS
from editorial.manual_reservation.draft_preflight import validate_request
from scripts.verify_de_meyer_image import verify_asset
import stvv_post as publisher

BRANCH = "fix/de-meyer-exact-image-transfer-20261104"
LEDGER = Path("editorial/manual_reservation/de_meyer_queue_ledger.json")
DRAFT_LEDGER = Path("editorial/manual_reservation/de_meyer_retry_v2_ledger.json")
EXPECTED_SHA = "40c97a3f63667cd930c3d803c7448eebf7b347f5043572927dfcaa65b51843a7"

def main():
    if (os.getenv("GITHUB_REF_NAME") != BRANCH or
        os.getenv("GITHUB_RUN_ATTEMPT") != "1" or
        os.getenv("STVV_SINGLE_QUEUE_APPROVED") != "APPROVE_ONE_DE_MEYER_QUEUE"):
        raise RuntimeError("One-shot queue authorization/ref missing; never auto retry")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("state") != "precommitted_one_shot_queue_intent":
        raise RuntimeError("Queue intent used or invalid; no provider mutation")
    draft = json.loads(DRAFT_LEDGER.read_text(encoding="utf-8"))
    request = validate_request()
    verified = verify_asset()
    if (draft.get("state") != "draft_created_verified" or
        draft.get("image_sha256") != EXPECTED_SHA or
        verified["sha256"] != EXPECTED_SHA or
        ledger.get("request_id") != request["id"] or
        ledger.get("caption_sha256") != hashlib.sha256(request["text"].encode()).hexdigest()):
        raise RuntimeError("Approved caption/image or Draft evidence mismatch")
    client = BufferReservations()
    snapshot = client.preflight()
    if snapshot["remaining_capacity"] < 1:
        raise RuntimeError("No capacity")
    remote_draft = client.get_post(draft["buffer_post_id"])
    if remote_draft.get("status") != "draft" or remote_draft.get("text") != request["text"]:
        raise RuntimeError("Existing Draft was changed; refusing queue mutation")
    assets = remote_draft.get("assets") or []
    if len(assets) != 1 or assets[0].get("source") != ledger["image_url"]:
        raise RuntimeError("Existing Draft image mismatch")
    for post in snapshot["posts"]:
        if post.get("text") == request["text"]:
            raise RuntimeError("Matching scheduled/sent post exists; no second enqueue")
    # Provider mutation: only addToQueue; never shareNow.
    mutation = ("mutation QueueApproved($input: CreatePostInput!) {"
                " createPost(input: $input) {"
                " ... on PostActionSuccess { post { " + POST_FIELDS + " } }"
                " ... on MutationError { message }"
                " } }")
    payload = {"text": request["text"], "channelId": snapshot["channel_id"],
               "assets": [{"image": {"url": ledger["image_url"]}}],
               "schedulingType": "automatic", "mode": "addToQueue",
               "needsApproval": False, "saveToDraft": False}
    ledger["state"] = "mutation_outcome_unknown_do_not_retry"
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    try:
        result = client.query(mutation, {"input": payload}).get("createPost") or {}
        post = result.get("post")
        if not isinstance(post, dict) or not post.get("id"):
            if result.get("message"):
                raise ReservationRejected("Buffer rejected queue mutation")
            raise RuntimeError("Unknown Buffer queue mutation outcome; do not retry")
        ledger["buffer_post_id"] = post["id"]
        remote = client.get_post(post["id"])
        a = remote.get("assets") or []
        if (remote.get("channelId") != snapshot["channel_id"] or
            remote.get("text") != request["text"] or
            remote.get("status") not in ("scheduled", "sending") or
            not remote.get("dueAt") or len(a) != 1 or
            a[0].get("source") != ledger["image_url"] or
            a[0].get("type") != "image"):
            raise RuntimeError("Queue read-back unverified; no retry")
        due = datetime.fromisoformat(remote["dueAt"].replace("Z","+00:00"))
        if due.utcoffset() is None or due <= datetime.now(timezone.utc):
            raise RuntimeError("Queue dueAt not safely in the future; investigate")
        ledger.update({"state":"scheduled_verified","due_at_utc":remote["dueAt"],
                       "remote_status":remote["status"],
                       "draft_preserved":True,"buffer_post_id":post["id"]})
        print("QUEUE_RESULT "+json.dumps(ledger,ensure_ascii=False),flush=True)
    finally:
        LEDGER.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__ == "__main__":
    main()
