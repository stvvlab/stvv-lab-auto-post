"""Reconcile a uniquely identified existing Buffer reservation; NEVER create/edit a post."""
import json
from datetime import datetime
from pathlib import Path

import stvv_post as publisher
from advance_reservations import stamp, verify_echo
from buffer_reservations import BufferReservations
from pending_reservation_diagnostic import scan_all_channel_posts

def main():
    report = {"checked_at": datetime.now(publisher.JST).isoformat(),
              "mode": "read_only_buffer_plus_local_ledger_reconciliation",
              "buffer_mutations": 0, "status": "not_started"}
    try:
        history = publisher.load()
        pending = history.get("pending_posts", {})
        key = "daily_2026-10-29_news"
        if key not in pending:
            report["status"] = "pending_already_resolved_no_action"
            return
        record = pending[key]
        if (record.get("delivery_mode") != "customScheduled"
                or record.get("source") != "https://stvv.com/nl/nieuws/artikel/g-voetballers-beleven-droomdag-op-stayen"
                or record.get("sha256") != "1b93e8ce690fc27dc982458444d1cca17becd2124b7ab89565e0631dc339b42d"
                or key in history.get("reserved_posts", {})
                or key in history.get("used_posts", [])
                or any(p.get("key") == key for p in history.get("publication_log", []))):
            raise RuntimeError("Unexpected pending record or existing publication; no changes")
        client = BufferReservations()
        posts = scan_all_channel_posts(client)
        matches = [p for p in posts if p.get("channelId") == publisher.CHANNEL
                   and p.get("text") == record.get("text")
                   and p.get("status") == "scheduled"
                   and stamp(p.get("dueAt", "")) == stamp(record["due_at"])]
        if len(matches) != 1:
            raise RuntimeError("Unique remote reservation not established; no changes")
        pid = matches[0]["id"]
        post = client.get_post(pid)
        verify_echo(post, {**record, "buffer_id": pid})
        if post.get("status") != "scheduled" or datetime.now(publisher.JST) >= stamp(record["due_at"]):
            raise RuntimeError("Remote status or dueAt changed; no changes")
        asset = post["assets"][0]
        if asset.get("id"):
            identity = {"buffer_asset_ids": [asset["id"]]}
        else:
            identity = {"buffer_asset_sources": [record["image_url"]]}
        recovered = {**record, "buffer_id": pid, "buffer_status": "scheduled",
                     "status_checked_at": datetime.now(publisher.JST).isoformat(),
                     "recovered_without_resend": True, **identity}
        history.setdefault("reserved_posts", {})[key] = recovered
        history["used_posts"].append(key)
        del history["pending_posts"][key]
        publisher.save(history)
        report.update(status="existing_reservation_reconciled",
                      buffer_id=pid, due_at=record["due_at"],
                      image_identity="asset_id" if asset.get("id") else "exact_immutable_source")
    except Exception as exc:
        report.update(status="blocked_no_retry", error_type=type(exc).__name__)
        raise
    finally:
        path = Path("reports/pending-reservation-recovery-latest.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("PENDING_RECOVERY " + json.dumps(report, ensure_ascii=False))

if __name__ == "__main__":
    main()
