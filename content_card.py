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


def story_parts(message):
    """Use real supplied text as the headline; never fabricate a score or stat."""
    body = clean(message)
    parts = [p.strip() for p in body.splitlines() if p.strip()]
    if not parts:
        return "STVV LAB", ""
    first = re.sub(r"^[^\w一-龥ぁ-んァ-ン]+", "", parts[0]).strip()
    if len(parts) > 1:
        return first[:80], "\n".join(parts[1:])
    # Split one-line analysis at the first natural sentence boundary.
    m = re.search(r"[。！？!?]", first)
    if m and 12 <= m.end() <= 65 and len(first) > m.end():
        return first[:m.end()], first[m.end():].strip()
    return first, ""


def atmosphere(draw, slot):
    """Layered stadium-light atmosphere without pretending to show real players."""
    from PIL import ImageFilter
    palette = {
        "player": ("#0C3764", "#03111F"),
        "compare": ("#173F78", "#091328"),
        "data": ("#083C54", "#041526"),
        "analysis": ("#06443D", "#041923"),
        "news": ("#173C70", "#060D20"),
        "vote": ("#3D2E66", "#07152D"),
        "recap": ("#4C304A", "#081426"),
    }
    top, bottom = palette[slot]
    def rgb(value):
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    a, b = rgb(top), rgb(bottom)
    for y in range(H):
        t = y / H
        draw.line((0, y, W, y), fill=tuple(int(a[k]*(1-t)+b[k]*t) for k in range(3)))
    # Perspective floodlights and distant stands.
    for x in (-180, 280, 820, 1290):
        draw.polygon([(x-190, 0), (x+190, 0), (W//2+130, 950), (W//2-130, 950)],
                     fill="#15304A")
    for row in range(10):
        y = 670 + row*46
        draw.line((0, y, W, y+row*5), fill="#23415B", width=2)
    for j in range(100):
        x = (j*317+49) % W
        y = 630 + (j*149) % 510
        draw.ellipse((x, y, x+3, y+3), fill="#5A7182")
    for x in (95, 975):
        for j in range(6):
            draw.ellipse((x-8, 60+j*28, x+8, 76+j*28), fill="#E2E8DD")
    draw.polygon([(0, 1020), (W, 800), (W, 890), (0, 1110)], fill="#FFE000")


def editorial_header(draw, slot, index):
    draw.rectangle((0, 0, W, 15), fill=YELLOW)
    draw.text((58, 40), "STVV / LAB", font=font(45), fill=WHITE)
    draw.text((795, 52), "FOOTBALL MEDIA", font=font(21), fill=YELLOW)
    draw.line((58, 113, 1022, 113), fill="#69859D", width=2)
    draw.text((60, 145), LABELS[slot][0] + "  /  " + LABELS[slot][1],
              font=font(35), fill=YELLOW)
    draw.text((950, 149), f"0{index}", font=font(34), fill=WHITE)


def render_content_card(slot, message, destination):
    if slot not in LABELS:
        raise ValueError("Unknown slot")
    headline_text, detail = story_parts(message)
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    atmosphere(d, slot)
    index = list(LABELS).index(slot) + 1
    editorial_header(d, slot, index)

    # Distinct editorial structure per category, all driven by verified text.
    if slot == "compare":
        d.polygon([(0, 305), (510, 260), (510, 770), (0, 860)], fill="#0B447D")
        d.polygon([(570, 260), (1080, 305), (1080, 860), (570, 770)], fill="#192C4B")
        d.text((440, 430), "VS", font=font(112), fill=YELLOW)
        title_y, title_h, detail_y = 850, 270, 1120
    elif slot == "data":
        # Grid and measured-looking graphics are intentionally omitted unless
        # actual numeric data are parsed; typography carries the story.
        for i in range(7):
            d.line((70+i*145, 360, 70+i*145, 860), fill="#20516B", width=2)
        d.text((62, 355), "NUMBERS / CONTEXT", font=font(42), fill=YELLOW)
        title_y, title_h, detail_y = 560, 380, 965
    elif slot == "analysis":
        d.rounded_rectangle((60, 320, 1020, 735), radius=12, outline="#B2D8D2", width=5)
        d.line((540, 320, 540, 735), fill="#B2D8D2", width=3)
        d.ellipse((460, 445, 620, 605), outline="#B2D8D2", width=3)
        d.text((77, 340), "TACTICAL BOARD / CONCEPT", font=font(28), fill=YELLOW)
        title_y, title_h, detail_y = 770, 340, 1120
    elif slot == "player":
        d.ellipse((660, 295, 1120, 755), outline="#306C9C", width=35)
        d.text((710, 390), "STVV", font=font(78), fill="#88A8C6")
        title_y, title_h, detail_y = 660, 420, 1100
    elif slot == "news":
        d.rectangle((55, 290, 425, 370), fill=YELLOW)
        d.text((76, 300), "OFFICIAL / NEWS", font=font(36), fill=INK)
        title_y, title_h, detail_y = 425, 600, 1060
    elif slot == "vote":
        d.text((55, 315), "YOUR CALL.", font=font(92), fill=YELLOW)
        title_y, title_h, detail_y = 485, 530, 1035
    else:
        d.rectangle((0, 315, W, 440), fill="#133F6D")
        d.text((65, 326), "MATCHDAY / REVIEW", font=font(59), fill=YELLOW)
        title_y, title_h, detail_y = 515, 515, 1050

    # Dark translucent-style plate gives the actual headline priority.
    d.rounded_rectangle((42, title_y-15, 1038, min(1160, title_y+title_h)),
                        radius=18, fill="#061425")
    d.rectangle((42, title_y-15, 56, min(1160, title_y+title_h)), fill=YELLOW)
    title_size = 70 if slot not in {"news", "recap"} else 76
    write(d, headline_text, 83, title_y+18, 925, title_h-42, color=WHITE, size=title_size)
    if detail and detail_y < 1190:
        write(d, detail, 79, detail_y, 915, 1185-detail_y,
              color=MUTED, size=35)
    d.rectangle((0, 1200, W, H), fill=INK)
    d.line((56, 1220, 1020, 1220), fill=YELLOW, width=5)
    d.text((60, 1248), "STVV LAB  /  FACTS FIRST", font=font(32), fill=WHITE)
    d.text((940, 1254), slot.upper(), font=font(19), fill=YELLOW)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination, format="PNG", optimize=True)
    return destination
