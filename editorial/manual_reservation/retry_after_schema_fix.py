"""One manual-approved retry after invalid GraphQL Draft mode, never publishing.

The first createPost was rejected at GraphQL validation; a read-only audit then
found zero matching posts. This module rechecks immediately and persists its
single-use attempt in Git before submitting the corrected mutation.
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
RETRY = Path("editorial/manual_reservation/de_meyer_schema_fix_retry.json")
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
    if RETRY.exists():
        raise RuntimeError("Retry ledger already exists; never send twice")
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
    record = {
        "request_id": request["id"],
        "prior_attempt": "Buffer GraphQL rejected invalid ShareMode=draft (schema-confirmed)",
        "reason": "Use saveToDraft=true; needsApproval=false; valid ShareMode=addToQueue",
        "state": "retry_pending_unknown_do_not_retry",
        "image_url": previous["image_url"],
        "image_sha256": EXPECTED
    }
    # Remote durable intent must exist before the single Buffer mutation.
    fd = os.open(str(RETRY), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    commit_ledger()
    post = client.create_draft(request["text"], previous["image_url"])
    record["buffer_post_id"] = post["id"]
    remote = client.get_post(post["id"])
    if (remote.get("id") != post["id"] or remote.get("status") != "draft"
        or remote.get("channelId") != stvv_post.CHANNEL or remote.get("text") != request["text"]
        or not remote.get("assets")):
        raise RuntimeError("Draft read-back incomplete; never retry blindly")
    record["state"] = "draft_created_verified"
    RETRY.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("add", "--", str(RETRY))
    git("commit", "-m", "Confirm single corrected Buffer Draft and image")
    git("push", "origin", "HEAD:" + BRANCH)
    print("DRAFT_RETRY_RESULT " + json.dumps({"state": "draft_created_verified", "id": post["id"]}))

if __name__ == "__main__":
    main()
