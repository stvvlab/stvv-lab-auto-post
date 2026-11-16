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
    if (not isinstance(title, str) or not title.strip()
            or not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
            or not isinstance(url, str) or not url.startswith("https://stvv.jp/")
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("Invalid provenance")
    # Long official headlines must not silently discard a valid review candidate.
    # Keep the full source headline in the bundle; shorten only image display.
    display_title = title
    if len(title) > 64:
        caption = preview.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError("Long headline without review caption")
        display_title = caption.split("\n", 1)[0].lstrip("📣📢⚽ ").strip()
        if len(display_title) > 64:
            display_title = display_title[:63] + "…"
    # Japanese glyphs are much wider than Latin characters: 24 glyphs at 51px
    # overflow a 1200px canvas. Use a conservative display-width budget.
    # Keep source title and full caption unchanged in the review bundle.
    def display_width(text):
        import unicodedata
        return sum(2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1 for ch in text)
    lines, line = [], ""
    for char in display_title:
        if line and display_width(line + char) > 36:
            lines.append(line)
            line = ""
        line += char
    if line:
        lines.append(line)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip("…")[:max(0, len(lines[-1])-1)] + "…"
    nodes = "\n".join(f'<text x="90" y="{295+i*70}" font-family="Noto Sans CJK JP, sans-serif" font-size="51" font-weight="700" fill="#FFFFFF">{xml_text(line)}</text>' for i, line in enumerate(lines))
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
    seen_urls = set()
    seen_phases = set()
    unphased_urls = set()
    for item in bundle["items"]:
        try:
            svg = render_svg(item)
        except ValueError as exc:
            results.append({"status": "skipped", "reason": str(exc)})
            continue
        digest = item["preview"]["source_body_sha256"]
        source_url = item["preview"]["source_url"]
        # A source can support distinct editorial phases (preview, lineup,
        # result, analysis). Require an explicit phase on BOTH items; otherwise
        # retain the conservative URL-only duplicate rule.
        purpose = item["preview"].get("editorial_purpose")
        phase = purpose.get("phase") if isinstance(purpose, dict) else None
        phase = phase.strip() if isinstance(phase, str) else None
        phase_key = (source_url, phase) if phase else None
        if source_url in seen_urls and (not phase_key or phase_key in seen_phases or source_url in unphased_urls):
            results.append({"status": "skipped", "reason": "Duplicate source URL/phase" if phase_key else "Duplicate source URL"})
            continue
        if digest in seen_digests:
            results.append({"status": "skipped", "reason": "Duplicate source digest"})
            continue
        seen_digests.add(digest)
        seen_urls.add(source_url)
        if phase_key:
            seen_phases.add(phase_key)
        else:
            unphased_urls.add(source_url)
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
