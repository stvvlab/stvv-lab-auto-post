"""Render deterministic, rights-safe STVV LAB draft cards. Never publish or approve."""
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT_PATHS = [
    ROOT / ".cache/stvv-fonts/NotoSansCJKjp-Bold.otf",
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def font(size):
    for path in FONT_PATHS:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("Japanese card font unavailable; cannot render")


PALETTES = {
    "navy_gold": ((8, 23, 57), (248, 212, 65), (235, 240, 250)),
    "ice_blue": ((13, 47, 72), (115, 227, 231), (245, 250, 252)),
    "crimson": ((53, 19, 36), (255, 146, 123), (252, 242, 240)),
    "forest": ((14, 45, 43), (169, 226, 170), (244, 250, 244)),
}


def render_card(title, path, palette="navy_gold"):
    """Only render supplied reviewed-text draft as a preview (not an approved asset)."""
    if not isinstance(title, str) or not title.strip() or len(title) > 90:
        raise ValueError("Invalid official headline")
    if any(c in title for c in "\r\n\t"):
        raise ValueError("Unexpected control characters")
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError("Only PNG preview supported")
    if palette not in PALETTES:
        raise ValueError("Unknown palette")
    background, accent, foreground = PALETTES[palette]
    image = Image.new("RGB", (1448, 1086), background)
    draw = ImageDraw.Draw(image)
    yellow = accent
    draw.rectangle((72, 98, 1376, 110), fill=yellow)
    draw.text((80, 135), "STVV LAB", font=font(70), fill=yellow)
    draw.text((80, 246), "OFFICIAL NEWS", font=font(36), fill=foreground)
    # Width-based wrapping keeps mixed Japanese/Latin headlines inside safe area.
    lines, current = [], ""
    headline_font = font(63)
    for character in re.sub(r"\s+", " ", title).strip():
        candidate = current + character
        if draw.textbbox((0, 0), candidate, font=headline_font)[2] > 1230 and current:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 5:
        raise ValueError("Headline will not fit the safe area")
    for n, line in enumerate(lines):
        draw.text((80, 360 + n * 100), line, font=headline_font, fill=foreground)
    draw.rectangle((72, 961, 1376, 968), fill=yellow)
    draw.text((80, 992), "SOURCE: STVV OFFICIAL  •  DRAFT PREVIEW", font=font(29),
              fill=(235, 240, 250))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def build_previews(drafts, output_dir):
    results = []
    for idx, draft in enumerate(drafts.get("drafts", [])):
        if draft.get("status") != "needs_review_and_image" or draft.get("reviewed") is not False:
            continue
        title = draft.get("text", "").split("｜", 1)
        if len(title) != 2:
            continue
        headline = title[1].split("\n", 1)[0]
        destination = Path(output_dir) / f"official_draft_{idx:03d}.png"
        try:
            palette = tuple(PALETTES)[idx % len(PALETTES)]
            render_card(headline, destination, palette=palette)
            results.append({"source_url": draft.get("source_url"),
                            "preview_path": str(destination), "palette": palette,
                            "status": "needs_visual_review", "reviewed": False})
        except (ValueError, RuntimeError, OSError) as error:
            results.append({"source_url": draft.get("source_url"),
                            "status": "render_failed", "error_type": type(error).__name__})
    return {"publication_performed": False, "images_approved": 0, "previews": results}


def main():
    drafts = json.loads((ROOT / "reports/simple-post-drafts.json").read_text(encoding="utf-8"))
    result = build_previews(drafts, ROOT / "generated/draft-previews")
    output = ROOT / "reports/simple-image-previews.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Draft image previews:", len(result["previews"]), "— not approved or published")


if __name__ == "__main__":
    main()
