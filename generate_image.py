from PIL import Image, ImageDraw, ImageFont
import os
import json
from datetime import datetime, timezone, timedelta


# ==================================================
# 基本設定
# ==================================================

WIDTH = 1200
HEIGHT = 675

OUTPUT_DIR = "generated"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "match_lab.png")

POSTS_FILE = "posts.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

JST = timezone(timedelta(hours=9))


# ==================================================
# STVV LAB COLORS
# ==================================================

NAVY = (5, 32, 58)
NAVY_LIGHT = (12, 52, 88)

YELLOW = (255, 220, 0)
WHITE = (255, 255, 255)

BLUE = (38, 116, 184)
LIGHT_BLUE = (105, 180, 225)

GRAY = (185, 197, 207)
DARK_GRAY = (80, 100, 115)


# ==================================================
# FONT
# ==================================================

def get_font(size, bold=False):

    font_candidates = []

    if bold:
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in font_candidates:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


FONT_SMALL = get_font(24)
FONT_MEDIUM = get_font(32)
FONT_MEDIUM_BOLD = get_font(32, True)
FONT_LARGE = get_font(52, True)
FONT_XL = get_font(70, True)
FONT_NUMBER = get_font(58, True)


# ==================================================
# DRAW HELPERS
# ==================================================

def draw_centered_text(
    draw,
    text,
    y,
    font,
    fill
):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    width = bbox[2] - bbox[0]

    x = (WIDTH - width) // 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill
    )


def draw_header(
    draw,
    category,
    subtitle
):

    draw.rectangle(
        (0, 0, WIDTH, 115),
        fill=WHITE
    )

    draw.rectangle(
        (0, 105, WIDTH, 115),
        fill=YELLOW
    )

    draw.text(
        (55, 27),
        "STVV LAB",
        font=FONT_LARGE,
        fill=NAVY
    )

    bbox = draw.textbbox(
        (0, 0),
        category,
        font=FONT_MEDIUM_BOLD
    )

    category_width = bbox[2] - bbox[0]

    draw.text(
        (
            WIDTH - category_width - 55,
            30
        ),
        category,
        font=FONT_MEDIUM_BOLD,
        fill=BLUE
    )

    draw.text(
        (58, 135),
        subtitle,
        font=FONT_SMALL,
        fill=GRAY
    )


def draw_footer(draw):

    draw.rectangle(
        (0, HEIGHT - 55, WIDTH, HEIGHT),
        fill=(3, 23, 42)
    )

    draw.text(
        (50, HEIGHT - 42),
        "STVV LAB  |  FOOTBALL DATA & ANALYSIS",
        font=FONT_SMALL,
        fill=GRAY
    )

    draw.text(
        (WIDTH - 165, HEIGHT - 42),
        "#STVV",
        font=FONT_SMALL,
        fill=YELLOW
    )


def draw_divider(
    draw,
    y
):

    draw.line(
        (60, y, WIDTH - 60, y),
        fill=DARK_GRAY,
        width=2
    )


# ==================================================
# PLAYER CARD
# ==================================================

def create_player_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "PLAYER DATA",
        "JAPANESE PLAYER CHECK"
    )

    draw.text(
        (70, 220),
        "PLAYER",
        font=FONT_SMALL,
        fill=LIGHT_BLUE
    )

    draw.text(
        (70, 260),
        "PERFORMANCE CHECK",
        font=FONT_LARGE,
        fill=WHITE
    )

    draw_divider(
        draw,
        340
    )

    labels = [
        "ATTACK",
        "CHANCE",
        "DEFENCE",
        "POSITION",
        "IMPACT"
    ]

    start_x = 80

    for i, label in enumerate(labels):

        x = start_x + i * 215

        draw.text(
            (x, 390),
            label,
            font=FONT_SMALL,
            fill=GRAY
        )

        draw.text(
            (x, 440),
            "—",
            font=FONT_NUMBER,
            fill=YELLOW
        )

    draw.text(
        (70, 545),
        "Actual match data will be displayed here.",
        font=FONT_SMALL,
        fill=GRAY
    )

    draw_footer(draw)

    return img


# ==================================================
# COMPARISON CARD
# ==================================================

def create_compare_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "HEAD TO HEAD",
        "STVV vs NEXT OPPONENT"
    )

    draw.text(
        (110, 215),
        "STVV",
        font=FONT_XL,
        fill=WHITE
    )

    draw_centered_text(
        draw,
        "VS",
        225,
        FONT_LARGE,
        YELLOW
    )

    opponent = "OPPONENT"

    bbox = draw.textbbox(
        (0, 0),
        opponent,
        font=FONT_XL
    )

    w = bbox[2] - bbox[0]

    draw.text(
        (WIDTH - w - 110, 215),
        opponent,
        font=FONT_XL,
        fill=WHITE
    )

    draw_divider(
        draw,
        325
    )

    rows = [
        "GOALS",
        "CONCEDED",
        "FORM",
        "HOME / AWAY"
    ]

    y = 370

    for row in rows:

        draw.text(
            (100, y),
            "—",
            font=FONT_MEDIUM_BOLD,
            fill=YELLOW
        )

        draw_centered_text(
            draw,
            row,
            y,
            FONT_MEDIUM,
            GRAY
        )

        draw.text(
            (WIDTH - 130, y),
            "—",
            font=FONT_MEDIUM_BOLD,
            fill=LIGHT_BLUE
        )

        y += 55

    draw_footer(draw)

    return img


# ==================================================
# MATCH DATA CARD
# ==================================================

def create_data_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "MATCH DATA",
        "MATCH STATS"
    )

    draw.text(
        (95, 190),
        "STVV",
        font=FONT_LARGE,
        fill=WHITE
    )

    draw_centered_text(
        draw,
        "MATCH STATS",
        195,
        FONT_MEDIUM_BOLD,
        YELLOW
    )

    opponent = "OPP"

    bbox = draw.textbbox(
        (0, 0),
        opponent,
        font=FONT_LARGE
    )

    w = bbox[2] - bbox[0]

    draw.text(
        (WIDTH - w - 95, 190),
        opponent,
        font=FONT_LARGE,
        fill=WHITE
    )

    draw_divider(
        draw,
        270
    )

    stats = [
        "SHOTS",
        "ON TARGET",
        "POSSESSION",
        "CORNERS"
    ]

    y = 315

    for stat in stats:

        draw.text(
            (105, y),
            "—",
            font=FONT_MEDIUM_BOLD,
            fill=YELLOW
        )

        draw_centered_text(
            draw,
            stat,
            y,
            FONT_MEDIUM,
            GRAY
        )

        draw.text(
            (WIDTH - 135, y),
            "—",
            font=FONT_MEDIUM_BOLD,
            fill=LIGHT_BLUE
        )

        y += 62

    draw.text(
        (70, 565),
        "DATA SOURCE REQUIRED",
        font=FONT_SMALL,
        fill=GRAY
    )

    draw_footer(draw)

    return img


# ==================================================
# ANALYSIS CARD
# ==================================================

def create_analysis_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "TACTICAL LAB",
        "MATCH ANALYSIS"
    )

    draw.text(
        (70, 205),
        "WHY?",
        font=FONT_XL,
        fill=YELLOW
    )

    draw.text(
        (70, 290),
        "WHAT CHANGED THE GAME?",
        font=FONT_LARGE,
        fill=WHITE
    )

    draw_divider(
        draw,
        370
    )

    points = [
        "01  BUILD UP",
        "02  PRESSING",
        "03  TRANSITION"
    ]

    y = 410

    for point in points:

        draw.text(
            (85, y),
            point,
            font=FONT_MEDIUM_BOLD,
            fill=LIGHT_BLUE
        )

        y += 55

    draw_footer(draw)

    return img


# ==================================================
# VOTE CARD
# ==================================================

def create_vote_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "FAN VOTE",
        "STVV SUPPORTERS"
    )

    draw_centered_text(
        draw,
        "YOUR CHOICE?",
        205,
        FONT_XL,
        WHITE
    )

    draw_centered_text(
        draw,
        "TELL US WHAT YOU THINK",
        300,
        FONT_MEDIUM_BOLD,
        YELLOW
    )

    draw_divider(
        draw,
        370
    )

    draw_centered_text(
        draw,
        "JOIN THE DISCUSSION",
        425,
        FONT_LARGE,
        LIGHT_BLUE
    )

    draw_centered_text(
        draw,
        "#STVV",
        510,
        FONT_MEDIUM_BOLD,
        GRAY
    )

    draw_footer(draw)

    return img


# ==================================================
# REVIEW CARD
# ==================================================

def create_review_card():

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        NAVY
    )

    draw = ImageDraw.Draw(img)

    draw_header(
        draw,
        "MATCH REVIEW",
        "AFTER THE FINAL WHISTLE"
    )

    draw.text(
        (70, 200),
        "90 MINUTES",
        font=FONT_XL,
        fill=WHITE
    )

    draw.text(
        (70, 285),
        "WHAT DECIDED THE GAME?",
        font=FONT_LARGE,
        fill=YELLOW
    )

    draw_divider(
        draw,
        365
    )

    sections = [
        ("GOOD", LIGHT_BLUE),
        ("KEY POINT", WHITE),
        ("NEXT", YELLOW)
    ]

    y = 410

    for title, color in sections:

        draw.text(
            (85, y),
            title,
            font=FONT_MEDIUM_BOLD,
            fill=color
        )

        draw.text(
            (330, y),
            "—",
            font=FONT_MEDIUM_BOLD,
            fill=GRAY
        )

        y += 58

    draw_footer(draw)

    return img


# ==================================================
# 投稿時間から画像タイプを決定
# ==================================================

def get_current_post_type():

    now = datetime.now(JST)

    schedule_by_hour = {
        8: "player",
        10: "compare",
        12: "data",
        15: "analysis",
        18: "news",
        21: "vote",
        23: "review",
    }

    return schedule_by_hour.get(
        now.hour,
        "data"
    )


# ==================================================
# IMAGE GENERATOR
# ==================================================

def generate_image(post_type):

    print(
        f"画像タイプ: {post_type}"
    )

    if post_type == "player":

        img = create_player_card()

    elif post_type == "compare":

        img = create_compare_card()

    elif post_type == "data":

        img = create_data_card()

    elif post_type == "analysis":

        img = create_analysis_card()

    elif post_type == "vote":

        img = create_vote_card()

    elif post_type == "review":

        img = create_review_card()

    elif post_type == "news":

        # ニュース枠は一旦
        # MATCH DATA系デザインを使用
        img = create_data_card()

    else:

        img = create_data_card()

    img.save(
        OUTPUT_FILE,
        "PNG"
    )

    print(
        f"画像生成完了: {OUTPUT_FILE}"
    )


# ==================================================
# MAIN
# ==================================================

def main():

    post_type = get_current_post_type()

    generate_image(
        post_type
    )


if __name__ == "__main__":
    main()
