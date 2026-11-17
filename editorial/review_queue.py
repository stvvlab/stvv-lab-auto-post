"""Read-only editorial review queue. Never approves, schedules or publishes."""
import json
from pathlib import Path
from editorial.pipeline_progress import ROOT, snapshot, load_json


def build_review_queue(root=ROOT):
    progress = snapshot(root)
    preparation = load_json(Path(root) / "reports/preparation-latest.json")
    candidates = preparation.get("candidates", []) if isinstance(preparation, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    allowed = set(progress["fresh_candidate_sources"])
    seen = set()
    queue = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        url = candidate.get("source_url")
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url or url not in allowed or url in seen:
            continue
        seen.add(url)
        queue.append({
            "source_url": url,
            "date_jst": candidate.get("date_jst"),
            "official_heading": candidate.get("official_heading"),
            "source_excerpt": str(candidate.get("source_body") or "")[:600],
            "status": "needs_human_review",
            "caption": None,
            "image_asset": None,
            "approved": False,
            "publish_allowed": False,
        })
    return {
        "status": "review_required" if queue else "no_fresh_candidate",
        "queue": queue,
        "remote_buffer_x_checked": False,
        "posting_performed": False,
        "note": "Local URL dedupe only; check remote history and topic overlap before approval.",
    }


if __name__ == "__main__":
    print(json.dumps(build_review_queue(), ensure_ascii=False, indent=2))
