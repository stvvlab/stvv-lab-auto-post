
"""STVV LAB automated X posting via Buffer. Python 3.12+."""
import html
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
BASE = "https://www.thesportsdb.com/api/v1/json/123"
TEAM_ID = "135461"
NEWS_URL = "https://stvv.jp/news/2026/"
BUFFER_URL = "https://api.buffer.com"
CHANNEL_ID = os.getenv(
    "BUFFER_CHANNEL_ID", "6ab8fce4ea19ca0bde027d80"
)
POSTED_PATH = Path("posted.json")

SLOTS = {
    8: "review",
    10: "compare",
    12: "data",
    15: "target",
    18: "news",
    21: "vote",
    23: "homeaway",
}

SPONSOR_WORDS = (
    "スポンサー", "パートナー", "協賛", "サプライヤー",
    "キャンペーン", "グッズ", "商品販売", "プレゼント", "抽選"
)
FOOTBALL_WORDS = (
    "試合", "結果", "順位", "勝点", "勝ち点", "先発",
    "スタメン", "出場", "ゴール", "得点", "選手",
    "監督", "移籍", "加入", "負傷", "復帰", "代表",
    "招集", "日程", "対戦", "勝利", "敗戦"
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "STVV-LAB/1.0 (news aggregation)"
})


class SourceUnavailable(Exception):
    pass


def fetch_json(url, params=None):
    try:
        response = SESSION.get(
            url, params=params, timeout=25
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceUnavailable(str(exc)) from exc


def load_history():
    if not POSTED_PATH.exists():
        return {"news": [], "used_posts": []}
    try:
        data = json.loads(
            POSTED_PATH.read_text(encoding="utf-8")
        )
        if isinstance(data, list):
            data = {"news": data, "used_posts": []}
        if not isinstance(data, dict):
            raise ValueError("posted.json must be an object")
        return {
            "news": list(data.get("news") or []),
            "used_posts": list(data.get("used_posts") or []),
        }
    except (ValueError, OSError, TypeError) as exc:
        raise RuntimeError(
            f"投稿履歴を読めません。安全のため停止: {exc}"
        ) from exc


def save_history(history):
    history["news"] = history["news"][-500:]
    history["used_posts"] = history["used_posts"][-1000:]

    temporary = POSTED_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(POSTED_PATH)

    subprocess.run(
        ["git", "config", "user.name", "github-actions[bot]"],
        check=True,
    )
    subprocess.run(
        [
            "git", "config", "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "add", str(POSTED_PATH)],
        check=True,
    )

    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        check=False,
    )
    if changed.returncode == 0:
        return
    if changed.returncode != 1:
        raise RuntimeError("git diff failed")

    subprocess.run(
        ["git", "commit", "-m", "Update STVV posting history"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)


def latest_match(now):
    payload = fetch_json(
        f"{BASE}/eventslast.php",
        {"id": TEAM_ID},
    )
    candidates = []

    for event in payload.get("results") or []:
        if TEAM_ID not in (
            str(event.get("idHomeTeam")),
            str(event.get("idAwayTeam")),
        ):
            continue

        if str(event.get("strStatus") or "").upper() not in (
            "FT", "AET", "PEN"
        ):
            continue

        if (
            event.get("intHomeScore") is None
            or event.get("intAwayScore") is None
        ):
            continue

        try:
            day = datetime.strptime(
                event["dateEvent"], "%Y-%m-%d"
            ).date()
            int(event["intHomeScore"])
            int(event["intAwayScore"])
        except (KeyError, ValueError, TypeError):
            continue

        if 0 <= (now.date() - day).days <= 30:
            candidates.append((day, event))

    return (
        max(candidates, key=lambda item: item[0])[1]
        if candidates else None
    )


def match_stats(event_id):
    if not event_id:
        return {}

    try:
        payload = fetch_json(
            f"{BASE}/lookupeventstats.php",
            {"id": event_id},
        )
        rows = (
            payload.get("eventstats")
            or payload.get("statistics")
            or []
        )
        result = {}

        for row in rows:
            name = str(
                row.get("strStat")
                or row.get("strStatistic")
                or ""
            ).lower().strip()

            if name:
                home = (
                    row.get("intHome")
                    if row.get("intHome") is not None
                    else row.get("strHome")
                )
                away = (
                    row.get("intAway")
                    if row.get("intAway") is not None
                    else row.get("strAway")
                )
                result[name] = (home, away)

        return result

    except (
        SourceUnavailable, ValueError,
        AttributeError, TypeError
    ) as exc:
        print(f"スタッツ未取得: {exc}")
        return {}


def build_match_post(event, slot):
    home = str(event.get("idHomeTeam")) == TEAM_ID
    opponent = (
        event.get("strAwayTeam")
        if home else event.get("strHomeTeam")
    )

    if not opponent or not event.get("idEvent"):
        return None

    own = int(
        event["intHomeScore"]
        if home else event["intAwayScore"]
    )
    other = int(
        event["intAwayScore"]
        if home else event["intHomeScore"]
    )

    venue = "ホーム" if home else "アウェイ"
    base = (
        f"{event['dateEvent']}｜{venue}\n"
        f"STVV {own}–{other} {opponent}"
    )
    result = (
        "勝利" if own > other
        else "引き分け" if own == other
        else "敗戦"
    )
    suffix = "\n\n#STVV #シントトロイデン"

    if slot == "result":
        return (
            f"⚽ STVV試合結果\n{base}\n{result}。\n\n"
            "印象に残った選手は？" + suffix
        )

    if slot == "review":
        return (
            f"🔎 STVV 試合振り返り\n{base}\n"
            f"結果は{result}。\n\n"
            "次の試合に向けて注目する点は？" + suffix
        )

    if slot == "homeaway":
        return (
            f"🏟️ STVV {venue}戦\n{base}\n"
            f"得点：{own}／失点：{other}\n\n"
            f"次の{venue}戦に期待することは？" + suffix
        )

    if slot == "vote":
        return (
            f"🗳️ STVVファンに質問\n{base}\n\n"
            "この試合のMOMは誰？" + suffix
        )

    stats = match_stats(event["idEvent"])
    aliases = {
        "shots": ("total shots", "shots", "total attempts"),
        "target": (
            "shots on goal", "shots on target", "on target"
        ),
        "possession": ("ball possession", "possession"),
        "corners": ("corner kicks", "corners"),
    }
    values = {}

    for key, names in aliases.items():
        pair = next(
            (stats[name] for name in names if name in stats),
            None,
        )
        if (
            pair and len(pair) == 2
            and all(value is not None for value in pair)
        ):
            values[key] = tuple(
                str(v) for v in (
                    pair if home else pair[::-1]
                )
            )

    if slot == "compare" and "shots" in values:
        a, b = values["shots"]
        return (
            f"⚔️ シュート数比較\n{base}\n"
            f"STVV {a}本／相手 {b}本\n\n"
            "どう感じた？" + suffix
        )

    if slot == "target" and "target" in values:
        a, b = values["target"]
        return (
            f"🎯 枠内シュート比較\n{base}\n"
            f"STVV {a}本／相手 {b}本\n\n"
            "数字から見えることは？" + suffix
        )

    if slot == "data" and values:
        labels = {
            "shots": "シュート",
            "target": "枠内シュート",
            "possession": "支配率",
            "corners": "CK",
        }
        lines = [
            f"{labels[k]}：{a} 対 {b}"
            for k, (a, b) in values.items()
        ][:3]
        return (
            f"📊 STVV 試合データ\n{base}\n"
            + "\n".join(lines)
            + "\n\n気になった数字は？"
            + suffix
        )

    return None


def clean_title(value):
    value = re.sub(
        r"\[/?caption\b[^\]]*\]",
        " ",
        str(value or ""),
        flags=re.I,
    )
    value = BeautifulSoup(
        html.unescape(value), "html.parser"
    ).get_text(" ", strip=True)
    return re.sub(r"\s+", " ", value).strip()


def article_title(url, fallback):
    try:
        response = SESSION.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        h1 = soup.find("h1")
        og = soup.find(
            "meta", attrs={"property": "og:title"}
        )

        for title in (
            h1.get_text(" ", strip=True) if h1 else "",
            og.get("content", "") if og else "",
            fallback,
        ):
            title = clean_title(title)
            if len(title) >= 8:
                return title

    except requests.RequestException as exc:
        print(f"ニュース詳細を取得できません: {exc}")

    return clean_title(fallback)


def get_news(now):
    try:
        response = SESSION.get(NEWS_URL, timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceUnavailable(str(exc)) from exc

    soup = BeautifulSoup(response.text, "html.parser")
    articles = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        url = urljoin(
            NEWS_URL, anchor["href"]
        ).split("#", 1)[0].split("?", 1)[0]
        url = url.rstrip("/") + "/"

        match = re.fullmatch(
            r"https://stvv\.jp/news/(game|team)/(20\d{6}[^/]*)/",
            url,
            flags=re.I,
        )
        if not match or url in seen:
            continue

        seen.add(url)

        try:
            article_day = datetime.strptime(
                match.group(2)[:8], "%Y%m%d"
            ).date()
        except ValueError:
            continue

        if not 0 <= (now.date() - article_day).days <= 7:
            continue

        title = article_title(
            url, anchor.get_text(" ", strip=True)
        )

        if (
            len(title) < 8
            or any(word in title for word in SPONSOR_WORDS)
        ):
            continue

        if not any(word in title for word in FOOTBALL_WORDS):
            continue

        articles.append({
            "url": url,
            "title": title,
            "day": article_day,
            "category": match.group(1).lower(),
        })

    articles.sort(
        key=lambda item: (
            item["day"],
            item["category"] == "game",
        ),
        reverse=True,
    )
    return articles


def build_news_post(article):
    header = (
        "⚽ STVV MATCH NEWS 🇧🇪"
        if article["category"] == "game"
        else "🚨 STVV TEAM NEWS 🇧🇪"
    )
    return (
        f"{header}\n\n{article['title']}\n\n"
        f"🔗 {article['url']}\n\n"
        "#STVV #シントトロイデン"
    )


def x_length(text):
    total = 0
    last = 0

    for match in re.finditer(r"https?://\S+", text):
        total += sum(
            1 if ord(c) < 128 else 2
            for c in text[last:match.start()]
        ) + 23
        last = match.end()

    return total + sum(
        1 if ord(c) < 128 else 2
        for c in text[last:]
    )


def post_to_buffer(text):
    if x_length(text) > 270:
        raise ValueError(
            "投稿文字数が上限を超えました。"
            "切り詰めず安全に停止します。"
        )

    api_key = os.environ.get("BUFFER_API_KEY")
    if not api_key:
        raise RuntimeError("BUFFER_API_KEY が未設定です")

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text status }
        }
        ... on MutationError { message }
      }
    }
    """

    payload = {
        "query": mutation,
        "variables": {
            "input": {
                "text": text,
                "channelId": CHANNEL_ID,
                "schedulingType": "automatic",
                "mode": "shareNow",
            }
        },
    }

    response = requests.post(
        BUFFER_URL,
        json=payload,
        timeout=30,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Buffer GraphQLエラー: {data['errors']}"
        )

    result = (
        (data.get("data") or {}).get("createPost") or {}
    )
    post = result.get("post") or {}

    if result.get("message") or not post.get("id"):
        raise RuntimeError(
            f"Buffer投稿が確認できません: {result}"
        )

    print(f"Buffer投稿成功: {post['id']}\n{text}")


def publish_match(history, now, slot):
    event = latest_match(now)
    if not event:
        print(
            "30日以内の終了済みSTVV試合は"
            "取得できませんでした"
        )
        return False

    key = f"real_{event['idEvent']}_{slot}"
    if key in history["used_posts"]:
        print(f"投稿済み: {key}")
        return False

    text = build_match_post(event, slot)
    if not text:
        print(
            f"この試合には{slot}用の"
            "確認済みデータがありません"
        )
        return False

    post_to_buffer(text)
    history["used_posts"].append(key)
    save_history(history)
    return True


def publish_news(history, now):
    articles = get_news(now)

    if not history["news"]:
        history["news"] = [
            item["url"] for item in articles
        ]
        save_history(history)
        print(
            "ニュース既読履歴を初期化。"
            "次回から新着を投稿します"
        )
        return False

    for article in articles:
        if article["url"] in history["news"]:
            continue

        post_to_buffer(build_news_post(article))
        history["news"].append(article["url"])
        save_history(history)
        return True

    print("未投稿の新着ニュースはありません")
    return False


# ==========================================
# 最新情報がない場合の投稿テーマ
# ==========================================

FALLBACK_TOPICS = {
    "review": [
        "STVVの試合を見るとき、最初に注目するのは守備の並び？ それとも前線の動き？",
        "失点場面を振り返るなら、個人の対応とチーム全体の配置、どちらを先に確認したい？",
        "試合を評価するとき、結果と内容のどちらをより重視する？",
        "STVVの試合で「流れが変わった」と感じるのは、どんなプレー？",
        "90分を振り返るなら、まず確認したい数字や場面は何？",
        "守備の改善点を探すとき、プレス開始位置と最終ラインの距離、どちらを見る？",
        "試合のMVPを選ぶなら、得点以外に何を評価したい？",
        "接戦の試合で勝敗を分ける要素は、セットプレー？ 交代策？",
        "STVVの試合を見返すなら、前半と後半のどちらから分析する？",
        "試合内容をひと言で表すとき、何を基準にする？",
    ],
    "compare": [
        "攻撃を比べるなら、シュート数と決定機の質、どちらが重要？",
        "ボール保持率が高いチームと速攻が鋭いチーム、どちらが手ごわい？",
        "サイド攻撃と中央突破。STVVに期待するのはどちら？",
        "前線の選手を比較するなら、得点力と守備への貢献、どちらを重視する？",
        "中盤の選手を見るなら、パス成功率と前進させるパス、どちらに注目？",
        "DFを評価するなら、対人の強さとビルドアップ、どちらを重視する？",
        "GKを比較するなら、セーブと足元の技術、どちらが決め手？",
        "高い位置からのプレスと自陣でのブロック、どちらが好き？",
        "若手の起用と経験豊富な選手の安定感。どちらを優先したい？",
        "得点力と失点の少なさ。順位を上げる鍵はどちらだと思う？",
    ],
    "data": [
        "📊 シュート数が多くても勝てない試合。次に確認したい数字は何？",
        "📊 枠内シュート率と決定率。攻撃の精度を見るならどちら？",
        "📊 パス成功率だけでは分からない攻撃の質。どんな指標を見たい？",
        "📊 セットプレーの強さを測るなら、獲得数と得点数、どちらに注目？",
        "📊 守備の良さを測る数字として、被シュート数以外に何を見たい？",
        "📊 走行距離とスプリント回数。運動量を見るならどちら？",
        "📊 ボール奪取数は多ければいい？ 奪う位置も重要だと思う？",
        "📊 クロスの本数と成功率。サイド攻撃を分析するならどちら？",
        "📊 前半と後半の得点傾向。STVVで調べてみたいのは何？",
        "📊 交代選手の貢献度を測るなら、どんな数字が必要？",
    ],
    "target": [
        "🎯 枠内シュートを増やすには、シュート位置とラストパス、どちらの改善が先？",
        "🎯 決定機を作るなら、裏への抜け出しとサイドの崩し、どちらに期待？",
        "🎯 ミドルシュートは積極的に狙うべき？ それともゴール前まで運ぶべき？",
        "🎯 1対1の場面。シュートを選ぶ選手とパスを選ぶ選手、どちらが好み？",
        "🎯 セットプレーで狙いたいのは、直接ゴール？ こぼれ球の回収？",
        "🎯 攻撃のテンポを上げるには、縦パスとドリブル突破、どちらが有効？",
        "🎯 相手が引いて守るとき、どんな攻め方が効果的だと思う？",
        "🎯 シュート精度を高めるには、どんな練習が重要だと思う？",
        "🎯 ゴール前で人数をかける攻撃とカウンターへの備え、どう両立する？",
        "🎯 得点シーンを分析するなら、最後の一手とその前の動き、どちらに注目？",
    ],
    "news": [
        "📰 STVVの公式発表で、最も知りたいのは選手情報？ 試合情報？",
        "📰 日本人選手の情報で、出場状況とプレー内容、どちらを詳しく知りたい？",
        "📰 移籍ニュースを見るとき、まず確認したいポイントは何？",
        "📰 STVVの最新情報を追うなら、監督コメントと選手コメント、どちらが気になる？",
        "📰 試合前に知りたいのは予想先発？ 相手チームの特徴？",
        "📰 クラブの育成について、どんな話題を深掘りしてほしい？",
        "📰 STVVの情報発信で、もっと増えてほしいコンテンツは何？",
        "📰 日本とベルギーのサッカーを比較するなら、何を取り上げてほしい？",
        "📰 試合後の情報で、スタッツと選手の声、どちらを先に見たい？",
        "📰 STVV LABで次に調べてほしいテーマを教えてください！",
    ],
    "vote": [
        "🗳️ STVVで注目したいポジションは？ FW／MF／DF／GK",
        "🗳️ 好きな得点パターンは？ カウンター／セットプレー／崩し／ミドル",
        "🗳️ 試合観戦で重視するのは？ 結果／戦術／個人技／雰囲気",
        "🗳️ 次に見たい分析は？ 攻撃／守備／選手比較／対戦相手",
        "🗳️ 理想の中盤は？ ボール奪取型／展開力型／運動量型／得点型",
        "🗳️ 試合前に気になるのは？ 先発／フォーメーション／相手の弱点／直近成績",
        "🗳️ サッカー観戦で好きな瞬間は？ ゴール／好守備／パスワーク／逆転劇",
        "🗳️ 注目する若手の特徴は？ スピード／技術／判断力／フィジカル",
        "🗳️ 勝利に欠かせないのは？ 決定力／守備組織／運動量／采配",
        "🗳️ STVV LABへの希望は？ 試合速報／戦術解説／選手紹介／データ分析",
    ],
    "homeaway": [
        "🏟️ ホームで強いチームに必要なのは、先制点？ 安定した守備？",
        "🏟️ アウェイで勝ち点を取るために大切なのは何だと思う？",
        "🏟️ 試合の入り方と終盤の戦い方。どちらが勝敗を左右する？",
        "🏟️ 相手サポーターの声が大きい会場。選手に必要な強さは何？",
        "🏟️ ホームゲームで見たいのは、積極的な攻撃？ 堅実な試合運び？",
        "🏟️ 遠征先での試合。まず注目したいのはピッチ環境？ 対戦相手？",
        "🏟️ 先制した後の戦い方。追加点を狙う？ 主導権を維持する？",
        "🏟️ 追いかける展開で効果的なのは、交代策？ フォーメーション変更？",
        "🏟️ ホームとアウェイで、戦術はどこまで変えるべき？",
        "🏟️ STVVの試合を現地観戦するなら、どこに注目して見たい？",
    ],
}


def publish_fallback(history, now, slot):
    day_key = now.strftime("%Y-%m-%d")
    key = f"fallback_{day_key}_{slot}"

    if key in history["used_posts"]:
        print(f"本日の{slot}枠は投稿済み")
        return False

    topics = FALLBACK_TOPICS[slot]
    index = (
        now.date().toordinal()
        + list(SLOTS.values()).index(slot) * 3
    ) % len(topics)

    titles = {
        "review": "🔎 STVV LAB｜試合の見方",
        "compare": "⚔️ STVV LAB｜比較・考察",
        "data": "STVV LAB｜データの見方",
        "target": "STVV LAB｜攻撃分析",
        "news": "STVV LAB｜ファンの声",
        "vote": "STVV LAB｜みんなに質問",
        "homeaway": "STVV LAB｜次戦に向けて",
    }

    message = (
        f"{titles[slot]}\n\n"
        f"{topics[index]}\n\n"
        "#STVV #シントトロイデン"
    )

    post_to_buffer(message)
    history["used_posts"].append(key)
    save_history(history)
    return True


def try_live_content(history, now, slot):
    try:
        if slot == "news":
            return (
                publish_news(history, now)
                or publish_match(history, now, "result")
            )
        return publish_match(history, now, slot)

    except (
        SourceUnavailable, ValueError,
        KeyError, TypeError, AttributeError
    ) as exc:
        print(
            "データ生成に失敗したため"
            f"常設テーマへ切り替え: {exc}"
        )
        return False


def main():
    now = datetime.now(JST)
    history = load_history()
    manual = (
        os.getenv("GITHUB_EVENT_NAME")
        == "workflow_dispatch"
    )

    print(
        f"STVV LAB {now.isoformat()} / "
        f"{'手動' if manual else '定期'}"
    )

    if manual:
        for slot in (
            "result", "data", "compare", "target",
            "review", "homeaway", "vote"
        ):
            try:
                if publish_match(history, now, slot):
                    return
            except (
                SourceUnavailable, ValueError,
                KeyError, TypeError, AttributeError
            ) as exc:
                print(f"試合取得失敗: {exc}")
                break

        try:
            if publish_news(history, now):
                return
        except (
            SourceUnavailable, ValueError,
            KeyError, TypeError, AttributeError
        ) as exc:
            print(f"ニュース取得失敗: {exc}")

        publish_fallback(history, now, "vote")
        return

    slot = SLOTS.get(now.hour)
    if not slot:
        print("投稿対象の時間ではありません")
        return

    if not try_live_content(history, now, slot):
        publish_fallback(history, now, slot)


if __name__ == "__main__":
    main()
