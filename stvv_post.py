
"""STVV LAB automatic posting - stable edition."""

import hashlib
import html
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ==========================================
# 基本設定
# ==========================================

JST = timezone(timedelta(hours=9))

SPORTS_DB = "https://www.thesportsdb.com/api/v1/json/123"
TEAM_ID = "135461"

NEWS_URL = "https://stvv.jp/news/2026/"
BUFFER_URL = "https://api.buffer.com"

CHANNEL_ID = os.getenv(
    "BUFFER_CHANNEL_ID",
    "6ab8fce4ea19ca0bde027d80",
)

HISTORY_FILE = Path("posted.json")

SCHEDULE_SLOTS = {
    "0 23 * * *": "player",
    "30 1 * * *": "compare",
    "30 3 * * *": "data",
    "30 6 * * *": "analysis",
    "0 9 * * *": "news",
    "0 12 * * *": "vote",
    "0 14 * * *": "recap",
}

SLOT_TIMES = {
    "player": "08:00",
    "compare": "10:30",
    "data": "12:30",
    "analysis": "15:30",
    "news": "18:00",
    "vote": "21:00",
    "recap": "23:00",
}

SLOT_TITLES = {
    "player": "🇯🇵 STVV LAB｜選手分析",
    "compare": "⚔️ STVV LAB｜比較分析",
    "data": "📊 STVV LAB｜試合データ",
    "analysis": "🧠 STVV LAB｜戦術分析",
    "news": "📰 STVV LAB｜クラブ情報",
    "vote": "🗳️ STVV LAB｜ファン参加",
    "recap": "⚽ STVV LAB｜試合レビュー",
}

SPONSOR_WORDS = (
    "スポンサー",
    "パートナー契約",
    "協賛",
    "サプライヤー",
    "商品販売",
    "グッズ",
    "キャンペーン",
    "プレゼント",
    "抽選",
)

FOOTBALL_WORDS = (
    "試合",
    "結果",
    "順位",
    "選手",
    "監督",
    "移籍",
    "加入",
    "退団",
    "負傷",
    "復帰",
    "出場",
    "得点",
    "ゴール",
    "代表",
    "招集",
    "対戦",
    "勝利",
    "敗戦",
    "日程",
    "スタメン",
    "契約更新",
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "STVV-LAB/2.0",
})


# ==========================================
# 共通処理
# ==========================================

def log(message):
    now = datetime.now(JST)
    print(
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{message}",
        flush=True,
    )


def fetch_json(endpoint, params=None):
    response = SESSION.get(
        f"{SPORTS_DB}/{endpoint}",
        params=params,
        timeout=25,
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("API response is not an object")

    return data


def clean_text(value):
    text = html.unescape(str(value or ""))
    text = BeautifulSoup(
        text, "html.parser"
    ).get_text(" ", strip=True)

    return re.sub(r"\s+", " ", text).strip()


def text_length(value):
    total = 0
    position = 0

    for match in re.finditer(
        r"https?://\S+", value
    ):
        before = value[position:match.start()]

        total += sum(
            1 if ord(char) < 128 else 2
            for char in before
        )

        total += 23
        position = match.end()

    total += sum(
        1 if ord(char) < 128 else 2
        for char in value[position:]
    )

    return total


def make_key(*values):
    source = "|".join(str(x) for x in values)

    return hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()[:20]


# ==========================================
# 投稿履歴
# ==========================================

def load_history():
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            "posted.json がありません。"
            "既存履歴を保護するため停止します。"
        )

    data = json.loads(
        HISTORY_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, dict):
        raise RuntimeError(
            "posted.json の形式が不正です"
        )

    if not isinstance(
        data.get("news"), list
    ):
        raise RuntimeError(
            "news の形式が不正です"
        )

    if not isinstance(
        data.get("used_posts"), list
    ):
        raise RuntimeError(
            "used_posts の形式が不正です"
        )

    # 既存のキーは削除しない
    data.setdefault("publication_log", [])
    data.setdefault("tracked_topics", {})

    return data


def save_history(history):
    temporary = HISTORY_FILE.with_name(
        "posted.json.tmp"
    )

    temporary.write_text(
        json.dumps(
            history,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    temporary.replace(HISTORY_FILE)

    subprocess.run(
        [
            "git", "config",
            "user.name",
            "github-actions[bot]",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git", "config",
            "user.email",
            "41898282+github-actions[bot]"
            "@users.noreply.github.com",
        ],
        check=True,
    )

    subprocess.run(
        ["git", "add", "posted.json"],
        check=True,
    )

    diff = subprocess.run(
        [
            "git", "diff",
            "--cached", "--quiet",
        ],
        check=False,
    )

    if diff.returncode == 0:
        return

    if diff.returncode != 1:
        raise RuntimeError(
            "Git差分の確認に失敗しました"
        )

    subprocess.run(
        [
            "git", "commit",
            "-m", "Update STVV LAB history",
        ],
        check=True,
    )

    subprocess.run(
        ["git", "push"],
        check=True,
    )


# ==========================================
# 実行枠の判定
# ==========================================

def determine_slot(now):
    event_name = os.getenv(
        "GITHUB_EVENT_NAME", ""
    )

    if event_name == "workflow_dispatch":
        return "manual"

    cron = os.getenv(
        "GITHUB_SCHEDULE", ""
    ).strip()

    if cron:
        slot = SCHEDULE_SLOTS.get(cron)

        if not slot:
            raise RuntimeError(
                f"未知のスケジュール: {cron}"
            )

        return slot

    # ローカル実行用
    current = now.strftime("%H:%M")

    for slot, scheduled in SLOT_TIMES.items():
        if current == scheduled:
            return slot

    return None


# ==========================================
# 試合データ
# ==========================================

def get_latest_match(now):
    data = fetch_json(
        "eventslast.php",
        {"id": TEAM_ID},
    )

    candidates = []

    for event in data.get("results") or []:
        if not isinstance(event, dict):
            continue

        teams = {
            str(event.get("idHomeTeam")),
            str(event.get("idAwayTeam")),
        }

        if TEAM_ID not in teams:
            continue

        status = str(
            event.get("strStatus") or ""
        ).upper()

        if status not in {
            "FT", "AET", "PEN"
        }:
            continue

        try:
            day = datetime.strptime(
                event["dateEvent"],
                "%Y-%m-%d",
            ).date()

            home_score = int(
                event["intHomeScore"]
            )

            away_score = int(
                event["intAwayScore"]
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ):
            continue

        age = (now.date() - day).days

        if age < 0 or age > 7:
            continue

        if not event.get("idEvent"):
            continue

        candidates.append(
            (day, event, home_score, away_score)
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


def get_match_info(event):
    home = (
        str(event.get("idHomeTeam"))
        == TEAM_ID
    )

    opponent = (
        event.get("strAwayTeam")
        if home
        else event.get("strHomeTeam")
    )

    if not opponent:
        return None

    own_score = int(
        event["intHomeScore"]
        if home
        else event["intAwayScore"]
    )

    other_score = int(
        event["intAwayScore"]
        if home
        else event["intHomeScore"]
    )

    result = (
        "勝利"
        if own_score > other_score
        else "引き分け"
        if own_score == other_score
        else "敗戦"
    )

    return {
        "id": str(event["idEvent"]),
        "date": event["dateEvent"],
        "opponent": str(opponent),
        "venue": (
            "ホーム" if home else "アウェイ"
        ),
        "home": home,
        "own": own_score,
        "other": other_score,
        "result": result,
    }


def get_match_stats(event_id):
    try:
        data = fetch_json(
            "lookupeventstats.php",
            {"id": event_id},
        )
    except (
        requests.RequestException,
        ValueError,
    ) as error:
        log(f"スタッツ取得失敗: {error}")
        return {}

    rows = (
        data.get("eventstats")
        or data.get("statistics")
        or []
    )

    stats = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        name = str(
            row.get("strStat")
            or row.get("strStatistic")
            or ""
        ).lower().strip()

        if not name:
            continue

        home = row.get("intHome")
        away = row.get("intAway")

        if home is None:
            home = row.get("strHome")

        if away is None:
            away = row.get("strAway")

        stats[name] = (home, away)

    return stats


def find_stat(stats, names, home):
    index = 0 if home else 1

    for name in names:
        pair = stats.get(name)

        if (
            isinstance(pair, (list, tuple))
            and len(pair) == 2
            and pair[index] is not None
            and pair[1 - index] is not None
        ):
            own = str(pair[index])
            other = str(pair[1 - index])

            return own, other

    return None


# ==========================================
# 試合関連の投稿
# ==========================================

def build_match_post(event, slot):
    info = get_match_info(event)

    if not info:
        return None

    base = (
        f"{info['date']}｜{info['venue']}\n"
        f"STVV {info['own']}–"
        f"{info['other']} "
        f"{info['opponent']}"
    )

    suffix = (
        "\n\n#STVV #シントトロイデン"
    )

    if slot == "recap":
        return (
            "⚽ STVV｜試合結果\n\n"
            f"{base}\n"
            f"結果：{info['result']}\n\n"
            "勝敗とスコアを確認。"
            "試合内容の評価には、"
            "さらにプレーデータが必要です。"
            + suffix
        )

    if slot == "vote":
        return (
            "🗳️ STVV｜試合を振り返る\n\n"
            f"{base}\n\n"
            "この試合で最も評価したいのは？\n"
            "① 攻撃\n"
            "② 守備\n"
            "③ 個人のプレー\n"
            "④ 監督の采配"
            + suffix
        )

    if slot not in {
        "data", "compare", "analysis"
    }:
        return None

    stats = get_match_stats(info["id"])

    shots = find_stat(
        stats,
        [
            "total shots",
            "shots",
            "total attempts",
        ],
        info["home"],
    )

    target = find_stat(
        stats,
        [
            "shots on goal",
            "shots on target",
            "on target",
        ],
        info["home"],
    )

    possession = find_stat(
        stats,
        [
            "ball possession",
            "possession",
        ],
        info["home"],
    )

    if slot == "compare" and shots:
        return (
            "⚔️ STVV｜シュート数比較\n\n"
            f"{base}\n\n"
            f"STVV：{shots[0]}\n"
            f"相手：{shots[1]}\n\n"
            "シュート数だけでは"
            "決定機の質までは判断できません。"
            + suffix
        )

    if slot == "data":
        lines = []

        if shots:
            lines.append(
                f"シュート："
                f"{shots[0]} 対 {shots[1]}"
            )

        if target:
            lines.append(
                f"枠内："
                f"{target[0]} 対 {target[1]}"
            )

        if possession:
            lines.append(
                f"支配率："
                f"{possession[0]} 対 "
                f"{possession[1]}"
            )

        if lines:
            return (
                "📊 STVV｜試合データ\n\n"
                f"{base}\n\n"
                + "\n".join(lines)
                + "\n\n数字をもとに"
                "試合内容を振り返ります。"
                + suffix
            )

    if slot == "analysis" and shots and target:
        try:
            own_shots = float(
                shots[0].replace("%", "")
            )

            own_target = float(
                target[0].replace("%", "")
            )

            if own_shots <= 0:
                return None

            rate = (
                own_target / own_shots * 100
            )

            if not 0 <= rate <= 100:
                return None

        except ValueError:
            return None

        return (
            "🧠 STVV｜攻撃データ分析\n\n"
            f"{base}\n\n"
            f"シュート：{shots[0]}本\n"
            f"枠内：{target[0]}本\n"
            f"枠内率：約{rate:.1f}%\n\n"
            "枠内率は攻撃を評価する"
            "指標の一つです。"
            "決定機の質とは区別して考えます。"
            + suffix
        )

    return None


# ==========================================
# 公式ニュース
# ==========================================

def get_news(now):
    response = SESSION.get(
        NEWS_URL,
        timeout=25,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    articles = []
    seen = set()

    pattern = re.compile(
        r"^/news/(game|team)/"
        r"(20\d{6}[^/]*)/$",
        re.I,
    )

    for anchor in soup.find_all(
        "a", href=True
    ):
        url = urljoin(
            NEWS_URL,
            anchor["href"],
        )

        parsed = urlparse(url)

        if parsed.netloc.lower() != "stvv.jp":
            continue

        path = parsed.path.rstrip("/") + "/"
        match = pattern.fullmatch(path)

        if not match:
            continue

        canonical = (
            "https://stvv.jp" + path
        )

        if canonical in seen:
            continue

        seen.add(canonical)

        try:
            day = datetime.strptime(
                match.group(2)[:8],
                "%Y%m%d",
            ).date()
        except ValueError:
            continue

        age = (now.date() - day).days

        if not 0 <= age <= 7:
            continue

        title = clean_text(
            anchor.get_text(" ", strip=True)
        )

        if len(title) < 8:
            continue

        if any(
            word in title
            for word in SPONSOR_WORDS
        ):
            continue

        if not any(
            word in title
            for word in FOOTBALL_WORDS
        ):
            continue

        articles.append({
            "url": canonical,
            "title": title,
            "day": day.isoformat(),
        })

    articles.sort(
        key=lambda item: item["day"],
        reverse=True,
    )

    return articles


def build_news_post(article):
    return (
        "📰 STVV｜公式ニュース\n\n"
        f"{article['title']}\n\n"
        "公式発表はこちら👇\n"
        f"{article['url']}\n\n"
        "#STVV #シントトロイデン"
    )


# ==========================================
# データ不足時の投稿
# ==========================================

EVERGREEN = {
    "player": [
        (
            "選手を評価するとき、"
            "得点・アシストだけでは"
            "見えない貢献があります。\n\n"
            "例えば、守備への切り替え、"
            "味方のための動き、"
            "ボールを受ける位置。\n\n"
            "あなたが最も注目するのは？"
        ),
        (
            "日本人選手の欧州挑戦を"
            "見るときに注目したいのは、"
            "出場時間だけではありません。\n\n"
            "どんな役割を任され、"
            "試合にどう関わっているか。"
            "その変化も重要です。"
        ),
        (
            "FWの貢献度を考えるなら、"
            "ゴール以外にも注目。\n\n"
            "裏への抜け出し、"
            "前線からの守備、"
            "味方へのスペース作り。\n\n"
            "数字に表れにくい働きもあります。"
        ),
    ],
    "compare": [
        (
            "シュート数が多いチームと、"
            "少ないチャンスを決め切るチーム。\n\n"
            "攻撃力を比べるなら、"
            "本数だけでなく"
            "シュート位置や決定機の質も"
            "確認したいところです。"
        ),
        (
            "DFを比較するとき、"
            "タックル数だけで"
            "優劣を決められるでしょうか。\n\n"
            "ポジショニングによって"
            "相手にパスを出させない守備も、"
            "大きな貢献です。"
        ),
        (
            "中盤の選手を比較するなら、"
            "パス成功率だけでは不十分。\n\n"
            "前進させるパス、"
            "相手の守備を動かす判断、"
            "ボールを失うリスクも"
            "合わせて考えたいところです。"
        ),
    ],
    "data": [
        (
            "📊 サッカーのデータ分析\n\n"
            "ボール保持率が高くても、"
            "必ず勝てるわけではありません。\n\n"
            "どこで保持したのか、"
            "そこから何回チャンスを"
            "作れたのかが重要です。"
        ),
        (
            "📊 枠内シュート率とは？\n\n"
            "枠内シュート数を"
            "総シュート数で割った割合。\n\n"
            "ただし、枠内に飛んだだけで"
            "得点期待値が高いとは限りません。"
        ),
        (
            "📊 守備データの見方\n\n"
            "被シュート数が少ないことは"
            "重要な指標の一つ。\n\n"
            "一方で、少ない本数でも"
            "決定的な場面を許していれば、"
            "守備の評価は変わります。"
        ),
    ],
    "analysis": [
        (
            "🧠 STVV LAB｜戦術の見方\n\n"
            "前線からプレスをかけるなら、"
            "後方の選手との連動が重要。\n\n"
            "前だけが追いかけても、"
            "中盤にスペースが生まれます。"
        ),
        (
            "🧠 サイド攻撃のポイント\n\n"
            "幅を取る選手と"
            "内側に入る選手の連携。\n\n"
            "相手DFに複数の選択肢を"
            "意識させることで、"
            "突破の可能性が広がります。"
        ),
        (
            "🧠 試合終盤の戦い方\n\n"
            "リード時には"
            "ボールを保持するだけでなく、"
            "失った直後の配置も重要。\n\n"
            "攻守のバランスが"
            "勝点を左右します。"
        ),
    ],
    "news": [
        (
            "📰 STVV LAB｜情報の見方\n\n"
            "移籍や負傷の情報は、"
            "公式発表と報道を"
            "分けて確認することが重要。\n\n"
            "未確定情報を"
            "事実として扱わないことを"
            "大切にします。"
        ),
        (
            "📰 STVV LAB｜注目ポイント\n\n"
            "クラブの動きを追うときは、"
            "新加入だけでなく"
            "契約更新や若手の起用にも注目。\n\n"
            "チーム編成の方向性を"
            "考える材料になります。"
        ),
        (
            "📰 STVV LAB｜試合情報\n\n"
            "試合前に確認したいのは、"
            "対戦相手の直近成績、"
            "出場可能な選手、"
            "ホーム・アウェイの条件。\n\n"
            "予想と確定情報は"
            "分けて扱います。"
        ),
    ],
    "vote": [
        (
            "🗳️ STVVファンに質問！\n\n"
            "試合で一番見たいのは？\n\n"
            "① 日本人選手の活躍\n"
            "② チームの勝利\n"
            "③ 戦術的な駆け引き\n"
            "④ 若手の成長"
        ),
        (
            "🗳️ STVV LABアンケート\n\n"
            "次に詳しく読みたい分析は？\n\n"
            "① 攻撃の仕組み\n"
            "② 守備の連動\n"
            "③ 選手の個人成績\n"
            "④ 対戦相手の研究"
        ),
        (
            "🗳️ サッカー観戦の楽しみ\n\n"
            "あなたが最も注目するのは？\n\n"
            "① ゴールシーン\n"
            "② 好守備\n"
            "③ パスワーク\n"
            "④ 監督の采配"
        ),
    ],
    "recap": [
        (
            "⚽ STVV LAB｜試合分析\n\n"
            "試合を振り返るときは、"
            "スコアだけでなく"
            "得点・失点の時間帯にも注目。\n\n"
            "どの局面で試合が動いたかを"
            "確認することが大切です。"
        ),
        (
            "⚽ STVV LAB｜勝敗の要因\n\n"
            "試合結果を分析するなら、"
            "決定力だけでなく"
            "チャンスの作り方も重要。\n\n"
            "良い形を何度作れたかで、"
            "次戦への評価も変わります。"
        ),
        (
            "⚽ STVV LAB｜次戦への視点\n\n"
            "試合後に注目したいのは、"
            "課題が次の試合で"
            "改善されたかどうか。\n\n"
            "単発の結果ではなく、"
            "複数試合の変化を"
            "追うことが重要です。"
        ),
    ],
}


def build_evergreen(slot, now):
    topics = EVERGREEN[slot]

    # 日付と枠でテーマを切り替える
    index = (
        now.date().toordinal()
        + list(SLOT_TIMES).index(slot) * 7
    ) % len(topics)

    return (
        f"{SLOT_TITLES[slot]}\n\n"
        f"{topics[index]}\n\n"
        "#STVV #シントトロイデン"
    )


# ==========================================
# Buffer投稿
# ==========================================

def post_to_buffer(message):
    api_key = os.getenv(
        "BUFFER_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "BUFFER_API_KEY が未設定です"
        )

    if not CHANNEL_ID:
        raise RuntimeError(
            "BUFFER_CHANNEL_ID が未設定です"
        )

    if text_length(message) > 270:
        raise RuntimeError(
            "投稿文字数が安全上限を超えました"
        )

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            text
            status
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    payload = {
        "query": mutation,
        "variables": {
            "input": {
                "text": message,
                "channelId": CHANNEL_ID,
                "schedulingType": "automatic",
                "mode": "shareNow",
            }
        },
    }

    response = SESSION.post(
        BUFFER_URL,
        json=payload,
        timeout=30,
        headers={
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": "application/json",
        },
    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):
        raise RuntimeError(
            f"Buffer APIエラー: "
            f"{result['errors']}"
        )

    action = (
        result.get("data") or {}
    ).get("createPost") or {}

    post = action.get("post") or {}

    if not post.get("id"):
        raise RuntimeError(
            f"Buffer投稿を確認できません: "
            f"{action}"
        )

    log(
        f"Buffer受付成功: {post['id']}"
    )

    return {
        "id": str(post["id"]),
        "status": post.get("status"),
    }


# ==========================================
# 投稿管理
# ==========================================

def already_posted(history, key):
    return key in history["used_posts"]


def publish(
    history,
    key,
    message,
    slot,
    source=None,
):
    if already_posted(history, key):
        log(f"投稿済みのためスキップ: {key}")
        return False

    log(
        f"投稿開始: {slot} / {key}"
    )

    result = post_to_buffer(message)

    history["used_posts"].append(key)

    history["publication_log"].append({
        "key": key,
        "slot": slot,
        "buffer_id": result["id"],
        "buffer_status": result["status"],
        "submitted_at": (
            datetime.now(JST).isoformat()
        ),
        "source": source,
        "text": message,
    })

    save_history(history)

    log("投稿履歴を保存しました")

    return True


def publish_news(history, now):
    articles = get_news(now)

    for article in articles:
        url = article["url"]

        if url in history["news"]:
            continue

        key = "news_" + make_key(url)

        if already_posted(history, key):
            continue

        message = build_news_post(article)

        if text_length(message) > 270:
            log(
                "ニュースが長いためスキップ: "
                + url
            )
            continue

        # 投稿と履歴保存が成功した後に
        # ニュース既読を追加する
        result = publish(
            history,
            key,
            message,
            "news",
            source=url,
        )

        if result:
            history["news"].append(url)
            save_history(history)
            return True

    return False


def publish_match(
    history,
    now,
    slot,
    event,
):
    if event is None:
        return False

    event_id = str(
        event.get("idEvent") or ""
    )

    if not event_id:
        return False

    key = f"real_{event_id}_{slot}"

    if already_posted(history, key):
        return False

    message = build_match_post(
        event, slot
    )

    if not message:
        return False

    return publish(
        history,
        key,
        message,
        slot,
        source=f"thesportsdb:{event_id}",
    )


def publish_evergreen(
    history,
    now,
    slot,
):
    day = now.strftime("%Y-%m-%d")
    key = f"fallback_{day}_{slot}"

    if already_posted(history, key):
        return False

    message = build_evergreen(
        slot, now
    )

    return publish(
        history,
        key,
        message,
        slot,
    )


# ==========================================
# メイン処理
# ==========================================

def main():
    now = datetime.now(JST)

    log("STVV LAB 自動投稿開始")

    history = load_history()
    slot = determine_slot(now)

    if not slot:
        log("投稿対象時刻ではありません")
        return

    if slot == "manual":
        log("手動実行モード")

        # 手動実行は試合結果の未投稿分を優先
        try:
            event = get_latest_match(now)

            if event:
                if publish_match(
                    history,
                    now,
                    "recap",
                    event,
                ):
                    return

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            log(
                f"試合データ取得失敗: {error}"
            )

        # 手動実行で既存の投稿を
        # 無理に再投稿しない
        log(
            "新しい試合結果がないため"
            "手動投稿を終了します"
        )
        return

    log(
        f"対象枠: {slot} "
        f"({SLOT_TIMES[slot]} JST)"
    )

    day = now.strftime("%Y-%m-%d")

    # この枠で既に投稿していたら終了
    daily_key = f"daily_{day}_{slot}"

    if already_posted(
        history, daily_key
    ):
        log("この枠は本日投稿済みです")
        return

    published = False

    # 18時は公式ニュース優先
    if slot == "news":
        try:
            published = publish_news(
                history, now
            )
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            log(
                f"ニュース取得失敗: {error}"
            )

    # 試合情報を使える枠
    if (
        not published
        and slot in {
            "compare",
            "data",
            "analysis",
            "vote",
            "recap",
        }
    ):
        try:
            event = get_latest_match(now)

            if event:
                published = publish_match(
                    history,
                    now,
                    slot,
                    event,
                )

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            log(
                f"試合データ取得失敗: {error}"
            )

    # 実データがない場合
    if not published:
        published = publish_evergreen(
            history,
            now,
            slot,
        )

    if published:
        history["used_posts"].append(
            daily_key
        )
        save_history(history)

        log(
            f"{slot} 枠の処理完了"
        )


if __name__ == "__main__":
    main()
