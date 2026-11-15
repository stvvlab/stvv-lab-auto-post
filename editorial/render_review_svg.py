"""Offline SVG rendering for unapproved review bundles; no publishing."""
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape


def xml_text(value):
    """Strip XML 1.0 forbidden codepoints before escaping text."""
    clean = "".join(ch for ch in value if ch in "\t\n\r" or 0x20 <= ord(ch) <= 0xD7FF or 0xE000 <= ord(ch) <= 0xFFFD or 0x10000 <= ord(ch) <= 0x10FFFF)
    return escape(clean)


def render_svg(item):
    if not isinstance(item, dict) or not isinstance(item.get("preview"), dict) or not isinstance(item.get("image_brief"), dict):
        raise ValueError("Malformed review item")
    preview, brief = item["preview"], item["image_brief"]
    keys = ("source_url", "official_heading", "date_jst", "caption", "source_body_sha256")
    if any(preview.get(k) != brief.get(k) for k in keys):
        raise ValueError("Preview/brief provenance mismatch")
    if (preview.get("approval_status") != "not_approved" or brief.get("approval_status") != "not_approved"
            or preview.get("ready_for_buffer") is not False or brief.get("ready_for_buffer") is not False
            or preview.get("image_status") != "not_generated" or brief.get("image_status") != "brief_only"
            or brief.get("image_path") is not None):
        raise ValueError("Not an unapproved image brief")
    title, date, url, digest = (preview.get(k) for k in ("official_heading", "date_jst", "source_url", "source_body_sha256"))
    if (not isinstance(title, str) or not title.strip() or len(title) > 64
            or not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
            or not isinstance(url, str) or not url.startswith("https://stvv.jp/")
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("Invalid provenance or headline too long")
    lines = [title[i:i+24] for i in range(0, len(title), 24)]
    nodes = "\n".join(f'<text x="90" y="{295+i*70}" font-size="51" font-weight="700" fill="#FFFFFF">{xml_text(line)}</text>' for i, line in enumerate(lines))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
<rect width="1200" height="675" fill="#091B37"/>
<path d="M 860 0 L 1200 0 L 1200 675 L 1040 675 Z" fill="#122C4F"/>
<rect x="90" y="105" width="88" height="9" fill="#F4D334"/>
<text x="90" y="176" font-family="sans-serif" font-size="28" letter-spacing="4" fill="#F4D334">STVV LAB</text>
{nodes}
<rect x="90" y="554" width="1020" height="1" fill="#61718A"/>
<text x="90" y="607" font-family="sans-serif" font-size="22" fill="#D7DFEA">OFFICIAL SOURCE  |  {xml_text(date)}</text>
<text x="1110" y="607" text-anchor="end" font-family="sans-serif" font-size="18" fill="#F4D334">REVIEW ONLY</text>
</svg>'''


def render_bundle(bundle, output_dir):
    if not isinstance(bundle, dict) or bundle.get("status") not in ("review_required", "no_preview_ready") or not isinstance(bundle.get("items"), list):
        raise ValueError("Invalid review bundle")
    output_dir = Path(output_dir)
    results = []
    seen_digests = set()
    for item in bundle["items"]:
        try:
            svg = render_svg(item)
        except ValueError as exc:
            results.append({"status": "skipped", "reason": str(exc)})
            continue
        digest = item["preview"]["source_body_sha256"]
        if digest in seen_digests:
            results.append({"status": "skipped", "reason": "Duplicate source digest"})
            continue
        seen_digests.add(digest)
        path = output_dir / f"review-{digest}.svg"
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as target:
                target.write(svg)
        except FileExistsError:
            results.append({"status": "skipped", "reason": "Review image already exists", "path": str(path)})
            continue
        results.append({"status": "rendered_unapproved", "path": str(path), "source_url": item["preview"]["source_url"]})
    return {"images": results, "approval_performed": False, "buffer_sent": False, "x_published": False}


def main():
    root = Path(__file__).resolve().parent.parent
    bundle = json.loads((root / "reports/review-bundle-latest.json").read_text(encoding="utf-8"))
    print(json.dumps(render_bundle(bundle, root / "reports/review-images"), ensure_ascii=False))


if __name__ == "__main__":
    main()
