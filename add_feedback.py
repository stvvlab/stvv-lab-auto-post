
"""STVV LAB: manual post feedback registration."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FEEDBACK_FILE = Path("feedback.json")
POSTED_FILE = Path("posted.json")
JST = timezone(timedelta(hours=9))


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} が見つかりません")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="STVV LABの投稿を5段階で評価します"
    )
    parser.add_argument(
        "--post",
        required=True,
        help="投稿履歴のkey（例: daily_2026-10-12_news）",
    )
    parser.add_argument(
        "--rating",
        required=True,
        type=int,
        choices=range(1, 6),
        metavar="1-5",
        help="評価（1〜5）",
    )
    parser.add_argument(
        "--comment",
        default="",
        help="評価理由",
    )
    args = parser.parse_args()

    feedback_data = load_json(FEEDBACK_FILE)
    posted_data = load_json(POSTED_FILE)

    settings = feedback_data.get("settings", {})
    if not settings.get("manual_feedback_enabled", False):
        raise RuntimeError("手動評価が無効になっています")

    publication_log = posted_data.get("publication_log", [])
    target = next(
        (
            post for post in publication_log
            if post.get("key") == args.post
        ),
        None,
    )

    if target is None:
        raise ValueError(
            f"投稿履歴に存在しないkeyです: {args.post}"
        )

    reviews = feedback_data.setdefault("feedback", [])
    if not isinstance(reviews, list):
        raise ValueError("feedbackの形式が不正です")

    review = {
        "post_key": args.post,
        "slot": target.get("slot"),
        "rating": args.rating,
        "comment": args.comment,
        "updated_at": datetime.now(JST).isoformat(),
    }

    # 同じ投稿を再評価した場合は最新評価に更新
    reviews[:] = [
        item for item in reviews
        if item.get("post_key") != args.post
    ]
    reviews.append(review)

    FEEDBACK_FILE.write_text(
        json.dumps(
            feedback_data,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("評価を登録しました")
    print(f"投稿: {args.post}")
    print(f"評価: {args.rating}/5")
    print(f"理由: {args.comment or 'なし'}")


if __name__ == "__main__":
    main()
