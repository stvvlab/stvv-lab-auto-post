"""Deterministic, read-only STVV posting recovery diagnosis.
Never publishes, alters history, or infers an X post from an Action's success.
"""
import argparse
import json
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo


def outstanding_x_verifications(history):
    """Track unresolved Buffer-sent reservations across later scheduled runs.

    Older shareNow records have no durable X-verification state, so only the
    advance-reservation records are in scope. A later verified reservation
    supersedes an older publication-log snapshot.
    """
    records = {}
    for record in history.get("publication_log", []):
        if (isinstance(record, dict)
                and record.get("delivery_state") == "buffer_reports_sent_x_unverified"
                and record.get("key")):
            records[record["key"]] = record
    for key, record in history.get("reserved_posts", {}).items():
        if isinstance(record, dict) and record.get("buffer_status") == "sent":
            records[key] = record
    return sorted(key for key, record in records.items()
                  if record.get("x_display_verified") is not True)



JST = ZoneInfo("Asia/Tokyo")
# Mirrors the three active public slots in .github/workflows/main.yml.
# This is an observation tool, not a scheduler or an approval mechanism.
COVERAGE_SLOTS = (("player", 8), ("news", 18), ("recap", 23))


def forward_coverage(manifest, history, now=None):
    """Inspect the next 36h from local files only. Never contact or mutate Buffer."""
    now = now or datetime.now(JST)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware now required")
    now = now.astimezone(JST)
    if (not isinstance(history, dict)
            or not isinstance(history.get("used_posts"), list)
            or not isinstance(history.get("pending_posts"), dict)
            or not isinstance(history.get("reserved_posts"), dict)
            or not isinstance(history.get("publication_log"), list)
            or any(not isinstance(key, str) for key in history["used_posts"])):
        return {"status": "ledger_unavailable", "mode": "read_only_local_ledger",
                "checked_at_jst": now.isoformat(), "slots": [],
                "remote_buffer_checked": False, "x_display_checked": False}
    cards = manifest.get("cards", []) if isinstance(manifest, dict) else []
    if not isinstance(cards, list):
        cards = []
    occupied = set(history["used_posts"])
    occupied.update(p.get("key") for p in history["publication_log"]
                    if isinstance(p, dict) and isinstance(p.get("key"), str))
    slots = []
    for offset in range(3):
        day = (now + timedelta(days=offset)).date()
        for slot, hour in COVERAGE_SLOTS:
            due = datetime.combine(day, time(hour), tzinfo=JST)
            if not now <= due <= now + timedelta(hours=36):
                continue
            key = f"daily_{day.isoformat()}_{slot}"
            record = history["reserved_posts"].get(key)
            candidate_count = sum(
                isinstance(card, dict)
                and card.get("status") == "ready"
                and card.get("reviewed") is True
                and isinstance(card.get("slots"), list)
                and slot in card["slots"]
                and (not card.get("publish_due_jst")
                     or card.get("publish_due_jst") == due.isoformat())
                and (card.get("media_type") != "text_only"
                     or card.get("text_only_approved") is True)
                for card in cards)
            if key in history["pending_posts"]:
                state = "pending_outcome_unknown_do_not_retry"
            elif isinstance(record, dict):
                remote_state = record.get("buffer_status", "unknown")
                if remote_state == "scheduled":
                    state = "scheduled_in_ledger_remote_unverified"
                elif remote_state == "sent":
                    state = ("x_verified_in_ledger" if record.get("x_display_verified") is True
                             else "buffer_sent_in_ledger_x_unverified")
                else:
                    state = "reservation_not_active_or_unknown_do_not_retry"
            elif key in occupied:
                state = "already_processed_in_ledger_do_not_retry"
            elif candidate_count:
                state = "reviewed_candidate_requires_live_checks"
            else:
                state = "no_reviewed_candidate"
            slots.append({"key": key, "due_jst": due.isoformat(),
                          "state": state, "potential_reviewed_cards": candidate_count,
                          "buffer_status": record.get("buffer_status") if isinstance(record, dict)
                                           else None})
    counts = {state: sum(s["state"] == state for s in slots)
              for state in sorted(set(s["state"] for s in slots))}
    return {"status": "local_coverage_inspected", "mode": "read_only_local_ledger",
            "checked_at_jst": now.isoformat(), "horizon_hours": 36,
            "remote_buffer_checked": False, "x_display_checked": False,
            "candidate_counts_are_not_publication_approval": True,
            "summary": counts, "slots": sorted(slots, key=lambda s: s["due_jst"])}


def diagnose(manifest, preparation, delivery, history=None):
    cards = manifest.get("cards", [])
    ready_cards = [c for c in cards if isinstance(c, dict)
                   and c.get("status") == "ready" and c.get("reviewed") is True]
    ready = len(ready_cards)
    ready_images = sum(c.get("media_type") != "text_only" for c in ready_cards)
    ready_text_only = sum(c.get("media_type") == "text_only"
                          and c.get("text_only_approved") is True
                          for c in ready_cards)
    reservations = (history or {}).get("reserved_posts", {})
    if not isinstance(reservations, dict):
        reservations = {}

    def already_reserved(card):
        # Local diagnosis only: not a publication gate. The publisher adds hashtags.
        source, caption = card.get("source_url"), card.get("text")
        if not isinstance(source, str) or not isinstance(caption, str) or not caption:
            return False
        return any(
            isinstance(record, dict)
            and record.get("source") == source
            and isinstance(record.get("text"), str)
            and (record["text"] == caption or record["text"].startswith(caption + "\n"))
            and (not card.get("editorial_purpose")
                 or record.get("editorial_purpose") == card["editorial_purpose"])
            for record in reservations.values()
        )

    ready_reserved = sum(already_reserved(c) for c in ready_cards)
    problems = []
    if ready == 0:
        problems.append("approved_ready_assets_zero")
    if preparation.get("status") == "no_unposted_candidate_in_scanned_lists":
        problems.append("no_new_verified_source")
    # An empty reviewed queue is a correct no-post outcome, not a failed
    # publication. An actual rejected image is a separate safety blocker.
    if delivery.get("status") == "skipped_image_verification":
        problems.append("image_verification_blocked")
    # A failed delivery step or an unresolved send must not disappear merely
    # because no publication was appended to the history.
    delivery_status = delivery.get("status")
    delivery_state = delivery.get("delivery_state")
    if delivery_status == "execution_failed":
        problems.append("scheduled_delivery_execution_failed")
    if (delivery_status == "blocked_pending_outcome_unknown"
            or delivery_state in {"send_outcome_unknown_do_not_retry",
                                  "previous_pending_requires_review",
                                  "ledger_unreadable_do_not_retry"}
            or delivery.get("pending_reservation_keys")):
        problems.append("send_outcome_unknown_do_not_retry")
    if (delivery_status == "blocked_buffer_rejected"
            or delivery_state == "buffer_rejected_not_published"):
        problems.append("buffer_explicitly_rejected")
    if (delivery_status == "blocked_reservation_error"
            or delivery_state == "buffer_reservation_error_do_not_retry"
            or any(isinstance(r, dict) and r.get("buffer_status") == "error"
                   for r in delivery.get("reservation_states", []))):
        problems.append("buffer_reservation_error")
    if delivery.get("start_delay_seconds", 0) > 1800:
        problems.append("github_start_delayed_over_30_minutes")
    outstanding = outstanding_x_verifications(history or {})
    if (outstanding or (not delivery.get("x_display_verified", False)
                        and delivery.get("new_publications"))):
        # This is missing X evidence, not proof of failed publication.
        problems.append("x_publication_not_verified")
    if "send_outcome_unknown_do_not_retry" in problems:
        next_fix = ("Reconcile the exact pending ID and remote Buffer state without "
                    "resending. Preserve the ledger until the outcome is proven.")
    elif "scheduled_delivery_execution_failed" in problems:
        next_fix = ("Inspect the failed scheduled job step and durable ledger; "
                    "fix the specific cause without manual dispatch or resend.")
    elif "buffer_explicitly_rejected" in problems or "buffer_reservation_error" in problems:
        next_fix = ("Inspect the recorded Buffer rejection or reservation error; "
                    "do not automatically retry or create another post.")
    elif "image_verification_blocked" in problems:
        next_fix = ("Verify approved image bytes, public asset identity and caption; "
                    "do not bypass the image gate.")
    elif "x_publication_not_verified" in problems:
        next_fix = ("Verify the exact X text and image for each Buffer-sent "
                    "reservation, then record evidence in the durable ledger. "
                    "Never resend an unverified post.")
    elif ready == 0:
        next_fix = ("Prepare and explicitly approve a genuinely new fact-checked "
                    "image/card, then verify Buffer reservation and public X display. "
                    "Do not reuse a published card or relax duplicates.")
    else:
        next_fix = ("Investigate actual reservation and publication state "
                    "without replaying unknown sends.")
    return {
        "status": "needs_recovery" if problems else "no_detected_blocker",
        "problems": problems,
        "ready_reviewed_cards": ready,
        "ready_reviewed_images": ready_images,
        "ready_reviewed_text_only": ready_text_only,
        "ready_already_reserved": ready_reserved,
        "ready_not_reserved": ready - ready_reserved,
        "ready_counts_are_local_diagnostics_only": True,
        "last_delivery_status": delivery.get("status", "unknown"),
        "last_delivery_state": delivery.get("delivery_state", "unknown"),
        "delivery_run_id": delivery.get("run_id"),
        "preparation_checked_at": preparation.get("checked_at"),
        "new_buffer_reservations": len(delivery.get("new_reservations", [])),
        "outstanding_x_verification_count": len(outstanding),
        "outstanding_x_verification_keys": outstanding,
        "new_x_publications_verified": sum(
            1 for p in delivery.get("new_publications", [])
            if isinstance(p, dict) and p.get("x_display_verified") is True),
        "next_fix": next_fix,
        "automatic_code_generation_enabled": False,
        "publishing_attempted": False,
        "forward_coverage": forward_coverage(manifest, history),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/recovery-triage-latest.json")
    args = parser.parse_args()
    def load(path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object: {path}")
        return data
    result = diagnose(load("editorial/imagegen_cards.json"),
                      load("reports/preparation-latest.json"),
                      load("reports/delivery-latest.json"),
                      load("posted.json"))
    out = Path(args.output)
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
