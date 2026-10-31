"""Reserve a reviewed card promptly after its manifest reaches main.

This does not publish immediately. It reuses the existing one-attempt,
durable-pending Buffer reservation implementation and the currently active slots.
Only a manifest push on main is wired to this entrypoint in Actions.
"""
import json
import os
from datetime import datetime
from pathlib import Path

import advance_reservations
import stvv_post as publisher
from buffer_reservations import BufferReservations
from reservation_preview import ACTIVE_RESERVATION_SLOTS

ROOT = Path(__file__).resolve().parent


def assert_authorized_event(environ=None):
    env = os.environ if environ is None else environ
    if (env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("STVV_APPROVED_CARD_TRIGGER") != "true"
            or env.get("STVV_ADVANCE_RESERVATIONS") != "true"):
        raise RuntimeError("Reviewed-card reservation requires a main-branch manifest push")


def main():
    assert_authorized_event()
    now = datetime.now(publisher.JST)
    report = {
        "checked_at": now.isoformat(),
        "trigger": "approved_manifest_main_push",
        "mode": f"existing_{len(ACTIVE_RESERVATION_SLOTS)}_slot_advance_reservations",
        "x_display_verified": False,
        "publications_performed": 0,
        "new_reservations": [],
    }
    try:
        result = advance_reservations.run(
            publisher.load(), now, BufferReservations(), publisher.save,
            publisher.SESSION)
        report.update(status=result["status"],
                      new_reservations=result.get("new_reservations", []),
                      reconciliation_updates=result.get("updates", []))
    except Exception as error:
        # Do not log exception messages or retry an uncertain send.
        report.update(status="execution_failed_do_not_retry",
                      error_type=type(error).__name__)
        raise
    finally:
        output = ROOT / "reports/reservation-trigger-latest.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print("APPROVED_CARD_RESERVATION " + json.dumps(
        {"status": report["status"], "new_reservations": len(report["new_reservations"])},
        ensure_ascii=False))
    return report


if __name__ == "__main__":
    main()
