"""Read-only Buffer API introspection of existing Draft to queue operations."""
import json
from buffer_reservations import BufferReservations
from editorial.manual_reservation.draft_preflight import validate_request
def main():
    c=BufferReservations()
    t=c.query('query { __schema { mutationType { name fields { name args { name type {kind name ofType {kind name ofType {kind name}}} } } } } }')
    fs=t["__schema"]["mutationType"]["fields"]
    names=[f for f in fs if any(v in f["name"].lower() for v in ("post","draft","queue","schedule"))]
    print("MUTATIONS "+json.dumps(names,ensure_ascii=False))
    for type_name in ("UpdatePostInput","EditPostInput","CreatePostInput","ShareMode"):
        o=c.query('query { __type(name: '+json.dumps(type_name)+') {kind name inputFields {name type{kind name ofType{kind name}}} enumValues{name} } }').get("__type")
        print("TYPE "+type_name+" "+json.dumps(o,ensure_ascii=False))
    request=validate_request()
    from pathlib import Path
    ledger=json.loads(Path("editorial/manual_reservation/de_meyer_retry_v2_ledger.json").read_text())
    post=c.get_post(ledger["buffer_post_id"])
    print("EXISTING_DRAFT "+json.dumps({"id":post.get("id"),"status":post.get("status"),"text_matches":post.get("text")==request["text"],"assets":post.get("assets"),"dueAt":post.get("dueAt"),"channelId":post.get("channelId")},ensure_ascii=False))
    snap=c.preflight()
    print("CAPACITY "+json.dumps({k:v for k,v in snap.items() if k!="posts"},ensure_ascii=False))
if __name__=="__main__":main()
