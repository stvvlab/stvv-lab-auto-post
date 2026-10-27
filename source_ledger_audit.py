"""Read-only audit of source ledger against recorded publications.

Never infer that an orphan source is safe to republish. This audit makes
inconsistent history visible while preserving fail-closed duplicate checks.
"""
import argparse
import json
from pathlib import Path

from content_guard import canonical_source


def audit_sources(history, manifest):
    if not isinstance(history, dict) or not isinstance(manifest, dict):
        raise ValueError("Expected history and manifest objects")
    used = history.get("news")
    publications = history.get("publication_log")
    cards = manifest.get("cards")
    if not isinstance(used, list) or not isinstance(publications, list) or not isinstance(cards, list):
        raise ValueError("Missing source ledger, publication log, or cards")
    published = set()
    for row in publications:
        if isinstance(row, dict) and isinstance(row.get("source"), str):
            published.add(canonical_source(row["source"]))
    orphaned = sorted({canonical_source(s) for s in used if isinstance(s, str)} - published)
    ready = [c for c in cards if isinstance(c, dict) and c.get("status") == "ready"
             and c.get("reviewed") is True]
    return {
        "status": "needs_reconciliation" if orphaned else "no_orphaned_used_sources",
        "used_sources_without_publication_log": orphaned,
        "ready_reviewed_cards": len(ready),
        "publication_source_count": len(published),
        "safe_to_repost_orphaned_sources": False,
        "note": "A source missing from publication_log may still have been posted; verify Buffer and X before correcting history. This script performs no sends or writes to posting history.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", default="posted.json")
    parser.add_argument("--manifest", default="editorial/imagegen_cards.json")
    parser.add_argument("--output", default="reports/source-ledger-audit.json")
    args = parser.parse_args()
    report = audit_sources(json.loads(Path(args.history).read_text(encoding="utf-8")),
                           json.loads(Path(args.manifest).read_text(encoding="utf-8")))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"], "orphaned used sources:", len(report["used_sources_without_publication_log"]),
          "ready cards:", report["ready_reviewed_cards"])


if __name__ == "__main__":
    main()
