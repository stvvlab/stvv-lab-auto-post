"""Rights-safe portrait-free editorial image for the STVV LAB player slot.

No scraped photos, human faces, fake kits, badges, or unverified statistics.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path("generated/player_lab.png")
W, H = 1080, 1350
NAVY = "#06172C"
DARK = "#04101F"
YELLOW = "#FFD400"
WHITE = "#F7FAFF"
BLUE = "#174A83"
MUTED = "#B5C5D8"


def font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(name, size)


def render(destination=OUTPUT):
    image = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(image)
    # Layered graphic system. No player likeness is created.
    draw.polygon([(550, 0), (1080, 0), (1080, 920), (825, 1020), (355, 620)], fill=BLUE)
    draw.polygon([(750, 0), (1080, 0), (1080, 480)], fill="#0B3059")
    for i in range(15):
        x = 390 + i * 48
        draw.line((x, 185, x - 340, 980), fill="#17406B", width=2)
    draw.ellipse((470, 320, 1250, 1100), outline=YELLOW, width=11)
    draw.ellipse((550, 400, 1170, 1020), outline="#4475A7", width=4)

    draw.rectangle((0, 0, W, 17), fill=YELLOW)
    draw.text((60, 68), "STVV LAB", font=font(54), fill=WHITE)
    draw.text((61, 152), "INDEPENDENT FOOTBALL ANALYSIS", font=font(22, False), fill=MUTED)
    draw.rounded_rectangle((58, 260, 382, 332), radius=8, fill=YELLOW)
    draw.text((80, 275), "PLAYER LAB", font=font(39), fill=DARK)
    draw.text((50, 390), "JAPANESE", font=font(91), fill=WHITE)
    draw.text((50, 497), "PLAYERS", font=font(122), fill=YELLOW)

    # A large abstract number-like stripe motif, intentionally not a shirt number.
    draw.polygon([(740, 590), (928, 610), (722, 1070), (536, 1050)], fill=YELLOW)
    draw.polygon([(850, 760), (1030, 775), (900, 1070), (732, 1070)], fill=WHITE)

    draw.rectangle((0, 1100, W, H), fill=DARK)
    draw.text((58, 1135), "MOVEMENT  /  PRESSING  /  DECISIONS", font=font(31), fill=WHITE)
    draw.line((58, 1205, 1022, 1205), fill=BLUE, width=4)
    draw.text((58, 1243), "STVV LAB   |   PLAYER ANALYSIS", font=font(25), fill=YELLOW)
    draw.text((930, 1245), "01", font=font(36), fill=MUTED)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination


if __name__ == "__main__":
    print(f"Generated {render()}")
