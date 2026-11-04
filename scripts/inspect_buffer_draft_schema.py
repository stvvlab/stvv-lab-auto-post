"""Read-only Buffer GraphQL schema diagnostic; never submit a mutation."""
import json
from buffer_reservations import BufferReservations
def main():
    c=BufferReservations()
    q='query { __type(name: "CreatePostInput") { name inputFields { name type { kind name ofType {kind name ofType {kind name} } } } } }'
    try:
        schema=c.query(q)
        fields=schema.get("__type",{}).get("inputFields",[]) if schema.get("__type") else []
        print("CREATE_POST_SCHEMA "+json.dumps([{"name":f["name"],"type":f["type"]} for f in fields],ensure_ascii=False))
    except Exception as err:
        print("SCHEMA_INSPECTION_UNAVAILABLE "+type(err).__name__+": "+str(err))
if __name__=="__main__":
    main()
