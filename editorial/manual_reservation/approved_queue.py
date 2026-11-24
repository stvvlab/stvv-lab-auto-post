import json
import hashlib
from pathlib import Path
from buffer_reservations import BufferReservations
import requests

def main():
    p = Path("editorial/manual_reservation/approved_queue_request.json")
    r = json.loads(p.read_text())
    if r.get("approved") is not True:
        raise RuntimeError("Approval required")
    if r["text"] != r["approved_text"]:
        raise RuntimeError("Caption mismatch")
    if r.get("image_url"):
        response = requests.get(r["image_url"], timeout=25)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != r["image_sha256"]:
            raise RuntimeError("Image mismatch")
    elif r.get("text_only") is not True:
        raise RuntimeError("Text-only approval required")
    receipt = Path("approved_queue_receipt.json")
    receipt.write_text(json.dumps({"request_id":r["id"],"state":"unknown_do_not_retry"}))
    post = BufferReservations().enqueue_approved(r["text"], r.get("image_url"))
    receipt.write_text(json.dumps({"request_id":r["id"],"state":"scheduled_verified","post":post},ensure_ascii=False))
    print("QUEUE_RESULT",receipt.read_text())

if __name__ == "__main__":
    main()
