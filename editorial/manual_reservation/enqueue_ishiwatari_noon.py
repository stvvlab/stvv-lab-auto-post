"""One-shot approved player spotlight at a specified UTC time."""
import json,os,hashlib,requests
from pathlib import Path
from buffer_reservations import BufferReservations
REQ=Path("editorial/reservation_requests/2026-11-05_ishiwatari_noon.json")
def main():
    r=json.loads(REQ.read_text(encoding="utf-8"))
    if r.get("approval_status")!="approved" or r.get("due_at_utc")!="2026-11-05T03:30:00.000Z":
        raise RuntimeError("Approval or fixed noon schedule mismatch")
    response=requests.get(r["image_public_url"],timeout=30)
    response.raise_for_status()
    data=response.content
    if not data.startswith(bytes.fromhex("89504e470d0a1a0a")) or hashlib.sha256(data).hexdigest()!=r["image_sha256"]:
        raise RuntimeError("Approved PNG mismatch")
    client=BufferReservations()
    snap=client.preflight()
    if any(p["text"]==r["text"] for p in snap["posts"]):
        raise RuntimeError("Matching Buffer post exists; no duplicate")
    for org in client.query("query { account { organizations { id } } }")["account"]["organizations"]:
        if any(p["text"]==r["text"] for p in client.posts(org["id"],["draft"],channel=snap["channel_id"])):
            raise RuntimeError("Matching draft exists")
    post=client.schedule(r["text"],r["image_public_url"],r["due_at_utc"])
    remote=client.get_post(post["id"])
    if remote.get("text")!=r["text"] or remote.get("status")!="scheduled" or remote.get("dueAt")!=r["due_at_utc"]:
        raise RuntimeError("Reservation result uncertain; do not retry")
    print("VERIFIED_NOON_BUFFER_QUEUE "+json.dumps({"id":remote["id"],"dueAt":remote["dueAt"],"status":remote["status"]}))
if __name__=="__main__":main()
