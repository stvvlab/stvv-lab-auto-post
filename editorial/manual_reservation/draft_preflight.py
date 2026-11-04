"""Isolated, read-only preflight for a single approved STVV LAB Buffer draft.

This module deliberately does not send or schedule anything. It validates the
approved request and probes the configured Buffer channel before any mutation
is enabled. Existing daily scheduled publishers are untouched.
"""
import json
from pathlib import Path

from buffer_reservations import BufferReservations
import stvv_post as publisher

REQUEST = Path("editorial/reservation_requests/2026-11-04_de_meyer_departure.json")


def validate_request(path=REQUEST):
    request = json.loads(Path(path).read_text(encoding="utf-8"))
    if request.get("id") != "stvv-2026-11-02-de-meyer-departure":
        raise ValueError("Unexpected one-off request")
    if request.get("auto_publish") is not False:
        raise ValueError("Automatic publishing must remain disabled")
    if request.get("buffer_reservation_status") != "not_submitted":
        raise ValueError("Request has an existing submission state")
    if not request.get("source_url", "").startswith("https://stvv.jp/news/"):
        raise ValueError("Official source URL required")
    if not isinstance(request.get("text"), str) or not request["text"].strip():
        raise ValueError("Approved caption missing")
    if publisher.x_length(request["text"]) > 270:
        raise ValueError("Caption exceeds safe X length")
    return request


def preflight():
    request = validate_request()
    image_path = request.get("image_path")
    result = {
        "request_id": request["id"],
        "mode": "read_only_no_buffer_mutation",
        "caption_valid": True,
        "image_linked": bool(image_path),
        "target_channel": "@stvvlabo",
        "existing_daily_schedule_modified": False,
        "draft_created": False,
    }
    if not image_path:
        result["blocker"] = "approved_image_not_linked"
        return result
    image = Path(image_path)
    if not image.is_file():
        result["blocker"] = "approved_image_file_missing"
        return result
    try:
        snapshot = BufferReservations().preflight()
    except Exception as error:
        result["blocker"] = "buffer_read_only_preflight_failed"
        result["error_type"] = type(error).__name__
        return result
    result["channel_verified"] = snapshot["channel_id"] == publisher.CHANNEL
    captions = [post.get("text") for post in snapshot["posts"]]
    result["duplicate_in_remote_active_or_sent"] = request["text"] in captions
    result["blocker"] = "draft_mutation_not_yet_verified"
    return result


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
