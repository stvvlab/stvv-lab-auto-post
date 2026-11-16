"""Explicit-path offline review smoke runner. No posting or approval."""
import argparse
import json
from pathlib import Path
from editorial.review_bundle import prepare_review_bundle
from editorial.render_review_svg import render_bundle


def run(handoff_path, output_dir):
    handoff = json.loads(Path(handoff_path).read_text(encoding="utf-8"))
    bundle = prepare_review_bundle(handoff)
    output = Path(output_dir)
    # Refuse to replace any prior review bundle or image.
    if (output / "review-bundle.json").exists():
        raise FileExistsError(output / "review-bundle.json")
    # Persist the bundle first: a failed JSON write must not leave orphaned images.
    output.mkdir(parents=True, exist_ok=True)
    bundle_path = output / "review-bundle.json"
    with bundle_path.open("x", encoding="utf-8") as target:
        json.dump(bundle, target, ensure_ascii=False, indent=2)
        target.write("\n")
    images = render_bundle(bundle, output / "images")
    # Reflect actual SVG output without implying approval or publication.
    rendered = {
        (entry["source_url"], Path(entry["path"]).stem.removeprefix("review-")): entry["path"]
        for entry in images["images"] if entry["status"] == "rendered_unapproved"
    }
    for item in bundle["items"]:
        preview = item["preview"]
        key = (preview["source_url"], preview["source_body_sha256"])
        if key in rendered:
            preview["image_status"] = "generated_unapproved"
            preview["image_path"] = rendered[key]
            item["image_brief"]["image_status"] = "generated_unapproved"
            item["image_brief"]["image_path"] = rendered[key]
    bundle["image_generation_performed"] = bool(rendered)
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"bundle_path": str(bundle_path), "candidate_count": len(bundle["items"]),
            "images": images["images"], "chat_delivery_performed": False,
            "approval_performed": False, "buffer_sent": False, "x_published": False}


def main():
    parser = argparse.ArgumentParser(description="Offline STVV review smoke run")
    parser.add_argument("--handoff", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.handoff, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
