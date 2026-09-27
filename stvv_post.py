import os
import requests

BUFFER_API_URL = "https://api.buffer.com"
CHANNEL_ID = "6ab8fce4ea19ca0bde027d80"

BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

post_text = """🇧🇪 STVVラボ 自動投稿システム稼働テスト

GitHub Actions → Buffer → X の自動投稿テストです。

#STVV #シントトロイデン"""

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
        "text": post_text,
        "channelId": CHANNEL_ID,
        "schedulingType": "automatic",
        "mode": "shareNow"
    }
}

response = requests.post(
    BUFFER_API_URL,
    headers={
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "query": query,
        "variables": variables
    },
    timeout=30,
)

print("Status:", response.status_code)
print(response.text)

response.raise_for_status()
