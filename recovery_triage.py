"""Deterministic, read-only STVV posting recovery diagnosis.
Never publishes, alters history, or infers an X post from an Action's success.
"""
import argparse
import json
from pathlib import Path


def diagnose(manifest, preparation, delivery):
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
    if delivery.get("start_delay_seconds", 0) > 1800:
        problems.append("github_start_delayed_over_30_minutes")
    if not delivery.get("x_display_verified", False):
        # Absence of verification is not itself proof of a missed post.
        if delivery.get("new_publications"):
            problems.append("x_publication_not_verified")
    return {
        "status": "needs_recovery" if problems else "no_detected_blocker",
        "problems": problems,
        "ready_reviewed_cards": ready,
        "last_delivery_status": delivery.get("status", "unknown"),
        "delivery_run_id": delivery.get("run_id"),
        "preparation_checked_at": preparation.get("checked_at"),
        "new_buffer_reservations": len(delivery.get("new_reservations", [])),
        "new_x_publications_verified": sum(
            1 for p in delivery.get("new_publications", [])
            if isinstance(p, dict) and p.get("x_display_verified") is True),
        "next_fix": ("Prepare and explicitly approve a fact-checked new image/card, "
                     "then verify Buffer reservation and public X display. "
                     "Do not reuse a published card or relax duplicates."
                     if ready == 0 else
                     "Investigate actual reservation and publication state without replaying unknown sends."),
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
                      load("reports/delivery-latest.json"))
    out = Path(args.output)
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
