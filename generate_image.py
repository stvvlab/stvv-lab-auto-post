
import os
from datetime import datetime, timezone, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont


# ==========================================
# STVV LAB 設定
# ==========================================

API_BASE = "https://www.thesportsdb.com/api/v1/json/123"
STVV_ID = "135461"

OUTPUT_PATH = "generated/match_lab.png"

WIDTH = 1200
HEIGHT = 675
JST = timezone(timedelta(hours=9))

NAVY = (9, 29, 58)
DARK = (5, 18, 38)
BLUE = (26, 89, 166)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
LIGHT = (225, 233, 242)
GRAY = (150, 165, 180)


def font(size, bold=True):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    return ImageFont.truetype(path, size)


def api_get(endpoint, params):
    response = requests.get(
        f"{API_BASE}/{endpoint}",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("API response is invalid")
    return data


# ==========================================
# STVV最新試合取得
# ==========================================

def get_latest_match():
    data = api_get(
        "eventslast.php",
        {"id": STVV_ID},
    )

    events = data.get("results") or []
    today = datetime.now(JST).date()
    candidates = []

    for event in events:
        if STVV_ID not in {
            str(event.get("idHomeTeam")),
            str(event.get("idAwayTeam")),
        }:
            continue

        if event.get("strStatus") not in (
            "FT", "AET", "PEN"
        ):
            continue

        if (
            event.get("intHomeScore") is None
            or event.get("intAwayScore") is None
        ):
            continue

        try:
            match_date = datetime.strptime(
                event["dateEvent"], "%Y-%m-%d"
            ).date()
        except (KeyError, TypeError, ValueError):
            continue

        days_old = (today - match_date).days

        if 0 <= days_old <= 30:
            candidates.append((match_date, event))

    if not candidates:
        raise RuntimeError(
            "直近30日以内の終了済みSTVV試合がありません"
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


# ==========================================
# 試合スタッツ
# ==========================================

def get_stats(event_id):
    if not event_id:
        return {}

    try:
        data = api_get(
            "lookupeventstats.php",
            {"id": event_id},
        )
    except (requests.RequestException, ValueError) as error:
        print(f"スタッツ取得失敗: {error}")
        return {}

    rows = (
        data.get("eventstats")
        or data.get("statistics")
        or []
    )

    result = {}

    for row in rows:
        name = (
            row.get("strStat")
            or row.get("strStatistic")
            or ""
        ).strip().lower()

        if not name:
            continue

        home = row.get("intHome")
        away = row.get("intAway")

        if home is None:
            home = row.get("strHome")
        if away is None:
            away = row.get("strAway")

        result[name] = (home, away)

    return result


def find_stat(stats, aliases, index):
    for alias in aliases:
        pair = stats.get(alias.lower())
        if pair and pair[index] is not None:
            return str(pair[index])
    return "—"


# ==========================================
# 画像描画
# ==========================================

def center_text(draw, x, y, text, size, color):
    text = str(text)
    current_font = font(size)

    while size > 15:
        box = draw.textbbox(
            (0, 0), text, font=current_font
        )
        if box[2] - box[0] <= 470:
            break
        size -= 2
        current_font = font(size)

    box = draw.textbbox(
        (0, 0), text, font=current_font
    )

    width = box[2] - box[0]

    draw.text(
        (x - width / 2, y),
        text,
        font=current_font,
        fill=color,
    )


def create_image(event, stats):
    home = str(event["idHomeTeam"]) == STVV_ID

    opponent = (
        event["strAwayTeam"]
        if home
        else event["strHomeTeam"]
    )

    stvv_score = (
        event["intHomeScore"]
        if home
        else event["intAwayScore"]
    )

    opponent_score = (
        event["intAwayScore"]
        if home
        else event["intHomeScore"]
    )

    stvv_index = 0 if home else 1
    opponent_index = 1 - stvv_index

    image = Image.new(
        "RGB", (WIDTH, HEIGHT), NAVY
    )
    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (0, 0, WIDTH, 16), fill=YELLOW
    )

    draw.text(
        (55, 40),
        "STVV LAB",
        font=font(48),
        fill=WHITE,
    )

    draw.text(
        (55, 105),
        "MATCH DATA",
        font=font(28),
        fill=YELLOW,
    )

    match_date = event["dateEvent"].replace("-", ".")
    location = "HOME" if home else "AWAY"

    draw.text(
        (830, 60),
        f"{match_date}  {location}",
        font=font(22, False),
        fill=LIGHT,
    )

    center_text(
        draw, 270, 175,
        "SINT-TRUIDEN", 34, WHITE
    )

    center_text(
        draw, 930, 175,
        opponent.upper(), 34, WHITE
    )

    center_text(
        draw, 270, 225,
        stvv_score, 76, YELLOW
    )

    center_text(
        draw, 600, 245,
        "-", 76, WHITE
    )

    center_text(
        draw, 930, 225,
        opponent_score, 76, WHITE
    )

    draw.line(
        (55, 340, 1145, 340),
        fill=BLUE,
        width=3,
    )

    definitions = [
        (
            "SHOTS",
            ["total shots", "shots", "total attempts"],
        ),
        (
            "ON TARGET",
            ["shots on goal", "shots on target"],
        ),
        (
            "POSSESSION",
            ["ball possession", "possession"],
        ),
        (
            "CORNERS",
            ["corner kicks", "corners"],
        ),
    ]

    y = 375

    for label, aliases in definitions:
        stvv_value = find_stat(
            stats, aliases, stvv_index
        )
        other_value = find_stat(
            stats, aliases, opponent_index
        )

        center_text(
            draw, 270, y,
            stvv_value, 38, YELLOW
        )

        center_text(
            draw, 600, y + 5,
            label, 30, LIGHT
        )

        center_text(
            draw, 930, y,
            other_value, 38, WHITE
        )

        y += 65

    draw.rectangle(
        (0, HEIGHT - 42, WIDTH, HEIGHT),
        fill=DARK,
    )

    draw.text(
        (55, HEIGHT - 34),
        "DATA: TheSportsDB",
        font=font(22, False),
        fill=GRAY,
    )

    return image


# ==========================================
# メイン処理
# ==========================================

def main():
    print("STVV LAB 画像生成開始")

    try:
        event = get_latest_match()

        print(
            "対象試合:",
            event.get("dateEvent"),
            event.get("strEvent"),
        )

        stats = get_stats(event.get("idEvent"))
        image = create_image(event, stats)

        os.makedirs("generated", exist_ok=True)

        temporary_path = OUTPUT_PATH + ".tmp.png"
        image.save(temporary_path, "PNG")

        os.replace(temporary_path, OUTPUT_PATH)

        print(f"画像生成成功: {OUTPUT_PATH}")

    except Exception as error:
        print(f"画像生成を中止: {error}")
        print("既存の画像は上書きしません")
        raise


if __name__ == "__main__":
    main()
