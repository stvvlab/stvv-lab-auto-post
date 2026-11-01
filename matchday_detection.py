"""Read-only match-day detection from TheSportsDB, never publication approval.

Dates are considered provisional until a separately reviewed official fixture
confirms opponent and kickoff. No Buffer/X calls or posting history mutations.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from stvv_post import JST, SPORTS, TEAM, SESSION

ROOT = Path(__file__).resolve().parent
ENDPOINT = "eventsnext.php"


def detect(events, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware now required")
    now = now.astimezone(JST)
    found = []
    for event in events:
        if not isinstance(event, dict):
            continue
        home = str(event.get("idHomeTeam"))
        away = str(event.get("idAwayTeam"))
        if TEAM not in (home, away) or home == away:
            continue
        date_text = event.get("dateEvent")
        if not isinstance(date_text, str):
            continue
        try:
            day = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            continue
        # The provider's dateEvent is not necessarily JST. Use a +/- 1 day
        # margin; never claim that a match is definitively today from it.
        if not now.date() - timedelta(days=1) <= day <= now.date() + timedelta(days=7):
            continue
        opponent = event.get("strAwayTeam") if home == TEAM else event.get("strHomeTeam")
        if not isinstance(opponent, str) or not opponent.strip():
            continue
        found.append({
            "provider_event_id": str(event.get("idEvent") or ""),
            "provider_date": day.isoformat(),
            "opponent": opponent.strip(),
            "home_away": "HOME" if home == TEAM else "AWAY",
            "status": "requires_official_schedule_confirmation",
            "matchday_confirmed": False,
            "kickoff_jst": None,
            "can_publish": False,
        })
    return sorted(found, key=lambda item: (item["provider_date"], item["opponent"]))


def scan(now, session=SESSION):
    report = {
        "checked_at": now.astimezone(JST).isoformat(),
        "source": "TheSportsDB eventsnext.php",
        "status": "provider_unavailable",
        "candidates": [],
        "matchday_confirmed": False,
        "can_publish": False,
        "posting_performed": False,
        "note": "Read-only provisional fixture discovery; official opponent, date and kickoff cross-check required.",
    }
    try:
        response = session.get(f"{SPORTS}/{ENDPOINT}", params={"id": TEAM}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("Unexpected eventsnext payload")
        report["candidates"] = detect(payload["events"], now)
        report["status"] = "candidates_found" if report["candidates"] else "no_candidates"
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        report["error_type"] = type(error).__name__
    except Exception as error:
        # Network/JSON exceptions are diagnostic only and must never block posting.
        report["error_type"] = type(error).__name__
    return report


def main():
    now = datetime.now(JST)
    report = scan(now)
    path = ROOT / "reports/matchday-detection-latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "candidate_count": len(report["candidates"]),
                      "can_publish": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
