"""Generate factual, post-specific, portrait-free Japanese social cards."""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY, BLUE, YELLOW, WHITE = "#06172C", "#123D71", "#FFD400", "#F7FAFF"
LABELS = {
    "player": "PLAYER LAB", "compare": "COMPARE", "data": "DATA LAB",
    "analysis": "TACTICS", "news": "STVV NEWS", "vote": "FAN VOICE",
    "recap": "MATCH REVIEW",
}
FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size):
    for name in FONTS:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    raise RuntimeError("Japanese-compatible font unavailable")


def wrap(draw, text, face, max_width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for char in paragraph:
            trial = line + char
            if line and draw.textbbox((0, 0), trial, font=face)[2] > max_width:
                lines.append(line)
                line = char
            else:
                line = trial
        if line:
            lines.append(line)
    return lines


def render_content_card(slot, message, destination):
    if slot not in LABELS:
        raise ValueError("Unknown slot")
    # Use exactly the already-approved post text, never invent facts or stats.
    body = re.sub(r"https?://\S+", "", message)
    body = re.sub(r"#(?:STVV|シントトロイデン|STVVLAB)\S*", "", body)
    body = re.sub(r"^[^\w\u3040-\u30ff\u3400-\u9fff]+", "", body.strip())
    body = body.strip() or "STVV LAB"
    image = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(image)
    draw.polygon([(720, 0), (1080, 0), (1080, 1080), (800, 1080), (430, 380)], fill=BLUE)
    draw.rectangle((0, 0, W, 18), fill=YELLOW)
    draw.text((65, 70), "STVV LAB", font=font(64), fill=WHITE)
    draw.rounded_rectangle((65, 200, 570, 285), radius=12, fill=YELLOW)
    draw.text((87, 218), LABELS[slot], font=font(41), fill=NAVY)
    draw.line((65, 345, 1010, 345), fill=YELLOW, width=5)

    # Size to fit all essential lines without clipping.
    for size in (68, 61, 54, 48, 42, 36):
        face = font(size)
        lines = wrap(draw, body, face, 920)
        line_height = size + 24
        if len(lines) * line_height <= 720:
            break
    else:
        raise ValueError("Post text too long for readable card")
    y = 395
    for line in lines:
        draw.text((65, y), line, font=face, fill=WHITE)
        y += line_height
    draw.rectangle((0, 1190, W, H), fill="#04101F")
    draw.text((65, 1235), "STVV LAB  |  INDEPENDENT FOOTBALL MEDIA", font=font(28), fill=YELLOW)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination
