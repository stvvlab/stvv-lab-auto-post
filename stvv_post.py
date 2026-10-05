import os
import json
import subprocess
import re
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
]


def is_excluded_news(title):

    normalized = title.lower()

    for keyword in EXCLUDED_KEYWORDS:

        if keyword.lower() in normalized:

            return True

    return False


# ==================================================
# STVV公式ニュース取得
# ==================================================

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

    for a in soup.find_all(
        "a",
        href=True
    ):

        href = a["href"]

        title = " ".join(
            a.get_text(
                " ",
                strip=True
            ).split()
        )

        if "/news/" not in href:
            continue

        if len(title) < 10:
            continue

        if is_excluded_news(title):

            print(
                f"除外ニュース: {title}"
            )

            continue

        url = urljoin(
            NEWS_URL,
            href
        )

        if any(
            item["url"] == url
            for item in news
        ):
            continue

        news.append({
            "title": title,
            "url": url
        })

    return news


# ==================================================
# ニュース投稿
# ==================================================

def create_news_post(article):

    title = article["title"]
    url = article["url"]

    text = (
        "🚨 STVV最新情報 🇧🇪⚽\n\n"
        f"{title}\n\n"
        "今日チェックしておきたい"
        "STVVのニュースです👀\n\n"
        f"🔗 {url}\n\n"
        "#STVV #海外サッカー"
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
# Buffer投稿
# ==================================================

def post_to_buffer(text):

    text = fit_x_length(text)

    print("")
    print("========== 最終投稿 ==========")
    print(text)
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
          }
        }

        ... on MutationError {
          message
        }

      }
    }
    """

    variables = {
        "input": {
            "text": text,
            "channelId": CHANNEL_ID,
            "schedulingType": "automatic",
            "mode": "shareNow"
        }
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

    post_to_buffer(text)

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

    buffer_post = post_to_buffer(
        text
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
