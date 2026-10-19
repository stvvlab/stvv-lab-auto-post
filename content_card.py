"""STVV LAB: seven bold, fact-safe, portrait-free football editorial posters."""
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY, INK, BLUE = "#061529", "#020A15", "#1462B3"
YELLOW, WHITE, MUTED = "#FFE000", "#FFFFFF", "#B9CCE0"
LABELS = {
    "player": ("PLAYER", "ANALYSIS"), "compare": ("HEAD TO", "HEAD"),
    "data": ("DATA", "INSIGHTS"), "analysis": ("TACTICS", "ANALYSIS"),
    "news": ("NEWS", "UPDATE"), "vote": ("FAN", "VOICE"),
    "recap": ("MATCH", "REVIEW"),
}
FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size):
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Japanese-compatible font unavailable")


def clean(message):
    message = re.sub(r"https?://\S+", "", message)
    message = re.sub(r"(?<!\w)#[^\s#]+", "", message)
    return message.strip() or "STVV LAB"


def lines(draw, text, face, max_width):
    result = []
    for paragraph in text.splitlines():
        current = ""
        for char in paragraph.strip():
            trial = current + char
            if current and draw.textbbox((0, 0), trial, font=face)[2] > max_width:
                result.append(current)
                current = char
            else:
                current = trial
        if current:
            result.append(current)
    return result


def write(draw, text, x, y, width, height, color=WHITE, size=59):
    for pt in range(size, 25, -2):
        face = font(pt)
        wrapped = lines(draw, text, face, width)
        step = pt + 16
        if len(wrapped) * step <= height:
            for line in wrapped:
                draw.text((x, y), line, font=face, fill=color, stroke_width=0)
                y += step
            return y
    # Preserve the start of a long story, with a visible truncation indicator.
    face = font(26)
    step = 40
    allowed = max(1, height // step)
    wrapped = lines(draw, text, face, width)
    for line in wrapped[:allowed - 1]:
        draw.text((x, y), line, font=face, fill=color)
        y += step
    draw.text((x, y), (wrapped[allowed - 1][:22] + "…") if len(wrapped) >= allowed else "…",
              font=face, fill=color)
    return y + step


def slash(draw, y, color=YELLOW, thickness=36):
    draw.polygon([(0, y+140), (W, y-100), (W, y-100+thickness),
                  (0, y+140+thickness)], fill=color)


def grit(draw, color="#17345B"):
    # Deterministic editorial texture, no photo rights or external assets.
    for i in range(35):
        x = (i * 197 + 41) % W
        y = (i * 389 + 107) % 1130
        draw.line((x, y, x+34, y-8), fill=color, width=2)


def brand(draw, number):
    draw.rectangle((0, 0, W, 17), fill=YELLOW)
    draw.text((55, 39), "STVV LAB", font=font(44), fill=WHITE)
    draw.text((810, 53), f"0{number} / 07", font=font(27), fill=YELLOW)


def headline(draw, slot, y=170, size=112):
    first, second = LABELS[slot]
    draw.text((51, y), first, font=font(size), fill=WHITE,
              stroke_width=2, stroke_fill=INK)
    draw.text((51, y+size-5), second, font=font(size), fill=YELLOW,
              stroke_width=2, stroke_fill=INK)


def panel(draw, text, y, height=360, color=WHITE):
    draw.rounded_rectangle((46, y-24, 1034, y+height), radius=18, fill="#07182D")
    draw.rectangle((46, y-24, 57, y+height), fill=YELLOW)
    write(draw, text, 88, y+12, 905, height-54, color=color, size=60)


def footer(draw, slot):
    draw.rectangle((0, 1194, W, H), fill=INK)
    draw.line((50, 1215, 1030, 1215), fill=YELLOW, width=5)
    draw.text((55, 1243), "STVV LAB  /  FOOTBALL ANALYSIS", font=font(31), fill=WHITE)
    draw.text((900, 1246), slot.upper(), font=font(20), fill=YELLOW)


def pitch(draw, x, y, w, h):
    draw.rounded_rectangle((x, y, x+w, y+h), radius=12,
                           fill="#0C433B", outline=WHITE, width=4)
    draw.line((x+w//2, y, x+w//2, y+h), fill="#82B6AA", width=4)
    draw.ellipse((x+w//2-60, y+h//2-60, x+w//2+60, y+h//2+60),
                 outline="#82B6AA", width=4)
    for px, py in [(0.15, 0.3), (0.33, 0.68), (0.54, 0.40), (0.76, 0.67)]:
        cx, cy = x+int(w*px), y+int(h*py)
        draw.ellipse((cx-17, cy-17, cx+17, cy+17), fill=YELLOW)
    # Decorative schematic, not a claimed match event.
    draw.line((x+int(w*.15), y+int(h*.3), x+int(w*.33), y+int(h*.68),
               x+int(w*.54), y+int(h*.4), x+int(w*.76), y+int(h*.67)),
              fill=YELLOW, width=9)


def render_content_card(slot, message, destination):
    if slot not in LABELS:
        raise ValueError("Unknown slot")
    body = clean(message)
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    grit(d)
    number = list(LABELS).index(slot)+1

    if slot == "player":
        d.ellipse((595, 340, 1260, 1000), outline=BLUE, width=36)
        d.ellipse((705, 445, 950, 690), fill="#193E6C", outline=YELLOW, width=12)
        d.polygon([(590, 1010), (670, 720), (950, 720), (1040, 1010)], fill="#174A8A")
        d.text((746, 750), "10", font=font(155), fill=YELLOW)
        slash(d, 950)
        brand(d, number)
        headline(d, slot, 165, 106)
        panel(d, body, 830, 335)

    elif slot == "compare":
        d.polygon([(0, 370), (525, 330), (525, 1060), (0, 1100)], fill="#104A88")
        d.polygon([(555, 330), (1080, 370), (1080, 1100), (555, 1060)], fill="#192D51")
        slash(d, 960)
        brand(d, number)
        headline(d, slot, 165, 105)
        d.text((180, 445), "A", font=font(185), fill=WHITE)
        d.text((460, 480), "VS", font=font(75), fill=YELLOW)
        d.text((740, 445), "B", font=font(185), fill=WHITE)
        panel(d, body, 760, 400)

    elif slot == "data":
        brand(d, number)
        headline(d, slot, 165, 109)
        # Chart is explicitly a decorative motif; never invent metrics.
        d.text((64, 460), "DATA / CONTEXT", font=font(33), fill=MUTED)
        for i, h in enumerate((75, 150, 108, 208, 245, 175, 295)):
            x = 105+i*128
            d.rounded_rectangle((x, 805-h, x+70, 805), radius=8,
                                fill=YELLOW if i == 6 else "#2365A3")
        d.line((70, 815, 1020, 815), fill=WHITE, width=3)
        d.text((68, 833), "VISUAL MOTIF  /  NOT MATCH STATISTICS",
               font=font(21), fill=MUTED)
        panel(d, body, 890, 265)

    elif slot == "analysis":
        brand(d, number)
        headline(d, slot, 155, 104)
        pitch(d, 78, 445, 924, 410)
        d.text((76, 866), "SCHEMATIC  /  NOT TRACKING DATA",
               font=font(23), fill=MUTED)
        panel(d, body, 925, 230)

    elif slot == "news":
        d.polygon([(740, 0), (1080, 0), (1080, 1150), (930, 1150)], fill="#0B4B91")
        slash(d, 930)
        brand(d, number)
        headline(d, slot, 170, 122)
        d.rounded_rectangle((56, 500, 300, 565), radius=5, fill=YELLOW)
        d.text((80, 509), "LATEST", font=font(37), fill=INK)
        panel(d, body, 625, 520)

    elif slot == "vote":
        d.ellipse((610, 380, 1090, 860), outline="#1D5794", width=38)
        d.ellipse((730, 500, 970, 740), outline=YELLOW, width=28)
        slash(d, 970)
        brand(d, number)
        headline(d, slot, 165, 126)
        d.text((74, 465), "YOUR OPINION", font=font(42), fill=YELLOW)
        panel(d, body, 655, 500)

    else:  # recap
        d.rectangle((0, 395, W, 775), fill="#123D71")
        d.polygon([(0, 770), (1080, 470), (1080, 800), (0, 1090)], fill="#1B568C")
        slash(d, 950)
        brand(d, number)
        headline(d, slot, 165, 111)
        d.text((80, 450), "FULL TIME / KEY MOMENTS", font=font(46), fill=YELLOW)
        panel(d, body, 705, 450)

    footer(d, slot)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination, format="PNG", optimize=True)
    return destination
