"""Seven content-aware, portrait-free STVV LAB editorial layouts."""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY, DARK, BLUE = "#06172C", "#030C18", "#123D71"
YELLOW, WHITE, MUTED = "#FFD400", "#F7FAFF", "#B9C8DC"
LABELS = {"player": "PLAYER LAB", "compare": "COMPARE", "data": "DATA LAB",
          "analysis": "TACTICS", "news": "STVV NEWS", "vote": "FAN VOICE",
          "recap": "MATCH REVIEW"}
FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
         "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for name in FONTS:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    raise RuntimeError("Japanese-compatible font unavailable")


def clean(message):
    text = re.sub(r"https?://\S+", "", message)
    text = re.sub(r"(?<!\w)#[^\s#]+", "", text)
    return text.strip() or "STVV LAB"


def wrap(draw, text, face, width):
    result = []
    for paragraph in text.splitlines():
        line = ""
        for char in paragraph.strip():
            next_line = line + char
            if line and draw.textbbox((0, 0), next_line, font=face)[2] > width:
                result.append(line)
                line = char
            else:
                line = next_line
        if line:
            result.append(line)
    return result


def fit(draw, text, width, height, max_size=70, min_size=28):
    for size in range(max_size, min_size - 1, -2):
        face = font(size)
        lines = wrap(draw, text, face, width)
        step = size + 19
        if len(lines) * step <= height:
            return face, lines, step
    raise ValueError("Text too long for legible card")


def write(draw, text, x, y, width, height, color=WHITE, max_size=70):
    face, lines, step = fit(draw, text, width, height, max_size)
    for line in lines:
        draw.text((x, y), line, font=face, fill=color)
        y += step
    return y


def pitch(draw, x, y, width, height):
    ink = "#4475A7"
    draw.rounded_rectangle((x, y, x+width, y+height), radius=12, outline=ink, width=5)
    draw.line((x+width//2, y, x+width//2, y+height), fill=ink, width=4)
    draw.ellipse((x+width//2-70, y+height//2-70,
                  x+width//2+70, y+height//2+70), outline=ink, width=4)
    for dx, dy in [(140, 125), (width//2, height//2), (width-140, height-125)]:
        draw.ellipse((x+dx-14, y+dy-14, x+dx+14, y+dy+14), fill=YELLOW)
    draw.line((x+140, y+125, x+width//2, y+height//2), fill=YELLOW, width=8)
    draw.line((x+width//2, y+height//2, x+width-140, y+height-125), fill=YELLOW, width=8)


def render_content_card(slot, message, destination):
    if slot not in LABELS:
        raise ValueError("Unknown slot")
    body = clean(message)
    # Seven visibly distinct visual identities, not one shared template.
    backgrounds = {
        "player": "#071B37", "compare": "#101127", "data": "#F1F5FA",
        "analysis": "#07352E", "news": "#F5D423",
        "vote": "#291C52", "recap": "#101820",
    }
    light = slot in {"data", "news"}
    foreground = DARK if light else WHITE
    image = Image.new("RGB", (W, H), backgrounds[slot])
    d = ImageDraw.Draw(image)
    if slot == "player":
        d.ellipse((620, 170, 1200, 750), outline=YELLOW, width=25)
        d.rectangle((0, 0, 26, 1180), fill=YELLOW)
    elif slot == "compare":
        d.polygon([(0, 0), (540, 0), (540, 1180), (0, 900)], fill="#183D77")
        d.polygon([(540, 0), (1080, 0), (1080, 900), (540, 1180)], fill="#332C55")
    elif slot == "data":
        d.rectangle((0, 0, 1080, 355), fill=BLUE)
    elif slot == "analysis":
        d.rectangle((0, 0, 1080, 355), fill="#09271F")
        d.line((0, 355, 1080, 355), fill=YELLOW, width=12)
    elif slot == "news":
        d.polygon([(730, 0), (1080, 0), (1080, 1180), (920, 1180)], fill="#E8B910")
    elif slot == "vote":
        for x in (70, 290, 510, 730, 950):
            d.ellipse((x-150, -180, x+150, 120), outline="#56498E", width=12)
    elif slot == "recap":
        d.rectangle((0, 0, 1080, 340), fill="#16385D")
        d.line((0, 340, 1080, 340), fill=YELLOW, width=12)
    d.rectangle((0, 0, W, 15), fill=YELLOW)
    d.text((64, 58), "STVV LAB", font=font(60), fill=WHITE if slot in {"data", "analysis", "recap", "compare", "player", "vote"} else DARK)
    d.text((68, 148), "INDEPENDENT FOOTBALL ANALYSIS", font=font(24), fill=WHITE if slot == "data" else (DARK if light else MUTED))
    d.rounded_rectangle((64, 225, 560, 310), radius=9, fill=DARK if light else YELLOW)
    d.text((84, 241), LABELS[slot], font=font(41), fill=WHITE if light else DARK)
    d.line((64, 348, 1016, 348), fill=DARK if light else YELLOW, width=5)

    if slot == "compare":
        d.rounded_rectangle((64, 385, 1016, 570), radius=18, fill=DARK)
        d.line((540, 398, 540, 560), fill=YELLOW, width=4)
        d.text((108, 405), "A", font=font(98), fill=WHITE)
        d.text((610, 405), "B", font=font(98), fill=YELLOW)
        write(d, body, 74, 625, 920, 475, max_size=65)
    elif slot == "data":
        for i, width in enumerate((330, 510, 720)):
            y = 420 + i*110
            d.rounded_rectangle((78, y, 78+width, y+42), radius=9,
                                fill=[BLUE, "#4475A7", YELLOW][i])
        d.text((75, 770), "DATA / CONTEXT", font=font(36), fill=YELLOW)
        write(d, body, 74, 850, 920, 260, color=DARK, max_size=52)
    elif slot == "analysis":
        pitch(d, 75, 390, 930, 385)
        write(d, body, 74, 825, 920, 300, max_size=54)
    elif slot == "news":
        d.rectangle((64, 394, 76, 1090), fill=YELLOW)
        write(d, body, 110, 430, 870, 640, color=DARK, max_size=76)
    elif slot == "vote":
        write(d, body, 74, 395, 920, 720, max_size=67)
        d.text((72, 1110), "YOUR VOICE MATTERS", font=font(32), fill=YELLOW)
    elif slot == "recap":
        d.rounded_rectangle((64, 390, 1016, 510), radius=12, fill=DARK)
        d.text((95, 415), "MATCH REVIEW", font=font(54), fill=YELLOW)
        write(d, body, 74, 565, 920, 555, max_size=65)
    else:
        d.ellipse((740, 395, 1020, 675), outline=YELLOW, width=11)
        write(d, body, 74, 415, 910, 690, max_size=67)

    d.rectangle((0, 1185, W, H), fill=("#123D71" if slot == "data" else DARK))
    d.line((64, 1210, 1016, 1210), fill=BLUE, width=4)
    d.text((65, 1240), "STVV LAB  |  FOOTBALL INSIGHT", font=font(31), fill=YELLOW)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination
