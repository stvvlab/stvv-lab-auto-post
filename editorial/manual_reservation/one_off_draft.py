"""Single-use, image-bound Buffer Draft delivery on dedicated review branch.

Does not schedule/publish. A GitHub push caused by the exact approved image
runs once; pending Git receipt prevents silent retries after uncertain results.
"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import requests
from buffer_reservations import BufferReservations
from editorial.manual_reservation.draft_preflight import validate_request
from scripts.verify_de_meyer_image import verify_asset

BRANCH = "fix/de-meyer-exact-image-transfer-20261104"
INTENT = Path("editorial/manual_reservation/de_meyer_draft_send_intent.json")
REPO = "stvvlab/stvv-lab-auto-post"


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def write_once(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def persist_intent():
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", str(INTENT))
    git("commit", "-m", "Record single-use pending Buffer Draft request")
    git("push", "origin", "HEAD:" + BRANCH)


def main():
    request = validate_request()
    if os.getenv("STVV_ONE_OFF_DRAFT_SEND") != "I_APPROVE_ONE_DRAFT":
        raise RuntimeError("No explicit single-draft authorization")
    if os.getenv("GITHUB_REF_NAME") != BRANCH:
        raise RuntimeError("Wrong branch; refusing Buffer mutation")
    if INTENT.exists():
        raise RuntimeError("Prior attempt exists; inspect Buffer; never retry automatically")

    verified = verify_asset()
    revision = git("rev-parse", "HEAD")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise RuntimeError("Immutable commit id not verified")
    image_url = ("https://raw.githubusercontent.com/" + REPO + "/" +
                 revision + "/" + verified["asset_path"])
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != verified["sha256"]:
        raise RuntimeError("GitHub remote image does not match approved original")
    if os.getenv("STVV_ONE_OFF_IMAGE_SHA256") and os.getenv("STVV_ONE_OFF_IMAGE_SHA256") != verified["sha256"]:
        raise RuntimeError("Image workflow SHA and approved original differ")

    client = BufferReservations()
    snapshot = client.preflight()
    if not snapshot.get("channel_id"):
        raise RuntimeError("Buffer channel not verified")
    if any(p.get("text") == request["text"] for p in snapshot["posts"]):
        raise RuntimeError("Duplicate caption already in Buffer scheduled/sent")
    organizations = client.query("query { account { organizations { id } } }")["account"]["organizations"]
    for organization in organizations:
        drafts = client.posts(organization["id"], ["draft"], channel=snapshot["channel_id"])
        if any(p.get("text") == request["text"] for p in drafts):
            raise RuntimeError("Duplicate caption already exists in Drafts")

    record = {
        "request_id": request["id"],
        "caption_sha256": hashlib.sha256(request["text"].encode("utf-8")).hexdigest(),
        "image_url": image_url,
        "image_sha256": verified["sha256"],
        "state": "pending_unknown_do_not_retry",
    }
    write_once(INTENT, record)
    persist_intent()  # durable remote ledger before the only Buffer mutation
    post = client.create_draft(request["text"], image_url)
    record["state"] = "draft_created"
    record["buffer_post_id"] = post["id"]
    INTENT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("add", "--", str(INTENT))
    git("commit", "-m", "Record Buffer Draft receipt")
    git("push", "origin", "HEAD:" + BRANCH)
    print(json.dumps({"status": "draft_created", "buffer_post_id": post["id"]}))


if __name__ == "__main__":
    main()
