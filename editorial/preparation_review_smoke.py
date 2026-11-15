"""Offline verified-inventory -> unapproved SVG review, excluding confirmed X posts.

No Buffer, X, approval or ChatGPT delivery. Requires explicit output directory.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

from editorial_handoff import build_handoff
from editorial.offline_review_smoke import run


def run_preparation(preparation_path, external_path, output_dir):
    preparation = json.loads(Path(preparation_path).read_text(encoding="utf-8"))
    external = json.loads(Path(external_path).read_text(encoding="utf-8"))
    if not isinstance(external, dict) or not isinstance(external.get("items"), list):
        raise ValueError("Invalid external publication ledger")
    confirmed = [item for item in external["items"] if isinstance(item, dict)
                 and item.get("status") == "confirmed_external_publication"]
    used = {item.get("source_url") for item in confirmed if isinstance(item.get("source_url"), str)}
    used_digests = {item.get("source_body_sha256") for item in confirmed
                    if isinstance(item.get("source_body_sha256"), str)
                    and len(item["source_body_sha256"]) == 64}
    # A previously published story may have moved to a different official URL.
    # Only exact verified body hashes count; absent hashes never cause a skip.
    candidates = preparation.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Invalid preparation candidates")
    def conflicting_round(candidate):
        """Do not render a headline that contradicts the source body round."""
        heading = candidate.get("official_heading", "")
        body = candidate.get("source_body", "")
        if not isinstance(heading, str) or not isinstance(body, str):
            return False
        # Japanese source pages may mix ASCII and full-width round numbers.
        heading = unicodedata.normalize("NFKC", heading)
        body = unicodedata.normalize("NFKC", body[:1000])
        headline_round = re.search(r"第\s*([0-9]+)\s*節", heading)
        body_round = re.search(r"第\s*([0-9]+)\s*節", body)
        return bool(headline_round and body_round and
                    headline_round.group(1) != body_round.group(1))

    unpublished = [c for c in candidates if isinstance(c, dict)
                   and c.get("source_url") not in used
                   and c.get("body_sha256") not in used_digests]
    conflicts = [c for c in unpublished if conflicting_round(c)]
    filtered = dict(preparation)
    filtered["candidates"] = [c for c in unpublished if not conflicting_round(c)]
    handoff = build_handoff(filtered)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handoff_path = output / "editorial-handoff.json"
    with handoff_path.open("x", encoding="utf-8") as target:
        json.dump(handoff, target, ensure_ascii=False, indent=2)
        target.write("\n")
    result = run(handoff_path, output / "review")
    result["confirmed_external_skipped"] = len(candidates) - len(unpublished)
    result["conflicting_round_skipped"] = len(conflicts)
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
