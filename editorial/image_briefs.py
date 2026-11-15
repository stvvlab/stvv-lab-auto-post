"""Read-only image production briefs from unapproved chat previews.

No image is generated, approved, uploaded, scheduled, or published here.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_image_briefs(preview):
    if not isinstance(preview, dict) or not isinstance(preview.get("previews"), list):
        raise ValueError("Malformed chat preview")
    briefs = []
    seen = set()
    for item in preview["previews"]:
        if not isinstance(item, dict):
            continue
        url = item.get("source_url")
        if (not isinstance(url, str) or not url.startswith("https://stvv.jp/")
                or url in seen or item.get("approval_status") != "not_approved"
                or item.get("ready_for_buffer") is not False
                or item.get("image_status") != "not_generated"
                or not isinstance(item.get("caption"), str)
                or not item["caption"].strip()
                or not isinstance(item.get("official_heading"), str)
                or not item["official_heading"].strip()):
            continue
        seen.add(url)
        briefs.append({
            "source_url": url,
            "official_heading": item["official_heading"],
            "date_jst": item.get("date_jst"),
            "caption": item["caption"],
            "source_body_sha256": item.get("source_body_sha256"),
            "visual_direction": "Navy and yellow football editorial graphic; no player faces, logos, scores or invented fixtures; use verified headline only",
            "image_status": "brief_only",
            "image_path": None,
            "image_sha256": None,
            "approval_status": "not_approved",
            "ready_for_buffer": False,
        })
    return {"status": "image_briefs_ready" if briefs else "no_image_briefs",
            "briefs": briefs, "image_generation_performed": False,
            "approval_performed": False, "buffer_sent": False, "x_published": False}


def main():
    source = ROOT / "reports/chat-preview-latest.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    output = ROOT / "reports/image-briefs-latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = build_image_briefs(data)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Image briefs: {len(result['briefs'])}; no image generation or publishing")


if __name__ == "__main__":
    main()
