import os
from datetime import datetime, timezone, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont


# ==================================================
# 基本設定
# ==================================================

API_BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

STVV_TEAM_ID = "135461"
BELGIUM_LEAGUE_ID = "4338"

OUTPUT_DIR = "generated"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "match_lab.png")

WIDTH = 1200
HEIGHT = 675

JST = timezone(timedelta(hours=9))


# ==================================================
# カラー
# ==================================================

NAVY = (9, 29, 58)
DARK_NAVY = (5, 18, 38)
BLUE = (26, 89, 166)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
LIGHT = (225, 233, 242)
GRAY = (150, 165, 180)


# ==================================================
# フォント
# ==================================================

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]

REGULAR_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]


def load_font(size, bold=True):

    candidates = (
        FONT_CANDIDATES
        if bold
        else REGULAR_FONT_CANDIDATES
    )

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


FONT_TITLE = load_font(48)
FONT_SUBTITLE = load_font(28)
FONT_TEAM = load_font(34)
FONT_SCORE = load_font(76)
FONT_STAT = load_font(30)
FONT_VALUE = load_font(38)
FONT_SMALL = load_font(22, bold=False)


# ==================================================
# TheSportsDB API
# ==================================================

def api_get(endpoint, params=None):

    url = f"{API_BASE_URL}/{endpoint}"

    print(f"TheSportsDB取得: {endpoint}")

    response = requests.get(
        url,
        params=params or {},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise RuntimeError(
            "TheSportsDBから正常なJSONを取得できませんでした。"
        )

    return data


# ==================================================
# シーズン判定
# ==================================================

def get_current_season():

    now = datetime.now(JST)

    if now.month >= 7:
        return f"{now.year}-{now.year + 1}"

    return f"{now.year - 1}-{now.year}"


# ==================================================
# STVVの直近終了試合
# ==================================================

def get_latest_finished_fixture():

    season = get_current_season()

    print(f"対象シーズン: {season}")

    data = api_get(
        "eventsseason.php",
        {
            "id": BELGIUM_LEAGUE_ID,
            "s": season
        }
    )

    events = data.get("events") or []

    if not events:
        raise RuntimeError(
            f"{season} のベルギーリーグ試合データを取得できませんでした。"
        )

    stvv_events = []

    for event in events:

        home_id = str(
            event.get("idHomeTeam") or ""
        )

        away_id = str(
            event.get("idAwayTeam") or ""
        )

        if STVV_TEAM_ID not in {
            home_id,
            away_id
        }:
            continue

        home_score = event.get("intHomeScore")
        away_score = event.get("intAwayScore")

        # スコアが両方存在する試合＝終了済みとして扱う
        if home_score is None or away_score is None:
            continue

        date_text = event.get("dateEvent") or ""

        time_text = (
            event.get("strTime")
            or "00:00:00"
        )

        try:
            event_datetime = datetime.fromisoformat(
                f"{date_text}T{time_text}"
            )
        except Exception:
            event_datetime = datetime.min

        stvv_events.append(
            (
                event_datetime,
                event
            )
        )

    if not stvv_events:
        raise RuntimeError(
            "STVVの終了済み試合を取得できませんでした。"
        )

    stvv_events.sort(
        key=lambda x: x[0],
        reverse=True
    )

    latest = stvv_events[0][1]

    print(
        "直近試合取得成功: "
        f"{latest.get('strHomeTeam')} "
        f"{latest.get('intHomeScore')}"
        "-"
        f"{latest.get('intAwayScore')} "
        f"{latest.get('strAwayTeam')}"
    )

    return latest


# ==================================================
# 試合スタッツ
# ==================================================

def get_event_statistics(event_id):

    if not event_id:
        return {}

    try:

        data = api_get(
            "lookupeventstats.php",
            {
                "id": event_id
            }
        )

    except Exception as e:

        print(
            f"試合スタッツ取得失敗: {e}"
        )

        return {}

    raw_stats = (
        data.get("eventstats")
        or data.get("statistics")
        or data.get("stats")
        or []
    )

    result = {}

    if not isinstance(raw_stats, list):
        return result

    for stat in raw_stats:

        if not isinstance(stat, dict):
            continue

        stat_name = (
            stat.get("strStat")
            or stat.get("strStatistic")
            or stat.get("type")
            or stat.get("strType")
        )

        if not stat_name:
            continue

        home_value = (
            stat.get("intHome")
            if stat.get("intHome") is not None
            else stat.get("strHome")
        )

        away_value = (
            stat.get("intAway")
            if stat.get("intAway") is not None
            else stat.get("strAway")
        )

        result[
            str(stat_name).strip().lower()
        ] = {
            "home": home_value,
            "away": away_value
        }

    return result


def find_stat(stats, names, side):

    for name in names:

        key = name.lower()

        if key in stats:

            value = stats[key].get(side)

            if value is not None:
                return value

    return None


# ==================================================
# 表示用データ
# ==================================================

def clean_value(value):

    if value is None:
        return "—"

    value = str(value).strip()

    if not value:
        return "—"

    return value


def build_match_data(event, statistics):

    home_id = str(
        event.get("idHomeTeam") or ""
    )

    away_id = str(
        event.get("idAwayTeam") or ""
    )

    home_name = (
        event.get("strHomeTeam")
        or "HOME"
    )

    away_name = (
        event.get("strAwayTeam")
        or "AWAY"
    )

    home_score = event.get("intHomeScore")
    away_score = event.get("intAwayScore")

    if home_id == STVV_TEAM_ID:

        stvv_name = home_name
        opponent_name = away_name

        stvv_score = home_score
        opponent_score = away_score

        stvv_side = "home"
        opponent_side = "away"

        venue = "HOME"

    elif away_id == STVV_TEAM_ID:

        stvv_name = away_name
        opponent_name = home_name

        stvv_score = away_score
        opponent_score = home_score

        stvv_side = "away"
        opponent_side = "home"

        venue = "AWAY"

    else:

        raise RuntimeError(
            "取得した試合にSTVVが含まれていません。"
        )

    date_raw = (
        event.get("dateEvent")
        or ""
    )

    try:

        match_date = datetime.strptime(
            date_raw,
            "%Y-%m-%d"
        ).strftime(
            "%Y.%m.%d"
        )

    except Exception:

        match_date = date_raw

    stat_definitions = [
        (
            "SHOTS",
            [
                "Total Shots",
                "Shots",
                "Total attempts"
            ]
        ),
        (
            "ON TARGET",
            [
                "Shots on Goal",
                "Shots on Target",
                "On Target"
            ]
        ),
        (
            "POSSESSION",
            [
                "Ball Possession",
                "Possession"
            ]
        ),
        (
            "CORNERS",
            [
                "Corner Kicks",
                "Corners"
            ]
        ),
    ]

    display_stats = []

    for label, names in stat_definitions:

        stvv_value = find_stat(
            statistics,
            names,
            stvv_side
        )

        opponent_value = find_stat(
            statistics,
            names,
            opponent_side
        )

        display_stats.append(
            (
                label,
                clean_value(stvv_value),
                clean_value(opponent_value)
            )
        )

    return {
        "stvv_name": stvv_name,
        "opponent_name": opponent_name,
        "stvv_score": clean_value(stvv_score),
        "opponent_score": clean_value(
            opponent_score
        ),
        "date": match_date,
        "venue": venue,
        "stats": display_stats
    }


# ==================================================
# 描画ヘルパー
# ==================================================

def text_center(
    draw,
    xy,
    text,
    font,
    fill
):

    x, y = xy

    text = str(text)

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    width = (
        bbox[2]
        - bbox[0]
    )

    draw.text(
        (
            x - width / 2,
            y
        ),
        text,
        font=font,
        fill=fill
    )


def shorten_team_name(
    name,
    max_length=20
):

    if not name:
        return "UNKNOWN"

    if len(name) <= max_length:
        return name.upper()

    return (
        name[:max_length - 1].upper()
        + "…"
    )


# ==================================================
# 実データ画像
# ==================================================

def create_match_data_card(match_data):

    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        NAVY
    )

    draw = ImageDraw.Draw(image)

    # 上部アクセント
    draw.rectangle(
        (
            0,
            0,
            WIDTH,
            16
        ),
        fill=YELLOW
    )

    # タイトル
    draw.text(
        (
            55,
            40
        ),
        "STVV LAB",
        font=FONT_TITLE,
        fill=WHITE
    )

    draw.text(
        (
            55,
            102
        ),
        "MATCH DATA",
        font=FONT_SUBTITLE,
        fill=YELLOW
    )

    # 日付・HOME/AWAY
    info_text = (
        f"{match_data['date']}  "
        f"{match_data['venue']}"
    )

    draw.text(
        (
            900,
            60
        ),
        info_text,
        font=FONT_SMALL,
        fill=LIGHT
    )

    # チーム
    stvv_name = shorten_team_name(
        match_data["stvv_name"]
    )

    opponent_name = shorten_team_name(
        match_data["opponent_name"]
    )

    text_center(
        draw,
        (
            270,
            175
        ),
        stvv_name,
        FONT_TEAM,
        WHITE
    )

    text_center(
        draw,
        (
            930,
            175
        ),
        opponent_name,
        FONT_TEAM,
        WHITE
    )

    # スコア
    text_center(
        draw,
        (
            270,
            225
        ),
        match_data["stvv_score"],
        FONT_SCORE,
        YELLOW
    )

    text_center(
        draw,
        (
            600,
            245
        ),
        "-",
        FONT_SCORE,
        WHITE
    )

    text_center(
        draw,
        (
            930,
            225
        ),
        match_data["opponent_score"],
        FONT_SCORE,
        WHITE
    )

    # 区切り
    draw.line(
        (
            55,
            340,
            1145,
            340
        ),
        fill=BLUE,
        width=3
    )

    # 統計
    y = 375

    for (
        label,
        stvv_value,
        opponent_value
    ) in match_data["stats"]:

        text_center(
            draw,
            (
                270,
                y
            ),
            stvv_value,
            FONT_VALUE,
            YELLOW
        )

        text_center(
            draw,
            (
                600,
                y + 5
            ),
            label,
            FONT_STAT,
            LIGHT
        )

        text_center(
            draw,
            (
                930,
                y
            ),
            opponent_value,
            FONT_VALUE,
            WHITE
        )

        y += 65

    # フッター
    draw.rectangle(
        (
            0,
            HEIGHT - 42,
            WIDTH,
            HEIGHT
        ),
        fill=DARK_NAVY
    )

    draw.text(
        (
            55,
            HEIGHT - 34
        ),
        "DATA: TheSportsDB",
        font=FONT_SMALL,
        fill=GRAY
    )

    return image


# ==================================================
# エラー時画像
# ==================================================

def create_error_card(message):

    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        NAVY
    )

    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (
            0,
            0,
            WIDTH,
            16
        ),
        fill=YELLOW
    )

    draw.text(
        (
            55,
            50
        ),
        "STVV LAB",
        font=FONT_TITLE,
        fill=WHITE
    )

    draw.text(
        (
            55,
            120
        ),
        "MATCH DATA",
        font=FONT_SUBTITLE,
        fill=YELLOW
    )

    draw.text(
        (
            55,
            260
        ),
        "DATA NOT AVAILABLE",
        font=FONT_TITLE,
        fill=WHITE
    )

    draw.text(
        (
            55,
            340
        ),
        str(message)[:70],
        font=FONT_SMALL,
        fill=LIGHT
    )

    return image


# ==================================================
# MAIN
# ==================================================

def main():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    try:

        print("")
        print("========== STVV LAB ==========")
        print("DATA SOURCE: TheSportsDB")
        print("==============================")
        print("")

        fixture = get_latest_finished_fixture()

        event_id = fixture.get("idEvent")

        print(
            f"Event ID: {event_id}"
        )

        statistics = get_event_statistics(
            event_id
        )

        match_data = build_match_data(
            fixture,
            statistics
        )

        print("")
        print("========== 取得データ ==========")

        print(
            f"STVV: {match_data['stvv_name']}"
        )

        print(
            f"対戦相手: "
            f"{match_data['opponent_name']}"
        )

        print(
            f"スコア: "
            f"{match_data['stvv_score']}"
            "-"
            f"{match_data['opponent_score']}"
        )

        print(
            f"会場: {match_data['venue']}"
        )

        for (
            label,
            stvv_value,
            opponent_value
        ) in match_data["stats"]:

            print(
                f"{label}: "
                f"{stvv_value} / "
                f"{opponent_value}"
            )

        print("==============================")
        print("")

        image = create_match_data_card(
            match_data
        )

        image.save(
            OUTPUT_PATH,
            "PNG"
        )

        print(
            f"画像生成成功: {OUTPUT_PATH}"
        )

    except Exception as e:

        print(
            f"実データ取得エラー: {e}"
        )

        image = create_error_card(
            str(e)
        )

        image.save(
            OUTPUT_PATH,
            "PNG"
        )

        print(
            "エラー表示画像を生成しました。"
        )

        raise


if __name__ == "__main__":
    main()
