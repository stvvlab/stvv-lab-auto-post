import os
import json
import subprocess
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


BUFFER_API_URL = "https://api.buffer.com"
CHANNEL_ID = "6ab8fce4ea19ca0bde027d80"
NEWS_URL = "https://stvv.jp/news/2026/"

POSTED_FILE = "posted.json"
POSTS_FILE = "posts.json"

BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

JST = timezone(timedelta(hours=9))


# ==================================================
# X文字数対策
# ==================================================

URL_PATTERN = re.compile(r"https?://\S+")


def x_weighted_length(text):
    """
    Xの文字数制限を安全側で概算。

    URL = 23
    ASCII文字 = 1
    日本語など = 2

    Buffer側で弾かれないよう、
    280ギリギリではなく270を上限にする。
    """

    total = 0
    position = 0

    for match in URL_PATTERN.finditer(text):

        before = text[position:match.start()]

        for char in before:
            if ord(char) <= 0x7F:
                total += 1
            else:
                total += 2

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

    weight = x_weighted_length(text)

    print(f"元のX換算文字数: {weight}")

    if weight <= max_weight:
        return text

    suffix = "…\n\n#STVV"

    allowed_weight = (
        max_weight
        - x_weighted_length(suffix)
    )

    result = ""

    for char in text:

        candidate = result + char

        if (
            x_weighted_length(candidate)
            > allowed_weight
        ):
            break

        result = candidate

    result = result.rstrip()

    final_text = result + suffix

    print(
        "X文字数制限のため"
        "本文を自動短縮しました。"
    )

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

            return {
                "news": data,
                "used_posts": []
            }

        data.setdefault(
            "news",
            []
        )

        data.setdefault(
            "used_posts",
            []
        )

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

        print(
            "posts.jsonがありません。"
        )

        return []

    with open(
        POSTS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    return data.get(
        "posts",
        []
    )


# ==================================================
# STVVニュース取得
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


def create_news_post(article):

    return f"""🇧🇪 STVV NEWS

{article["title"]}

シント＝トロイデンVVの最新情報です。

🔗 {article["url"]}

#STVV #シントトロイデン"""


# ==================================================
# Buffer投稿
# ==================================================

def post_to_buffer(text):

    text = fit_x_length(text)

    print("最終投稿内容:")
    print(text)

    print(
        f"最終X換算文字数: "
        f"{x_weighted_length(text)}"
    )

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

    # GraphQLエラー
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

    # Bufferが投稿を拒否
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
            "Buffer post ID missing: "
            f"{post}"
        )

    print(
        f"Buffer投稿成功: {post_id}"
    )

    return post


# ==================================================
# ストック投稿選択
# ==================================================

def choose_stock_post(
    posts,
    post_type,
    used_posts
):

    for index, post in enumerate(posts):

        if post.get("type") != post_type:
            continue

        post_id = (
            f"{post_type}_{index}"
        )

        if post_id in used_posts:
            continue

        return post_id, post

    return None, None


# ==================================================
# GitHubへposted.json保存
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
        ],
        capture_output=True
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
# MAIN
# ==================================================

def main():

    now = datetime.now(JST)

    hour = now.hour

    print(
        f"現在時刻 JST: {now}"
    )

    posted = load_posted()

    posted_news = posted.get(
        "news",
        []
    )

    used_posts = posted.get(
        "used_posts",
        []
    )

    posts = load_posts()


    # ----------------------------------------------
    # 08:00 NEWS
    # ----------------------------------------------

    if hour == 8:

        print(
            "8時：STVVニュース確認"
        )

        news = get_news()

        new_article = None

        for article in news:

            if (
                article["url"]
                not in posted_news
            ):

                new_article = article
                break

        if new_article is None:

            print(
                "新しいニュースはありません。"
            )

            return

        text = create_news_post(
            new_article
        )

        print("投稿内容:")
        print(text)

        # 成功するまでposted.jsonには書かない
        post_to_buffer(text)

        posted_news.append(
            new_article["url"]
        )

        posted["news"] = (
            posted_news
        )

        save_posted(posted)

        commit_posted_file()

        print(
            "ニュース投稿完了"
        )

        return


    # ----------------------------------------------
    # 12:00 PLAYER
    # ----------------------------------------------

    if hour == 12:

        post_type = "player"


    # ----------------------------------------------
    # 18:00 MATCH LAB
    # ----------------------------------------------

    elif hour == 18:

        post_type = "matchlab"


    # ----------------------------------------------
    # 21:00 LAB
    # ----------------------------------------------

    elif hour == 21:

        post_type = "lab"


    else:

        print(
            "投稿時間ではありません。"
        )

        return


    # ----------------------------------------------
    # 投稿ストック取得
    # ----------------------------------------------

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

        return


    text = post["text"]

    print("投稿内容:")
    print(text)


    # ----------------------------------------------
    # Buffer投稿
    # ----------------------------------------------

    buffer_post = post_to_buffer(
        text
    )

    print(
        f"Buffer ID: "
        f"{buffer_post['id']}"
    )


    # ----------------------------------------------
    # 本当に成功した後だけ投稿済みにする
    # ----------------------------------------------

    used_posts.append(
        post_id
    )

    posted["used_posts"] = (
        used_posts
    )

    save_posted(posted)

    commit_posted_file()

    print(
        f"{post_type} 投稿完了"
    )


if __name__ == "__main__":
    main()
