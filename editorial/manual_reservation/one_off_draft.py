"""One-shot, opt-in Buffer Draft sender for the approved De Meyer post.

Not called by any recurring workflow. Never automatically retries an uncertain
createPost outcome. Requires explicit verified image URL and operator opt-in.
"""
import hashlib
import json
import os
from pathlib import Path

from buffer_reservations import BufferReservations
from editorial.manual_reservation.draft_preflight import validate_request

INTENT = Path("editorial/manual_reservation/de_meyer_draft_send_intent.json")


def write_once(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    request = validate_request()
    if INTENT.exists():
        raise RuntimeError("A previous intent exists; inspect Buffer before any retry")
    if os.getenv("STVV_ONE_OFF_DRAFT_SEND") != "I_APPROVE_ONE_DRAFT":
        raise RuntimeError("One-off draft send not explicitly enabled")
    image_url = os.getenv("STVV_APPROVED_IMAGE_URL", "")
    image_sha = os.getenv("STVV_APPROVED_IMAGE_SHA256", "")
    if not image_url.startswith("https://") or len(image_sha) != 64 or any(
            ch not in "0123456789abcdef" for ch in image_sha):
        raise RuntimeError("Approved HTTPS image URL and SHA256 required")
    # Verify exact remote image bytes before any createPost attempt.
    import requests
    response = requests.get(image_url, timeout=20)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != image_sha:
        raise RuntimeError("Approved image bytes do not match")
    client = BufferReservations()
    snapshot = client.preflight()
    if snapshot["channel_id"] is None:
        raise RuntimeError("Target channel not verified")
    # Existing preflight excludes drafts; do not claim exhaustive duplicate safety.
    if any(p.get("text") == request["text"] for p in snapshot["posts"]):
        raise RuntimeError("Duplicate caption found in queue or sent posts")
    # Explicitly enumerate draft status too, before sending.
    orgs = client.query("query { account { organizations { id } } }")["account"]["organizations"]
    for org in orgs:
        drafts = client.posts(org["id"], ["draft"], channel=snapshot["channel_id"])
        if any(p.get("text") == request["text"] for p in drafts):
            raise RuntimeError("Duplicate caption already exists in Buffer Drafts")
    record = {"request_id": request["id"], "caption_sha256": hashlib.sha256(
        request["text"].encode()).hexdigest(), "image_url": image_url,
        "image_sha256": image_sha, "state": "pending_unknown_do_not_retry"}
    write_once(INTENT, record)
    # The pending file MUST be persisted to a durable shared ledger before
    # live sending. A local runner alone cannot guarantee this on ephemeral CI.
    raise RuntimeError("SAFE STOP: persist pending intent to durable shared ledger before sending")


if __name__ == "__main__":
    main()
