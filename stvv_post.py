import os
import json
import subprocess
import re
import html
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==================================================
# 基本設定
# ==================================================

BUFFER_API_URL = "https://api.buffer.com"
CHANNEL_ID = "6ab8fce4ea19ca0bde027d80"

NEWS_URL = "https://stvv.jp/news/2026/"

POSTED_FILE = "posted.json"
POSTS_FILE = "posts.json"

BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

JST = timezone(timedelta(hours=9))


# ==================================================
# 画像投稿設定
# ==================================================

GITHUB_OWNER = "stvvlab"
GITHUB_REPO = "stvv-lab-auto-post"
IMAGE_PATH = "generated/match_lab.png"

# 実データ画像が完成するまではFalse
ENABLE_IMAGE_POSTS = False

# ニュースには現状のMATCH LAB画像を付けない
IMAGE_POST_TYPES = {
    "player",
    "compare",
    "data",
    "analysis",
    "vote",
    "review",
}


# ==================================================
# 投稿スケジュール
# ==================================================

POST_SCHEDULE = {
    (8, 0): "player",
    (10, 30): "compare",
    (12, 30): "data",
    (15, 30): "analysis",
    (18, 0): "news",
    (21, 0): "vote",
    (23, 0): "review",
}


# ==================================================
# X文字数チェック
# ==================================================

URL_PATTERN = re.compile(r"https?://\S+")


def x_weighted_length(text):

    total = 0
    position = 0

    for match in URL_PATTERN.finditer(text):

        before = text[position:match.start()]

        for char in before:

            if ord(char) <= 0x7F:
                total += 1
            else:
                total += 2

        # XではURLを固定長として扱う
        total += 23

        position = match.end()

    remaining = text[position:]

    for char in remaining:

        if ord(char) <= 0x7F:
            total += 1
        else:
            total += 2

    return total


def fit_x_length(text, max_weight=270):

    text = text.strip()

    weight = x_weighted_length(text)

    print(f"元のX換算文字数: {weight}")

    if weight <= max_weight:
        return text

    suffix = "\n\n#STVV"

    allowed_weight = (
        max_weight
        - x_weighted_length(suffix)
    )

    result = ""

    for char in text:

        candidate = result + char

        if x_weighted_length(candidate) > allowed_weight:
            break

        result = candidate

    result = result.rstrip()

    final_text = result + suffix

    print("文字数制限のため本文を短縮しました。")

    print(
        f"短縮後X換算文字数: "
        f"{x_weighted_length(final_text)}"
    )

    return final_text


# ==================================================
# posted.json
# ==================================================

def load_posted():

    if not os.path.exists(POSTED_FILE):

        return {
            "news": [],
            "used_posts": []
        }

    try:

        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            data = {
                "news": data,
                "used_posts": []
            }

        data.setdefault("news", [])
        data.setdefault("used_posts", [])

        return data

    except Exception as e:

        print(
            f"posted.json読み込みエラー: {e}"
        )

        return {
            "news": [],
            "used_posts": []
        }


def save_posted(posted):

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            posted,
            f,
            ensure_ascii=False,
            indent=2
        )


# ==================================================
# posts.json
# ==================================================

def load_posts():

    if not os.path.exists(POSTS_FILE):

        print("posts.jsonがありません。")

        return []

    try:

        with open(
            POSTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        posts = data.get("posts", [])

        if not isinstance(posts, list):
            return []

        return posts

    except Exception as e:

        print(
            f"posts.json読み込みエラー: {e}"
        )

        return []


# ==================================================
# スポンサー・企業PR除外
# ==================================================

EXCLUDED_KEYWORDS = [
    "スポンサー",
    "パートナー",
    "スポンサー契約",
    "パートナー契約",
    "オフィシャルパートナー",
    "サプライヤー",
    "協賛",
    "キャンペーン",
    "グッズ",
    "商品販売",
    "販売開始",
    "プレゼント",
    "抽選",
    "コラボ商品",
    "新商品",
    "ショップ",
]

# STVV LABで積極的に扱うサッカー情報。
# 公式ニュースでは、この語を含む記事を優先して投稿する。
FOOTBALL_PRIORITY_KEYWORDS = [
    "試合",
    "結果",
    "マッチ",
    "リーグ",
    "順位",
    "勝点",
    "勝ち点",
    "スタメン",
    "先発",
    "メンバー",
    "出場",
    "ゴール",
    "得点",
    "アシスト",
    "選手",
    "監督",
    "コメント",
    "加入",
    "移籍",
    "契約",
    "退団",
    "負傷",
    "復帰",
    "代表",
    "招集",
    "日程",
    "対戦",
    "勝利",
    "敗戦",
    "引き分け",
    "トレーニング",
]


def is_excluded_news(title):

    normalized = title.lower()

    for keyword in EXCLUDED_KEYWORDS:

        if keyword.lower() in normalized:

            return True

    return False


def football_priority_score(title):

    normalized = title.lower()
    score = 0

    # 試合結果・順位は最優先
    very_high = [
        "試合結果",
        "結果",
        "順位",
        "勝点",
        "勝ち点",
        "勝利",
        "敗戦",
        "引き分け",
        "スタメン",
        "先発",
    ]

    high = [
        "試合",
        "マッチ",
        "出場",
        "ゴール",
        "得点",
        "アシスト",
        "選手",
        "監督",
        "加入",
        "移籍",
        "負傷",
        "復帰",
        "代表",
        "招集",
        "日程",
        "対戦",
    ]

    for keyword in very_high:
        if keyword.lower() in normalized:
            score += 10

    for keyword in high:
        if keyword.lower() in normalized:
            score += 3

    for keyword in FOOTBALL_PRIORITY_KEYWORDS:
        if keyword.lower() in normalized:
            score += 1

    return score


# ==================================================
# STVV公式ニュース取得
# ==================================================

# 一覧ページのリンク文字列は、WordPressのcaption等が混ざる場合がある。
# そのため、記事ページを開き、見出し・OGタイトル・titleタグの順で
# 正式なタイトルを取得する。
CAPTION_PATTERN = re.compile(
    r"\[/?caption\b[^\]]*\]",
    re.IGNORECASE
)

NOISE_PATTERN = re.compile(
    r"\b(?:alignnone|aligncenter|alignleft|alignright|attachment_\d+|width=\S+)\b",
    re.IGNORECASE
)


def clean_news_text(value):

    if not value:
        return ""

    value = html.unescape(str(value))
    value = CAPTION_PATTERN.sub(" ", value)
    value = NOISE_PATTERN.sub(" ", value)

    # HTMLタグが文字列として残っていた場合も除去
    value = BeautifulSoup(
        value,
        "html.parser"
    ).get_text(" ", strip=True)

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


def get_article_title(url, fallback_title=""):

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        candidates = []

        # 記事本文のH1を最優先
        h1 = soup.find("h1")

        if h1:
            candidates.append(
                h1.get_text(
                    " ",
                    strip=True
                )
            )

        # SNS共有用の正式タイトル
        og_title = soup.find(
            "meta",
            attrs={
                "property": "og:title"
            }
        )

        if og_title:
            candidates.append(
                og_title.get("content", "")
            )

        # 最後の保険
        if soup.title:
            candidates.append(
                soup.title.get_text(
                    " ",
                    strip=True
                )
            )

        candidates.append(
            fallback_title
        )

        for candidate in candidates:

            title = clean_news_text(
                candidate
            )

            # サイト名がtitleタグに付く場合の簡易除去
            title = re.sub(
                r"\s*[|｜]\s*シント.?トロイデン.*$",
                "",
                title,
                flags=re.IGNORECASE
            ).strip()

            if len(title) >= 8:
                return title

    except Exception as e:

        print(
            f"記事タイトル取得エラー: {url} / {e}"
        )

    return clean_news_text(
        fallback_title
    )


def get_news():

    response = requests.get(
        NEWS_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    news = []
    seen_urls = set()

    for a in soup.find_all(
        "a",
        href=True
    ):

        href = a["href"]

        url = urljoin(
            NEWS_URL,
            href
        )

        # 2026年の「個別ニュース記事」だけを対象にする。
        # /news/2025/ や /news/2026/ の年別一覧、
        # カテゴリ・ページ送り・他年度リンクはすべて除外する。
        normalized_url = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")

        expected_prefix = NEWS_URL.rstrip("/") + "/"

        if not normalized_url.startswith(expected_prefix):
            continue

        relative_path = normalized_url[len(expected_prefix):].strip("/")

        # 2026年トップそのものは記事ではない
        if not relative_path:
            continue

        # 個別記事は1階層のslugだけを許可。
        # category/... や page/... など複数階層は除外。
        if "/" in relative_path:
            continue

        # 年だけのリンクやページ送り等を除外
        if relative_path.isdigit():
            continue

        if relative_path.lower() in {
            "page",
            "category",
            "tag",
            "author",
            "feed",
        }:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        fallback_title = clean_news_text(
            a.get_text(
                " ",
                strip=True
            )
        )

        title = get_article_title(
            url,
            fallback_title
        )

        if len(title) < 8:
            continue

        if is_excluded_news(title):

            print(
                f"除外ニュース: {title}"
            )

            continue

        news.append({
            "title": title,
            "url": url
        })

    # サッカー情報を優先。特に試合結果・順位・スタメン等を上位へ。
    # 同点の場合は公式ページで取得した順序を維持する。
    news.sort(
        key=lambda article: football_priority_score(article["title"]),
        reverse=True
    )

    return news


# ==================================================
# ニュース投稿
# ==================================================

def create_news_post(article):

    title = article["title"]
    url = article["url"]

    text = (
        "🚨 STVV NEWS 🇧🇪⚽\n\n"
        f"{title}\n\n"
        "STVV公式から発表されたニュースをチェック👇\n\n"
        f"🔗 {url}\n\n"
        "#STVV #シントトロイデン"
    )

    return text


# ==================================================
# ストック投稿取得
# ==================================================

def choose_stock_post(
    posts,
    post_type,
    used_posts
):

    candidates = []

    for index, post in enumerate(posts):

        if post.get("type") != post_type:
            continue

        text = post.get("text", "").strip()

        if not text:
            continue

        post_id = f"{post_type}_{index}"

        if post_id in used_posts:
            continue

        candidates.append(
            (post_id, post)
        )

    if not candidates:

        return None, None

    return candidates[0]


# ==================================================
# GitHub画像URL取得
# ==================================================

def get_current_commit_sha():

    try:

        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        sha = result.stdout.strip()

        if not sha:
            return None

        return sha

    except Exception as e:

        print(
            f"GitHubコミットSHA取得エラー: {e}"
        )

        return None


def build_image_url():

    sha = get_current_commit_sha()

    if not sha:

        print(
            "画像URLを作成できないため"
            "テキスト投稿に切り替えます。"
        )

        return None

    url = (
        "https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"{sha}/"
        f"{IMAGE_PATH}"
    )

    return url


def verify_image_url(url):

    if not url:
        return False

    try:

        response = requests.get(
            url,
            timeout=20
        )

        if response.status_code != 200:

            print(
                "画像URL確認失敗: "
                f"HTTP {response.status_code}"
            )

            return False

        content_type = (
            response.headers
            .get("Content-Type", "")
            .lower()
        )

        if not content_type.startswith("image/"):

            print(
                "画像URLが画像として"
                "認識されませんでした。"
            )

            return False

        print(
            "画像URL確認成功"
        )

        return True

    except Exception as e:

        print(
            f"画像URL確認エラー: {e}"
        )

        return False


def get_image_url_for_post(post_type):

    if not ENABLE_IMAGE_POSTS:

        print(
            "画像投稿は現在OFFです。"
        )

        return None

    if post_type not in IMAGE_POST_TYPES:

        print(
            f"{post_type} は"
            "画像添付対象外です。"
        )

        return None

    image_url = build_image_url()

    if not verify_image_url(image_url):

        print(
            "画像を確認できなかったため"
            "テキストのみ投稿します。"
        )

        return None

    print(
        f"投稿画像URL: {image_url}"
    )

    return image_url


# ==================================================
# Buffer投稿
# ==================================================

def post_to_buffer(
    text,
    image_url=None
):

    text = fit_x_length(text)

    print("")
    print("========== 最終投稿 ==========")
    print(text)

    if image_url:
        print("")
        print(
            f"画像: {image_url}"
        )

    print("==============================")
    print("")

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {

        ... on PostActionSuccess {
          post {
            id
            text
            status
            assets {
              id
              mimeType
            }
          }
        }

        ... on MutationError {
          message
        }

      }
    }
    """

    post_input = {
        "text": text,
        "channelId": CHANNEL_ID,
        "schedulingType": "automatic",
        "mode": "shareNow"
    }

    if image_url:

        post_input["assets"] = [
            {
                "image": {
                    "url": image_url
                }
            }
        ]

    variables = {
        "input": post_input
    }

    response = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization":
                f"Bearer {BUFFER_API_KEY}",
            "Content-Type":
                "application/json"
        },
        json={
            "query": query,
            "variables": variables
        },
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    print("Buffer response:")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    if result.get("errors"):

        raise RuntimeError(
            f"Buffer GraphQL error: "
            f"{result['errors']}"
        )

    create_post = (
        result
        .get("data", {})
        .get("createPost")
    )

    if not create_post:

        raise RuntimeError(
            "Buffer createPost response missing: "
            f"{result}"
        )

    if create_post.get("message"):

        raise RuntimeError(
            "Buffer post failed: "
            f"{create_post['message']}"
        )

    post = create_post.get("post")

    if not post:

        raise RuntimeError(
            "Buffer did not create a post: "
            f"{create_post}"
        )

    post_id = post.get("id")

    if not post_id:

        raise RuntimeError(
            "Buffer post ID missing."
        )

    print(
        f"Buffer投稿成功: {post_id}"
    )

    return post


# ==================================================
# posted.jsonをGitHubへ保存
# ==================================================

def commit_posted_file():

    subprocess.run(
        [
            "git",
            "config",
            "user.name",
            "github-actions[bot]"
        ],
        check=True
    )

    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]"
            "@users.noreply.github.com"
        ],
        check=True
    )

    subprocess.run(
        [
            "git",
            "add",
            POSTED_FILE
        ],
        check=True
    )

    result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--quiet"
        ]
    )

    if result.returncode == 0:

        print(
            "posted.jsonに変更なし"
        )

        return

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "Update posted content"
        ],
        check=True
    )

    subprocess.run(
        [
            "git",
            "push"
        ],
        check=True
    )


# ==================================================
# ニュース投稿処理
# ==================================================

def handle_news(posted):

    print(
        "🚨 STVV重要ニュース確認"
    )

    posted_news = posted.get(
        "news",
        []
    )

    news = get_news()

    if not news:

        print(
            "取得できるニュースがありません。"
        )

        return False

    # 初回や履歴消失時に、過去記事を「最新情報」として大量投稿しない。
    # 現在一覧にあるURLを既読として保存し、次回以降の新着だけを対象にする。
    if not posted_news:

        posted["news"] = [
            article["url"]
            for article in news
        ][-300:]

        save_posted(posted)
        commit_posted_file()

        print(
            "ニュース履歴を初期化しました。"
            "過去記事は投稿せず、次回以降の新着から投稿します。"
        )

        return False

    new_article = None

    for article in news:

        if article["url"] not in posted_news:

            new_article = article
            break

    if new_article is None:

        print(
            "投稿対象の新しいニュースはありません。"
        )

        return False

    text = create_news_post(
        new_article
    )

    # ニュース投稿には現在画像を付けない
    post_to_buffer(
        text,
        image_url=None
    )

    posted_news.append(
        new_article["url"]
    )

    # 履歴肥大化防止
    posted["news"] = posted_news[-300:]

    save_posted(posted)

    commit_posted_file()

    print(
        "ニュース投稿完了"
    )

    return True


# ==================================================
# 通常投稿処理
# ==================================================

def handle_stock_post(
    post_type,
    posted
):

    posts = load_posts()

    used_posts = posted.get(
        "used_posts",
        []
    )

    post_id, post = choose_stock_post(
        posts,
        post_type,
        used_posts
    )

    if post is None:

        print(
            f"{post_type} の"
            "未投稿ストックがありません。"
        )

        # 投稿する価値のない枠を
        # 無理に埋めない
        return False

    text = post.get(
        "text",
        ""
    ).strip()

    if not text:

        print(
            "投稿本文が空です。"
        )

        return False

    image_url = get_image_url_for_post(
        post_type
    )

    buffer_post = post_to_buffer(
        text,
        image_url=image_url
    )

    print(
        f"Buffer ID: "
        f"{buffer_post['id']}"
    )

    # Buffer成功後だけ使用済みにする
    used_posts.append(
        post_id
    )

    # 履歴肥大化防止
    posted["used_posts"] = (
        used_posts[-500:]
    )

    save_posted(posted)

    commit_posted_file()

    print(
        f"{post_type} 投稿完了"
    )

    return True


# ==================================================
# MAIN
# ==================================================

def main():

    now = datetime.now(JST)

    hour = now.hour
    minute = now.minute

    print(
        f"現在時刻 JST: {now}"
    )

    print(
        f"実行時刻: {hour:02d}:{minute:02d}"
    )

    posted = load_posted()

    # GitHub Actionsは数分遅れて
    # 起動する場合があるため、
    # 「時」を中心に投稿枠を判定する。
    #
    # 同じ時刻に複数枠は設定しない。

    schedule_by_hour = {
        8: "player",
        10: "compare",
        12: "data",
        15: "analysis",
        18: "news",
        21: "vote",
        23: "review",
    }

    post_type = schedule_by_hour.get(
        hour
    )

    if post_type is None:

        print(
            "現在は投稿時間ではありません。"
        )

        return

    print(
        f"今回の投稿タイプ: {post_type}"
    )

    # ----------------------------------------------
    # 18時：重要ニュース
    # ----------------------------------------------

    if post_type == "news":

        handle_news(
            posted
        )

        return

    # ----------------------------------------------
    # その他6枠
    # ----------------------------------------------

    handle_stock_post(
        post_type,
        posted
    )


if __name__ == "__main__":
    main()
