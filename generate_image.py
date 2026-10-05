import os
from datetime import datetime, timezone, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont


# ==================================================
# 基本設定
# ==================================================

API_BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.environ.get("API_FOOTBALL_KEY", "")

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
FONT_BADGE = load_font(24)


# ==================================================
# API共通
# ==================================================

def api_get(endpoint, params=None):

    if not API_KEY:
        raise RuntimeError(
            "API_FOOTBALL_KEY が設定されていません。"
        )

    url = f"{API_BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers={
            "x-apisports-key": API_KEY
        },
        params=params or {},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    errors = data.get("errors")

    if errors:
        raise RuntimeError(
            f"API-FOOTBALL error: {errors}"
        )

    remaining = response.headers.get(
        "x-ratelimit-requests-remaining"
    )

    if remaining is not None:
        print(
            f"API残りリクエスト数: {remaining}"
        )

    return data.get("response", [])


# ==================================================
# STVV検索
# ==================================================

def find_stvv():

    print("STVVを検索します。")

    teams = api_get(
        "teams",
        {
            "search": "Sint-Truidense"
        }
    )

    if not teams:

        # 表記揺れ対策
        teams = api_get(
            "teams",
            {
                "search": "Truiden"
            }
        )

    if not teams:
        raise RuntimeError(
            "STVVをAPI上で見つけられませんでした。"
        )

    # Belgiumのクラブを優先
    selected = None

    for item in teams:

        team = item.get("team", {})

        name = team.get("name", "")
        country = team.get("country", "")

        if (
            country == "Belgium"
            and (
                "Truiden" in name
                or "Truidense" in name
            )
        ):
            selected = team
            break

    if selected is None:
        selected = teams[0].get("team", {})

    team_id = selected.get("id")
    team_name = selected.get("name")

    if not team_id:
        raise RuntimeError(
            "STVVのTeam IDを取得できませんでした。"
        )

    print(
        f"STVV取得成功: {team_name} "
        f"(Team ID: {team_id})"
    )

    return team_id, team_name


# ==================================================
# 直近終了試合
# ==================================================

def get_latest_finished_fixture(team_id):

    print("STVVの直近試合を取得します。")

    fixtures = api_get(
        "fixtures",
        {
            "team": team_id,
            "last": 10,
            "timezone": "Asia/Tokyo"
        }
    )

    if not fixtures:
        raise RuntimeError(
            "STVVの試合を取得できませんでした。"
        )

    finished_statuses = {
        "FT",
        "AET",
        "PEN"
    }

    finished = []

    for item in fixtures:

        fixture = item.get(
            "fixture",
            {}
        )

        status = fixture.get(
            "status",
            {}
        ).get("short")

        if status in finished_statuses:
            finished.append(item)

    if not finished:
        raise RuntimeError(
            "終了済みの直近試合がありません。"
        )

    # APIの返却順に依存せず日時で判定
    finished.sort(
        key=lambda x: x.get(
            "fixture",
            {}
        ).get(
            "timestamp",
            0
        ),
        reverse=True
    )

    latest = finished[0]

    fixture_id = latest[
        "fixture"
    ]["id"]

    print(
        f"直近試合 Fixture ID: {fixture_id}"
    )

    return latest


# ==================================================
# 試合統計
# ==================================================

def get_fixture_statistics(fixture_id):

    print(
        f"Fixture {fixture_id} の"
        "試合統計を取得します。"
    )

    statistics = api_get(
        "fixtures/statistics",
        {
            "fixture": fixture_id
        }
    )

    return statistics


def statistics_to_dict(statistics):

    result = {}

    for side in statistics:

        team = side.get(
            "team",
            {}
        )

        team_id = team.get("id")

        stat_dict = {}

        for stat in side.get(
            "statistics",
            []
        ):

            stat_type = stat.get("type")
            value = stat.get("value")

            stat_dict[stat_type] = value

        result[team_id] = stat_dict

    return result


# ==================================================
# 表示用データ作成
# ==================================================

def clean_value(value):

    if value is None:
        return "—"

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return "—"

    return str(value)


def build_match_data(
    fixture,
    statistics,
    stvv_id
):

    teams = fixture.get(
        "teams",
        {}
    )

    goals = fixture.get(
        "goals",
        {}
    )

    fixture_info = fixture.get(
        "fixture",
        {}
    )

    home = teams.get(
        "home",
        {}
    )

    away = teams.get(
        "away",
        {}
    )

    home_id = home.get("id")
    away_id = away.get("id")

    stats = statistics_to_dict(
        statistics
    )

    home_stats = stats.get(
        home_id,
        {}
    )

    away_stats = stats.get(
        away_id,
        {}
    )

    if stvv_id == home_id:

        stvv_name = home.get(
            "name",
            "STVV"
        )

        opponent_name = away.get(
            "name",
            "OPPONENT"
        )

        stvv_score = goals.get(
            "home"
        )

        opponent_score = goals.get(
            "away"
        )

        stvv_stats = home_stats
        opponent_stats = away_stats

        venue = "HOME"

    else:

        stvv_name = away.get(
            "name",
            "STVV"
        )

        opponent_name = home.get(
            "name",
            "OPPONENT"
        )

        stvv_score = goals.get(
            "away"
        )

        opponent_score = goals.get(
            "home"
        )

        stvv_stats = away_stats
        opponent_stats = home_stats

        venue = "AWAY"

    date_raw = fixture_info.get(
        "date",
        ""
    )

    try:

        match_date = datetime.fromisoformat(
            date_raw
        ).astimezone(
            JST
        ).strftime(
            "%Y.%m.%d"
        )

    except Exception:

        match_date = date_raw[:10]

    return {
        "stvv_name": stvv_name,
        "opponent_name": opponent_name,
        "stvv_score": clean_value(
            stvv_score
        ),
        "opponent_score": clean_value(
            opponent_score
        ),
        "date": match_date,
        "venue": venue,

        "stats": [
            (
                "SHOTS",
                clean_value(
                    stvv_stats.get(
                        "Total Shots"
                    )
                ),
                clean_value(
                    opponent_stats.get(
                        "Total Shots"
                    )
                )
            ),
            (
                "ON TARGET",
                clean_value(
                    stvv_stats.get(
                        "Shots on Goal"
                    )
                ),
                clean_value(
                    opponent_stats.get(
                        "Shots on Goal"
                    )
                )
            ),
            (
                "POSSESSION",
                clean_value(
                    stvv_stats.get(
                        "Ball Possession"
                    )
                ),
                clean_value(
                    opponent_stats.get(
                        "Ball Possession"
                    )
                )
            ),
            (
                "CORNERS",
                clean_value(
                    stvv_stats.get(
                        "Corner Kicks"
                    )
                ),
                clean_value(
                    opponent_stats.get(
                        "Corner Kicks"
                    )
                )
            ),
        ]
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
        name[:max_length - 1]
        .upper()
        + "…"
    )


# ==================================================
# 実データ画像
# ==================================================

def create_match_data_card(
    match_data
):

    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        NAVY
    )

    draw = ImageDraw.Draw(
        image
    )

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
        match_data[
            "stvv_name"
        ]
    )

    opponent_name = shorten_team_name(
        match_data[
            "opponent_name"
        ]
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
        match_data[
            "stvv_score"
        ],
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
        match_data[
            "opponent_score"
        ],
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
        "DATA: API-FOOTBALL",
        font=FONT_SMALL,
        fill=GRAY
    )

    return image


# ==================================================
# エラー時画像
# ==================================================

def create_error_card(
    message
):

    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        NAVY
    )

    draw = ImageDraw.Draw(
        image
    )

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
        message[:70],
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

        stvv_id, stvv_name = find_stvv()

        fixture = get_latest_finished_fixture(
            stvv_id
        )

        fixture_id = fixture[
            "fixture"
        ]["id"]

        statistics = get_fixture_statistics(
            fixture_id
        )

        match_data = build_match_data(
            fixture,
            statistics,
            stvv_id
        )

        print("")
        print("========== 取得データ ==========")
        print(
            f"STVV: {stvv_name}"
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

        print("===============================")
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

        # APIエラー時に偽データは生成しない
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

        # Actions上でも失敗として分かるようにする
        raise


if __name__ == "__main__":
    main()
