import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BUFFER_API_URL = "https://api.buffer.com"
CHANNEL_ID = "6ab8fce4ea19ca0bde027d80"
NEWS_URL = "https://stvv.jp/news/2026/"
POSTED_FILE = "posted.json"

BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []

    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)


def get_news():
    response = requests.get(
        NEWS_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    news = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = " ".join(a.get_text(" ", strip=True).split())

        if "/news/" not in href:
            continue

        if len(title) < 10:
            continue

        url = urljoin(NEWS_URL, href)

        if any(item["url"] == url for item in news):
            continue

        news.append({
            "title": title,
            "url": url
        })

    return news


def create_post(article):
    return f"""🇧🇪 STVV NEWS

{article["title"]}

シント＝トロイデンVVの最新情報です。

🔗 {article["url"]}

#STVV #シントトロイデン"""


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

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result


def main():
    posted = load_posted()
    news = get_news()

    if not news:
        print("ニュースが見つかりませんでした。")
        return

    # 新しい記事を探す
    new_article = None

    for article in news:
        if article["url"] not in posted:
            new_article = article
            break

    # 新着なし
    if new_article is None:
        print("新しいニュースはありません。")
        return

    post_text = create_post(new_article)

    print("投稿内容:")
    print(post_text)

    result = post_to_buffer(post_text)

    print("Buffer投稿成功:")
    print(result)

    # 投稿済みとして記録
    posted.append(new_article["url"])
    save_posted(posted)

    print("投稿済みURLを記録しました。")


if __name__ == "__main__":
    main()
