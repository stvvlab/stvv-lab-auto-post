"""Read-only end-to-end handoff to chat preview and image brief.

No image generation, approval, Buffer scheduling, or X publishing.
"""
import json
from pathlib import Path

from editorial.chat_preview import build_preview
from editorial.image_briefs import build_image_briefs

ROOT = Path(__file__).resolve().parent.parent


def prepare_review_bundle(handoff):
    preview = build_preview(handoff)
    images = build_image_briefs(preview)
    if len(images["briefs"]) != len(preview["previews"]):
        raise ValueError("Preview/image brief mismatch")
    return {
        "status": "review_required" if preview["previews"] else "no_preview_ready",
        "items": [
            {"preview": item, "image_brief": brief}
            for item, brief in zip(preview["previews"], images["briefs"])
        ],
        "chat_delivery_performed": False,
        "image_generation_performed": False,
        "approval_performed": False,
        "buffer_sent": False,
        "x_published": False,
    }


def main():
    source = ROOT / "reports/editorial-handoff-latest.json"
    handoff = json.loads(source.read_text(encoding="utf-8"))
    bundle = prepare_review_bundle(handoff)
    target = ROOT / "reports/review-bundle-latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Review bundle items: {len(bundle['items'])}; no delivery or publishing")


if __name__ == "__main__":
    main()
