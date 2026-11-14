"""Read-only, machine-readable preview artifact for human chat review.

Never turns a draft into approval, image creation, Buffer reservation or X post.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_preview(handoff):
    items = handoff.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Handoff items must be a list")
    previews = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        url, caption, digest = (item.get("source_url"),
                                item.get("caption"), item.get("source_body_sha256"))
        if (item.get("status") != "draft_needs_review"
                or item.get("approved") is not False
                or not isinstance(url, str) or not url.startswith("https://stvv.jp/")
                or not isinstance(caption, str) or not caption.strip()
                or len(caption) > 270
                or not isinstance(digest, str) or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)
                or url in seen):
            continue
        seen.add(url)
        previews.append({
            "source_url": url,
            "official_heading": item.get("official_heading"),
            "date_jst": item.get("date_jst"),
            "caption": caption,
            "source_body_sha256": digest,
            "image_status": "not_generated",
            "approval_status": "not_approved",
            "ready_for_buffer": False,
        })
    return {
        "status": "review_required" if previews else "no_preview_ready",
        "previews": previews,
        "chat_delivery_performed": False,
        "approval_performed": False,
        "image_generation_performed": False,
        "buffer_sent": False,
        "x_published": False,
    }


def main():
    handoff = json.loads((ROOT / "reports/editorial-handoff-latest.json").read_text(encoding="utf-8"))
    preview = build_preview(handoff)
    target = ROOT / "reports/chat-preview-latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Unapproved chat previews: {len(preview['previews'])}; no external delivery")


if __name__ == "__main__":
    main()
