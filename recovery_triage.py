"""Deterministic, read-only STVV posting recovery diagnosis.
Never publishes, alters history, or infers an X post from an Action's success.
"""
import argparse
import json
from pathlib import Path


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


def diagnose(manifest, preparation, delivery, history=None):
    cards = manifest.get("cards", [])
    ready = sum(isinstance(c, dict) and c.get("status") == "ready"
                and c.get("reviewed") is True for c in cards)
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
