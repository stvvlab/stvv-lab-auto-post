"""Offline verified-inventory -> unapproved SVG review, excluding confirmed X posts.

No Buffer, X, approval or ChatGPT delivery. Requires explicit output directory.
"""
import argparse
import json
from pathlib import Path

from editorial_handoff import build_handoff
from editorial.offline_review_smoke import run


def run_preparation(preparation_path, external_path, output_dir):
    preparation = json.loads(Path(preparation_path).read_text(encoding="utf-8"))
    external = json.loads(Path(external_path).read_text(encoding="utf-8"))
    if not isinstance(external, dict) or not isinstance(external.get("items"), list):
        raise ValueError("Invalid external publication ledger")
    used = {item.get("source_url") for item in external["items"]
            if isinstance(item, dict) and item.get("status") == "confirmed_external_publication"}
    candidates = preparation.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Invalid preparation candidates")
    filtered = dict(preparation)
    filtered["candidates"] = [c for c in candidates
                              if isinstance(c, dict) and c.get("source_url") not in used]
    handoff = build_handoff(filtered)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handoff_path = output / "editorial-handoff.json"
    with handoff_path.open("x", encoding="utf-8") as target:
        json.dump(handoff, target, ensure_ascii=False, indent=2)
        target.write("\n")
    result = run(handoff_path, output / "review")
    result["confirmed_external_skipped"] = len(candidates) - len(filtered["candidates"])
    result["handoff_path"] = str(handoff_path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", required=True)
    parser.add_argument("--external-publications", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(run_preparation(args.preparation, args.external_publications,
                                     args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
