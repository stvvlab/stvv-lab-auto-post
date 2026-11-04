"""One-shot verified Kokubo queue submission. No retry on unknown outcome."""
import hashlib,json,os,requests
from pathlib import Path
from buffer_reservations import BufferReservations,POST_FIELDS
REQ=Path("editorial/reservation_requests/2026-11-05_kokubo_national_team_pending.json")
def main():
 r=json.loads(REQ.read_text())
 if r.get("buffer_reservation_status")!="ready_to_submit_once" or r.get("id")!="stvv-2026-11-05-kokubo-national-team":
  raise RuntimeError("Not authorized")
 url=r["image_public_url"]; sha=r["image_sha256"]
 response=requests.get(url,timeout=25);response.raise_for_status()
 data=response.content
 if hashlib.sha256(data).hexdigest()!=sha or not data.startswith(b"\x89PNG\r\n\x1a\n"):
  raise RuntimeError("Image is not exact approved PNG")
 client=BufferReservations();snap=client.preflight()
 if any(p.get("text")==r["text"] for p in snap["posts"]):
  raise RuntimeError("Matching queue/sent post already exists")
 for org in client.query("query { account { organizations { id } } }")["account"]["organizations"]:
  if any(p.get("text")==r["text"] for p in client.posts(org["id"],["draft"],channel=snap["channel_id"])):
   raise RuntimeError("Matching draft exists; no duplicate")
 mutation=("mutation QueueApproved($input: CreatePostInput!) { createPost(input:$input) { ... on PostActionSuccess { post { "+POST_FIELDS+" } } ... on MutationError { message } } }")
 payload={"text":r["text"],"channelId":snap["channel_id"],"assets":[{"image":{"url":url}}],"schedulingType":"automatic","mode":"addToQueue","needsApproval":False,"saveToDraft":False}
 receipt=Path("kokubo_queue_receipt.json")
 receipt.write_text(json.dumps({"state":"pending_unknown_do_not_retry","request_id":r["id"]}))
 result=client.query(mutation,{"input":payload}).get("createPost") or {}
 post=result.get("post")
 if not post or not post.get("id"): raise RuntimeError("Buffer outcome unknown or rejected; do not retry")
 remote=client.get_post(post["id"])
 if remote.get("text")!=r["text"] or remote.get("status")!="scheduled" or not remote.get("dueAt"):
  raise RuntimeError("Buffer queue response could not be verified")
 receipt.write_text(json.dumps({"state":"scheduled_verified","buffer_id":post["id"],"due_at":remote["dueAt"],"status":remote["status"]},ensure_ascii=False))
 print(receipt.read_text())
if __name__=="__main__":main()
