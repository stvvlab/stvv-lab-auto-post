"""Read-only Buffer delivery monitor. Never creates, resends, or edits posts.

A Buffer 'sent' status is transport evidence, NOT verified X display.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit

from advance_reservations import verify_echo, stamp
from buffer_reservations import BufferReservations
from stvv_post import CHANNEL, JST

ROOT = Path(__file__).resolve().parents[1]


def classify(status, due_at, now, grace_minutes=15):
    due = stamp(due_at)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Monitoring requires timezone-aware time")
    if status == "sent":
        return "buffer_reports_sent_x_unverified"
    if status == "draft":
        return "moved_to_drafts_not_published"
    if status == "error":
        return "buffer_error_not_published"
    if status not in {"scheduled", "sending"}:
        return "unknown_buffer_status_do_not_retry"
    if now > due + timedelta(minutes=grace_minutes):
        return "overdue_not_sent_do_not_retry"
    return "waiting_for_due" if now < due else "sending_within_grace"


def collect(history, client, now):
    reservations = history.get("reserved_posts")
    if not isinstance(reservations, dict):
        raise ValueError("Invalid reservation ledger")
    rows = []
    for key, record in sorted(reservations.items()):
        if not isinstance(record, dict):
            raise ValueError("Invalid reservation record")
        for field in ("buffer_id", "text", "due_at", "image_url", "dimensions"):
            if not record.get(field):
                raise ValueError("Incomplete reservation; cannot safely confirm")
        remote = client.get_post(record["buffer_id"])
        if (str(remote.get("id")) != str(record["buffer_id"])
                or remote.get("channelId") != CHANNEL
                or remote.get("text") != record["text"]):
            raise RuntimeError("Remote reservation identity mismatch; do not resend")
        status = remote.get("status")
        if status != "draft":
            verify_echo(remote, record)
        state = classify(status, record["due_at"], now)
        rows.append({
            "key": key, "buffer_id": record["buffer_id"],
            "scheduled_jst": stamp(record["due_at"]).astimezone(JST).isoformat(),
            "ledger_status": record.get("buffer_status"),
            "remote_status": status, "delivery_state": state,
            "x_display_verified": False,
            "x_permalink_candidate": (x_permalink_candidate(remote)
                                      if status == "sent" else None),
        })
    return rows



def x_permalink_candidate(remote):
    """Only expose a plausible own-account X URL; this never verifies X display."""
    value = remote.get("externalLink")
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in
                {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
                or parsed.username or parsed.password or parsed.port is not None
                or parsed.query or parsed.fragment):
            return None
    except ValueError:
        return None
    match = re.fullmatch(r"/stvvlabo/status/([0-9]{8,25})/?", parsed.path, re.I)
    return "https://x.com/stvvlabo/status/" + match.group(1) if match else None

def needs_attention(row):
    """A scheduled post moved to drafts is a delivery failure, not success.

    Previously cancelled terminal reservations remain historical and must not
    generate a new alert or be requeued.
    """
    if row["delivery_state"] in {
            "overdue_not_sent_do_not_retry", "buffer_error_not_published",
            "unknown_buffer_status_do_not_retry"}:
        return True
    return (row["delivery_state"] == "moved_to_drafts_not_published"
            and row["ledger_status"] in {"scheduled", "sending"})


def main():
    now = datetime.now(JST)
    report = {"checked_at_jst": now.isoformat(), "mode": "read_only_no_send",
              "x_display_verified": False, "reservations": []}
    try:
        history = json.loads((ROOT / "posted.json").read_text(encoding="utf-8"))
        report["reservations"] = collect(history, BufferReservations(), now)
        report["status"] = ("action_required" if any(
            needs_attention(row) for row in report["reservations"])
            else "checked")
    except Exception as error:
        report["status"] = "check_failed_do_not_retry"
        report["error_type"] = type(error).__name__
        raise
    finally:
        path = ROOT / "reports/buffer-publication-monitor.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print("BUFFER_PUBLICATION_MONITOR " + json.dumps(report, ensure_ascii=False))
    if report["status"] == "action_required":
        raise SystemExit("Buffer reservation overdue or failed; NO automatic retry")


if __name__ == "__main__":
    main()
