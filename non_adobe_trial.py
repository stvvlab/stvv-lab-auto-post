"""Read-only preflight for STVV LAB's existing Adobe-free reviewed-card route."""
import argparse
import json
from pathlib import Path

def check_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("enabled") is not True or not isinstance(data.get("cards"), list):
        raise ValueError("Reviewed-card manifest disabled or malformed")
    ready = []
    blocked = []
    for index, card in enumerate(data["cards"]):
        if not isinstance(card, dict):
            blocked.append({"index": index, "reason": "malformed_card"})
            continue
        if card.get("status") != "ready":
            continue
        if card.get("reviewed") is not True:
            blocked.append({"index": index, "reason": "not_reviewed"})
            continue
        if not all(card.get(k) for k in ("source_url", "text", "asset_path", "sha256", "dimensions", "slots", "date_jst")):
            blocked.append({"index": index, "reason": "missing_metadata"})
            continue
        ready.append({"index": index, "source_url": card["source_url"]})
    return {
        "mode": "non_adobe_existing_reviewed_cards",
        "adobe_api_used": False,
        "buffer_mutation_performed": False,
        "x_publication_performed": False,
        "ready_metadata_candidates": ready,
        "blocked": blocked,
        "note": "This checks local manifest metadata only. Existing publisher independently verifies content, SHA256, public asset bytes, duplicates and freshness before any Buffer send."
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="editorial/imagegen_cards.json")
    p.add_argument("--output", default="reports/non-adobe-trial.json")
    args = p.parse_args()
    result = check_manifest(args.manifest)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Adobe-free reviewed-card preflight: %d ready metadata candidates, %d blocked; no post created" % (len(result["ready_metadata_candidates"]), len(result["blocked"])))

if __name__ == "__main__":
    main()
