
"""STVV LAB: safe scheduled posting to Buffer."""
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

JST = timezone(timedelta(hours=9))
TEAM = "135461"
SPORTS = "https://www.thesportsdb.com/api/v1/json/123"
NEWS = "https://stvv.jp/news/2026/"
BUFFER = "https://api.buffer.com"
CHANNEL = os.getenv(
    "BUFFER_CHANNEL_ID",
    "6ab8fce4ea19ca0bde027d80",
)
FILE = Path("posted.json")

SLOTS = {
    "0 23 * * *": ("player", 8, 0),
    "30 1 * * *": ("compare", 10, 30),
    "30 3 * * *": ("data", 12, 30),
    "30 6 * * *": ("analysis", 15, 30),
    "0 9 * * *": ("news", 18, 0),
    "0 12 * * *": ("vote", 21, 0),
    "0 14 * * *": ("recap", 23, 0),
}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "STVV-LAB/3.0"

SPONSORS = (
    "スポンサー", "協賛", "パートナー",
    "サプライヤー", "グッズ",
    "キャンペーン", "プレゼント", "抽選",
)
WORDS = (
    "試合", "選手", "監督", "移籍",
    "加入", "退団", "負傷", "復帰",
    "出場", "得点", "代表", "招集",
    "契約", "順位", "勝利", "敗戦", "日程",
)

TOPICS = {
    "player": [
        "🇯🇵 選手分析｜得点・アシストだけでは測れない貢献があります。守備への切り替え、受ける位置、味方のための動きも評価したいポイントです。",
        "🇯🇵 欧州でプレーする選手の成長を見るなら、出場時間だけでなく、任される役割やプレーの選択肢の変化にも注目したいところです。",
        "🇯🇵 FWの働きはゴールだけではありません。相手DFを動かすランニングや前線の守備が、味方のチャンスを生みます。",
    ],
    "compare": [
        "⚔️ チーム比較｜シュート本数だけで攻撃力は判断できません。どの位置から、どれほど良い体勢で打てたかも重要です。",
        "⚔️ DF比較｜タックル数が多い選手が必ずしも優秀とは限りません。パスコースを消す位置取りにも注目です。",
        "⚔️ 中盤比較｜パス成功率だけでなく、相手の守備を崩す前進パスや、失った直後の守備対応も確認したい指標です。",
    ],
    "data": [
        "📊 データの見方｜保持率が高くても勝てるとは限りません。保持した位置と、そこから生まれた決定機を合わせて見る必要があります。",
        "📊 枠内シュート率は枠内シュート数÷総シュート数。ただし、枠内に飛んだことと、得点の可能性が高かったことは別です。",
        "📊 守備分析｜被シュート数が少なくても、決定的な場面を何度も許していれば、守備が安定していたとは言い切れません。",
    ],
    "analysis": [
        "🧠 戦術分析｜前線からのプレスは、後方との連動が重要。前だけが追えば中盤に空間が生まれ、相手に前進を許します。",
        "🧠 サイド攻撃｜幅を取る選手と内側へ動く選手が連動すると、相手DFに複数の判断を迫ることができます。",
        "🧠 試合終盤｜リード時は保持だけでなく、失った直後の配置が重要。攻守のバランスが勝点を左右します。",
    ],
    "news": [
        "📰 STVV LAB｜移籍や負傷の情報は、公式発表と報道を分けて確認することが重要です。未確定情報を事実として扱わないことを大切にします。",
        "📰 STVV LAB｜クラブの動きを追うときは、新加入だけでなく契約更新や若手の起用にも注目。編成の方向性を考える材料になります。",
        "📰 STVV LAB｜試合前には対戦相手の直近成績、出場可能な選手、ホーム・アウェイの条件を確認。予想と確定情報は区別します。",
    ],
    "vote": [
        "🗳️ STVVファンに質問！試合で一番見たいのは？\n①日本人選手の活躍\n②チームの勝利\n③戦術的な駆け引き\n④若手の成長",
        "🗳️ STVV LABアンケート！次に詳しく読みたい分析は？\n①攻撃の仕組み\n②守備の連動\n③選手の個人成績\n④対戦相手の研究",
        "🗳️ サッカー観戦で最も注目するのは？\n①ゴールシーン\n②好守備\n③パスワーク\n④監督の采配",
    ],
    "recap": [
        "⚽ 試合を振り返るときは、スコアだけでなく得点・失点の時間帯にも注目。どの局面で試合が動いたかが重要です。",
        "⚽ 勝敗の要因｜決定力だけでなく、チャンスを作るまでの過程も重要。良い形を何度作れたかを振り返りたいところです。",
        "⚽ 次戦への視点｜前節の課題が改善されたか。単発の結果だけでなく、複数試合を通じた変化を追うことが大切です。",
    ],
}


def log(message):
    print(
        f"[{datetime.now(JST):%Y-%m-%d %H:%M:%S}] "
        f"{message}",
        flush=True,
    )


def git(*args):
    subprocess.run(["git", *args], check=True)


def save(history):
    temp = FILE.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(
            history, ensure_ascii=False, indent=2
        ) + "\n",
        encoding="utf-8",
    )
    temp.replace(FILE)

    git(
        "config", "user.name",
        "github-actions[bot]",
    )
    git(
        "config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    git("add", "posted.json")

    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"]
    )
    if result.returncode == 0:
        return
    if result.returncode != 1:
        raise RuntimeError("git diff failed")

    git(
        "commit", "-m",
        "Update STVV LAB posting state",
    )
    git("push")


def load():
    if not FILE.exists():
        raise RuntimeError(
            "posted.json がないため安全停止"
        )

    history = json.loads(
        FILE.read_text(encoding="utf-8")
    )

    if (
        not isinstance(history, dict)
        or not isinstance(history.get("news"), list)
        or not isinstance(
            history.get("used_posts"), list
        )
    ):
        raise RuntimeError(
            "posted.json の形式が不正です"
        )

    if (
        not isinstance(
            history.get("publication_log", []), list
        )
        or not isinstance(
            history.get("pending_posts", {}), dict
        )
    ):
        raise RuntimeError(
            "履歴の追加項目が不正です"
        )

    history.setdefault("publication_log", [])
    history.setdefault("pending_posts", {})
    history.setdefault("tracked_topics", {})

    return history


def slot_for_run(now):
    if (
        os.getenv("GITHUB_EVENT_NAME")
        == "workflow_dispatch"
    ):
        return None, None

    cron = os.getenv(
        "GITHUB_SCHEDULE", ""
    ).strip()

    if cron not in SLOTS:
        raise RuntimeError(
            f"予定時刻が不明です: {cron!r}"
        )

    slot, hour, minute = SLOTS[cron]

    expected = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if now < expected:
        expected -= timedelta(days=1)

    if now - expected > timedelta(hours=6):
        raise RuntimeError(
            "実行が6時間以上遅れたため安全停止"
        )

    return slot, expected.date().isoformat()


def fetch(endpoint, params):
    response = SESSION.get(
        f"{SPORTS}/{endpoint}",
        params=params,
        timeout=25,
    )
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(
            "APIレスポンスが不正です"
        )

    return data


def latest_match(now):
    events = fetch(
        "eventslast.php", {"id": TEAM}
    ).get("results") or []

    valid = []

    for event in events:
        if not isinstance(event, dict):
            continue

        teams = {
            str(event.get("idHomeTeam")),
            str(event.get("idAwayTeam")),
        }
        if TEAM not in teams:
            continue

        if str(
            event.get("strStatus", "")
        ).upper() not in {
            "FT", "AET", "PEN"
        }:
            continue

        try:
            day = datetime.strptime(
                event["dateEvent"], "%Y-%m-%d"
            ).date()
            home_score = int(
                event["intHomeScore"]
            )
            away_score = int(
                event["intAwayScore"]
            )
        except (
            KeyError, ValueError, TypeError
        ):
            continue

        if (
            0 <= (now.date() - day).days <= 7
            and event.get("idEvent")
        ):
            valid.append(
                (
                    day, event,
                    home_score, away_score,
                )
            )

    return (
        max(valid, key=lambda item: item[0])[1]
        if valid else None
    )


def match_post(event, slot):
    home = (
        str(event.get("idHomeTeam"))
        == TEAM
    )

    opponent = (
        event.get("strAwayTeam")
        if home
        else event.get("strHomeTeam")
    )
    if not opponent:
        return None

    own = int(
        event["intHomeScore"]
        if home
        else event["intAwayScore"]
    )
    other = int(
        event["intAwayScore"]
        if home
        else event["intHomeScore"]
    )

    base = (
        f"{event['dateEvent']}｜"
        f"{'ホーム' if home else 'アウェイ'}\n"
        f"STVV {own}–{other} {opponent}"
    )

    if slot == "recap":
        result = (
            "勝利" if own > other
            else "引き分け" if own == other
            else "敗戦"
        )
        return (
            f"⚽ STVV試合結果\n{base}\n"
            f"結果：{result}。"
        )

    if slot == "vote":
        return (
            f"🗳️ STVVファンに質問\n{base}\n"
            "この試合で最も印象に残った場面は？"
        )

    if slot not in {
        "data", "compare", "analysis"
    }:
        return None

    try:
        stats = fetch(
            "lookupeventstats.php",
            {"id": event["idEvent"]},
        )
    except (
        requests.RequestException, ValueError
    ) as error:
        log(f"スタッツ取得不可: {error}")
        return None

    rows = (
        stats.get("eventstats")
        or stats.get("statistics")
        or []
    )

    values = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        name = str(
            row.get("strStat")
            or row.get("strStatistic")
            or ""
        ).strip().lower()

        a = (
            row.get("intHome")
            if row.get("intHome") is not None
            else row.get("strHome")
        )
        b = (
            row.get("intAway")
            if row.get("intAway") is not None
            else row.get("strAway")
        )

        if a is not None and b is not None:
            values[name] = (
                (str(a), str(b))
                if home
                else (str(b), str(a))
            )

    def stat(*names):
        return next(
            (
                values[name]
                for name in names
                if name in values
            ),
            None,
        )

    shots = stat(
        "total shots",
        "shots",
        "total attempts",
    )
    target = stat(
        "shots on goal",
        "shots on target",
        "on target",
    )
    possession = stat(
        "ball possession",
        "possession",
    )

    if slot == "compare" and shots:
        return (
            f"⚔️ シュート数比較\n{base}\n"
            f"STVV {shots[0]}／相手 {shots[1]}\n"
            "本数と決定機の質は区別して評価します。"
        )

    if slot == "data":
        lines = []

        for label, pair in [
            ("シュート", shots),
            ("枠内", target),
            ("支配率", possession),
        ]:
            if pair:
                lines.append(
                    f"{label}："
                    f"{pair[0]} 対 {pair[1]}"
                )

        return (
            f"📊 STVV試合データ\n{base}\n"
            + "\n".join(lines)
            if lines else None
        )

    if (
        slot == "analysis"
        and shots
        and target
    ):
        try:
            a = float(shots[0])
            b = float(target[0])

            if a > 0 and 0 <= b <= a:
                return (
                    f"🧠 STVV攻撃データ\n{base}\n"
                    f"シュート{int(a)}本／"
                    f"枠内{int(b)}本\n"
                    f"枠内率：約{b / a * 100:.1f}%\n"
                    "決定機の質は別途検証が必要です。"
                )
        except ValueError:
            pass

    return None


def articles(now):
    response = SESSION.get(
        NEWS, timeout=25
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text, "html.parser"
    )
    found = {}

    for anchor in soup.find_all(
        "a", href=True
    ):
        url = urljoin(
            NEWS, anchor["href"]
        )
        parsed = urlparse(url)

        if parsed.netloc.lower() != "stvv.jp":
            continue

        path = (
            parsed.path.rstrip("/") + "/"
        )

        match = re.fullmatch(
            r"/news/(game|team)/"
            r"(20\d{6}[^/]*)/",
            path,
            re.I,
        )
        if not match:
            continue

        try:
            day = datetime.strptime(
                match.group(2)[:8],
                "%Y%m%d",
            ).date()
        except ValueError:
            continue

        if not (
            0 <= (now.date() - day).days <= 7
        ):
            continue

        title = re.sub(
            r"\s+",
            " ",
            BeautifulSoup(
                html.unescape(
                    anchor.get_text(
                        " ", strip=True
                    )
                ),
                "html.parser",
            ).get_text(" ", strip=True),
        ).strip()

        if (
            len(title) < 8
            or any(
                word in title
                for word in SPONSORS
            )
            or not any(
                word in title
                for word in WORDS
            )
        ):
            continue

        found[
            "https://stvv.jp" + path
        ] = (day, title)

    return sorted(
        found.items(),
        key=lambda item: item[1][0],
        reverse=True,
    )


def x_length(message):
    count = 0
    previous = 0

    for match in re.finditer(
        r"https?://\S+", message
    ):
        count += sum(
            1 if ord(c) < 128 else 2
            for c in message[
                previous:match.start()
            ]
        ) + 23

        previous = match.end()

    return count + sum(
        1 if ord(c) < 128 else 2
        for c in message[previous:]
    )


def send(message):
    key = os.getenv("BUFFER_API_KEY")

    if not key or not CHANNEL:
        raise RuntimeError(
            "Buffer設定がありません"
        )

    if x_length(message) > 270:
        raise RuntimeError(
            "X文字数の安全上限を超えました"
        )

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id status }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "input": {
                "text": message,
                "channelId": CHANNEL,
                "schedulingType": "automatic",
                "mode": "shareNow",
            }
        },
    }

    response = SESSION.post(
        BUFFER,
        json=payload,
        timeout=30,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Buffer GraphQL error: "
            f"{data['errors']}"
        )

    action = (
        (data.get("data") or {})
        .get("createPost") or {}
    )
    post = action.get("post") or {}

    if not post.get("id"):
        raise RuntimeError(
            "Buffer受付を確認できません: "
            f"{action}"
        )

    return post


def publish(
    history,
    key,
    message,
    slot,
    source=None,
    news_url=None,
):
    if key in history["used_posts"]:
        log(f"投稿済み: {key}")
        return False

    if key in history["pending_posts"]:
        log(
            f"送信結果の確認待ち: {key}。"
            "重複防止のため再送しません"
        )
        return False

    # 送信前に予約をGitHubへ保存する。
    # 保存失敗時はBufferに送信しない。
    history["pending_posts"][key] = {
        "slot": slot,
        "source": source,
        "text": message,
        "created_at": (
            datetime.now(JST).isoformat()
        ),
    }

    save(history)

    log(f"Buffer送信開始: {key}")

    # 送信結果が不明ならpendingを残す。
    # 自動再送による重複を防止する。
    post = send(message)

    history["used_posts"].append(key)

    history["publication_log"].append({
        "key": key,
        "slot": slot,
        "source": source,
        "buffer_id": str(post["id"]),
        "buffer_status": post.get("status"),
        "submitted_at": (
            datetime.now(JST).isoformat()
        ),
        "text": message,
    })

    if (
        news_url
        and news_url not in history["news"]
    ):
        history["news"].append(news_url)

    del history["pending_posts"][key]

    save(history)

    log(
        f"Buffer受付成功: {post['id']} "
        "/ 履歴保存完了"
    )
    return True


def main():
    now = datetime.now(JST)
    history = load()
    slot, day = slot_for_run(now)

    if slot is None:
        log(
            "手動実行は安全確認のみ。"
            "投稿はしません"
        )
        log(
            "既存投稿履歴: "
            f"{len(history['used_posts'])}件、"
            "確認待ち: "
            f"{len(history['pending_posts'])}件"
        )
        return

    daily = f"daily_{day}_{slot}"

    if (
        daily in history["used_posts"]
        or daily in history["pending_posts"]
    ):
        log(
            f"{day} {slot} は"
            "処理済み／確認待ちです"
        )
        return

    log(f"定期投稿: {day} {slot}")

    message = None
    source = None
    news_url = None

    if slot == "news":
        try:
            for url, (_, title) in articles(now):
                if url in history["news"]:
                    continue

                candidate = (
                    "📰 STVV公式ニュース\n"
                    f"{title}\n"
                    f"🔗 {url}"
                )

                if x_length(
                    candidate + "\n#STVV"
                ) <= 270:
                    message = candidate
                    source = url
                    news_url = url
                    break

        except (
            requests.RequestException,
            ValueError,
        ) as error:
            log(
                f"ニュース取得不可: {error}"
            )

    if (
        not message
        and slot in {
            "compare",
            "data",
            "analysis",
            "vote",
            "recap",
        }
    ):
        try:
            event = latest_match(now)

            if event:
                match_key = (
                    f"real_{event['idEvent']}"
                    f"_{slot}"
                )

                if (
                    match_key
                    not in history["used_posts"]
                ):
                    message = match_post(
                        event, slot
                    )

                    if message:
                        source = (
                            "thesportsdb:"
                            f"{event['idEvent']}"
                        )

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            log(
                f"試合取得不可: {error}"
            )

    if not message:
        topics = TOPICS[slot]

        index = (
            datetime.strptime(
                day, "%Y-%m-%d"
            ).date().toordinal()
            + list(TOPICS).index(slot) * 7
        ) % len(topics)

        message = topics[index]

    message += (
        "\n\n#STVV #シントトロイデン"
    )

    # 1投稿枠につき1つの履歴キー。
    # ニュースURLは同時に既読登録。
    publish(
        history,
        daily,
        message,
        slot,
        source,
        news_url,
    )


if __name__ == "__main__":
    main()
