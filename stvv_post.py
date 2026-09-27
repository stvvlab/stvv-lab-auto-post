import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BUFFER_API_URL = "https://api.buffer.com"
CHANNEL_ID = "6ab8fce4ea19ca0bde027d80"
NEWS_URL = "https://stvv.jp/news/2026/"

BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]


def get_latest_news():
    response = requests.get(
        NEWS_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    articles = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = " ".join(a.get_text(" ", strip=True).split())

        if "/news/" not in href:
            continue

        if not text:
            continue

        url = urljoin(NEWS_URL, href)

        # 重複を除外
        if any(x["url"] == url for x in articles):
            continue

        # STVVニュースらしいタイトルだけ
        if len(text) < 10:
            continue

        articles.append({
            "title": text,
            "url": url
        })

    return articles[:10]


def create_post(news):
    title = news["title"]

    # X向けに簡潔化
    title = re.sub(r"\s+", " ", title).strip()

    post = f"""🇧🇪 STVV NEWS

{title}

シント＝トロイデンVVの最新情報です。

🔗 {news["url"]}

#STVV #シントトロイデン"""

    return post


def post_to_buffer(text):
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
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "query": query,
            "variables": variables
        },
        timeout=30
    )

    response.raise_for_status()

    result = response.json()
    print(result)


def main():
    news_list = get_latest_news()

    if not news_list:
        print("ニュースが取得できませんでした。")
        return

    latest = news_list[0]

    post = create_post(latest)

    print("投稿内容:")
    print(post)

    post_to_buffer(post)

    print("Bufferへの投稿に成功しました。")


if __name__ == "__main__":
    main()
