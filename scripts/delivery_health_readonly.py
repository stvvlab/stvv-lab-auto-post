"""Read-only diagnosis of the latest STVV delivery and preparation reports.

This script never invokes Buffer, X, or the posting runner.
"""
import json
import sys
from pathlib import Path


def summarize(delivery, preparation):
    delay = delivery.get("start_delay_seconds")
    return {
        "delivery_status": delivery.get("status", "unknown"),
        "preparation_status": preparation.get("status", "unknown"),
        "schedule_delay_seconds": delay,
        "schedule_delayed_over_hour": isinstance(delay, (int, float)) and delay > 3600,
        "ready_cards": preparation.get("ready_cards", 0),
        "new_publications": len(delivery.get("new_publications") or []),
        "new_reservations": len(delivery.get("new_reservations") or []),
        "x_display_verified": delivery.get("x_display_verified") is True,
        "needs_editorial_preparation": not preparation.get("candidates") and not delivery.get("new_publications"),
        "note": "Read-only report; Buffer sent is not proof of X display. No posting attempted.",
    }


def main():
    root = Path(__file__).resolve().parent.parent
    try:
        delivery = json.loads((root / "reports/delivery-latest.json").read_text(encoding="utf-8"))
        preparation = json.loads((root / "reports/preparation-latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "report_unavailable", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(summarize(delivery, preparation), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
