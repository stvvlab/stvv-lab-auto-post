"""Reusable Buffer queue command. Explicit manual dispatch only."""
import json,os,hashlib,requests
from pathlib import Path
from buffer_reservations import BufferReservations,POST_FIELDS

def main():
    path=Path(os.environ["REQUEST_PATH"])
    if not str(path).startswith("editorial/reservation_requests/") or path.suffix!=".json":
        raise ValueError("Request must be an editorial JSON file")
    req=json.loads(path.read_text(encoding="utf-8"))
    if req.get("approval_status")!="approved":
        raise ValueError("Explicit approval_status=approved is required")
    caption=req["text"]
    url=req["image_public_url"]
    sha=req["image_sha256"]
    if not url.startswith("https://") or len(sha)!=64:
        raise ValueError("Missing verified image URL and SHA256")
    img=requests.get(url,timeout=30)
    img.raise_for_status()
    if not img.content.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        raise ValueError("Image URL did not return PNG bytes; abort before Buffer mutation")
    if hashlib.sha256(img.content).hexdigest()!=sha:
        raise ValueError("Approved image bytes do not match SHA256")
    client=BufferReservations()
    snap=client.preflight()
    if snap["remaining_capacity"]<1:
        raise ValueError("Buffer queue capacity exhausted")
    if any(p.get("text")==caption for p in snap["posts"]):
        raise ValueError("Duplicate post found; no action")
    query=("mutation Queue($input: CreatePostInput!) { createPost(input:$input) { ... on PostActionSuccess { post { "+POST_FIELDS+" } } ... on MutationError { message } } }")
    payload={"text":caption,"channelId":snap["channel_id"],"assets":[{"image":{"url":url}}],"schedulingType":"automatic","mode":"addToQueue","needsApproval":False,"saveToDraft":False}
    # No automatic retries: ambiguous provider outcomes require manual inspection.
    result=client.query(query,{"input":payload}).get("createPost") or {}
    post=result.get("post")
    if not post or not post.get("id"):
        raise RuntimeError("Buffer outcome uncertain; inspect Buffer before any retry")
    remote=client.get_post(post["id"])
    if remote.get("text")!=caption or remote.get("status")!="scheduled" or not remote.get("dueAt"):
        raise RuntimeError("Remote verification incomplete; do not retry")
    print("VERIFIED_BUFFER_QUEUE "+json.dumps({"id":post["id"],"dueAt":remote["dueAt"],"status":remote["status"]},ensure_ascii=False))
if __name__=="__main__":main()
