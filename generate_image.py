from PIL import Image, ImageDraw, ImageFont
import os

WIDTH = 1200
HEIGHT = 675

OUTPUT_DIR = "generated"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "match_lab.png")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# STVV LAB colors
NAVY = (5, 32, 58)
YELLOW = (255, 220, 0)
WHITE = (255, 255, 255)

img = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
draw = ImageDraw.Draw(img)

# Header
draw.rectangle((0, 0, WIDTH, 130), fill=WHITE)
draw.rectangle((0, 120, WIDTH, 130), fill=YELLOW)

# Accent
draw.rectangle((0, 130, 28, HEIGHT), fill=YELLOW)

# Fonts
try:
    title_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        76
    )
    subtitle_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        32
    )
    body_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        28
    )
except:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    body_font = ImageFont.load_default()

# Branding
draw.text(
    (55, 20),
    "MATCH LAB",
    font=title_font,
    fill=NAVY
)

draw.text(
    (720, 50),
    "NEXT OPPONENT",
    font=subtitle_font,
    fill=NAVY
)

# Main
draw.text(
    (70, 185),
    "STVV LAB",
    font=subtitle_font,
    fill=YELLOW
)

draw.text(
    (70, 250),
    "NEXT OPPONENT ANALYSIS",
    font=title_font,
    fill=WHITE
)

# Analysis points
points = [
    "1  DEFENSIVE STRUCTURE",
    "2  BUILD-UP PRESSURE",
    "3  KEY MATCHUP"
]

y = 400

for point in points:
    draw.text(
        (90, y),
        point,
        font=subtitle_font,
        fill=WHITE
    )
    y += 70

# Footer
draw.rectangle(
    (0, HEIGHT - 60, WIDTH, HEIGHT),
    fill=YELLOW
)

draw.text(
    (45, HEIGHT - 48),
    "STVV LAB | MATCH ANALYSIS",
    font=body_font,
    fill=NAVY
)

img.save(OUTPUT_FILE)

print(f"Generated: {OUTPUT_FILE}")
