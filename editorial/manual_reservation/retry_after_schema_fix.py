"""One manual-approved retry after invalid GraphQL Draft mode, never publishing.

The first createPost was rejected at GraphQL validation; a read-only audit then
found zero matching posts. An already-committed remote hold protects this one
corrected attempt. Read-back is required before reporting success.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from buffer_reservations import BufferReservations
from editorial.manual_reservation.draft_preflight import validate_request
from scripts.verify_de_meyer_image import verify_asset
import stvv_post

BRANCH = "fix/de-meyer-exact-image-transfer-20261104"
INTENT = Path("editorial/manual_reservation/de_meyer_draft_send_intent.json")
RETRY = Path("editorial/manual_reservation/de_meyer_retry_v2_ledger.json")
EXPECTED = "40c97a3f63667cd930c3d803c7448eebf7b347f5043572927dfcaa65b51843a7"

def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True, text=True)

def commit_ledger():
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", str(RETRY))
    git("commit", "-m", "Record single-use corrected Buffer Draft attempt")
    git("push", "origin", "HEAD:" + BRANCH)

def audit(client, caption):
    account = client.query("query { account { organizations { id } } }").get("account") or {}
    orgs = account.get("organizations")
    if not isinstance(orgs, list) or not orgs:
        raise RuntimeError("Buffer organizations unavailable")
    matches = []
    for org in orgs:
        for status in ("draft", "scheduled", "sending", "sent", "error", "needs_approval"):
            posts = client.posts(org["id"], [status], channel=stvv_post.CHANNEL)
            matches.extend(x["id"] for x in posts if x.get("text") == caption)
    if matches:
        raise RuntimeError("Matching Buffer post already exists; refusing retry")

def main():
    if os.getenv("GITHUB_REF_NAME") != BRANCH or os.getenv("STVV_ONE_OFF_RETRY_AUTHORIZED") != "RETRY_AFTER_SCHEMA_VALIDATION_ERROR_ONCE":
        raise RuntimeError("Retry authorization or branch missing")
    if os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        raise RuntimeError("Re-run is prohibited to avoid duplicate Drafts")
    if not RETRY.exists():
        raise RuntimeError("Server-side pre-send ledger is missing; refuse")
    ledger = json.loads(RETRY.read_text(encoding="utf-8"))
    if ledger.get("state") != "pre_send_reservation_held_no_auto_retry":
        raise RuntimeError("Pre-send ledger not in approved single-use state")
    previous = json.loads(INTENT.read_text(encoding="utf-8"))
    request = validate_request()
    verified = verify_asset()
    if (previous.get("state") != "pending_unknown_do_not_retry" or
        previous.get("request_id") != request["id"] or
        previous.get("image_sha256") != EXPECTED or
        verified["sha256"] != EXPECTED or
        previous.get("caption_sha256") != hashlib.sha256(request["text"].encode()).hexdigest()):
        raise RuntimeError("Prior attempt does not match approved item")
    client = BufferReservations()
    client.preflight()
    audit(client, request["text"])
    # The pre-send ledger has already been committed using the GitHub connector.
    # No unreliable GitHub Actions git push is needed before calling Buffer.
    record = dict(ledger)
    record["state"] = "attempt_outcome_unknown_no_auto_retry"
    record["image_url"] = previous["image_url"]
    record["image_sha256"] = EXPECTED
    post = client.create_draft(request["text"], previous["image_url"])
    record["buffer_post_id"] = post["id"]
    remote = client.get_post(post["id"])
    if (remote.get("id") != post["id"] or remote.get("status") != "draft"
        or remote.get("channelId") != stvv_post.CHANNEL or remote.get("text") != request["text"]
        or not remote.get("assets")):
        raise RuntimeError("Draft read-back incomplete; never retry blindly")
    record["state"] = "draft_created_verified"
    RETRY.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DRAFT_RETRY_RESULT " + json.dumps({"state": "draft_created_verified", "id": post["id"]}), flush=True)
    # The workflow also uploads the receipt as an artifact if branch push fails.
    git("add", "--", str(RETRY))
    git("commit", "-m", "Confirm single corrected Buffer Draft and image")
    git("push", "origin", "HEAD:" + BRANCH)

if __name__ == "__main__":
    main()
