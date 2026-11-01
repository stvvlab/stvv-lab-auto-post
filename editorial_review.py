"""Read-only editorial improvement report. Does not publish or change history."""
import argparse
import json
from pathlib import Path
from editorial_score import evaluate

SUGGESTIONS = {
    "accuracy": "公式出典と日時・選手名・スコアを再確認",
    "analysis": "具体的な試合局面・比較根拠を補強",
    "engagement": "冒頭の見どころと読者への問いを改善",
    "clarity": "冗長な表現を短縮し主題を明確化",
    "visual": "審査済み画像の視認性と本文との整合を確認",
    "variety": "直近投稿と切り口・構成の重複を見直す",
}


def review(data):
    if not isinstance(data, dict):
        raise ValueError("review input must be an object")
    ratings = data.get("ratings", {})
    result = evaluate(ratings, kind=data.get("kind", "news"),
                      text_only=data.get("text_only", False))
    if result["status"] == "unscored":
        result["suggestions"] = ["未評価項目を確認: " + ", ".join(result["missing"])]
    else:
        result["suggestions"] = [
            SUGGESTIONS[k] for k, v in sorted(ratings.items(), key=lambda item: item[1])
            if v < 0.8
        ][:3]
    result["note"] = "助言のみ。投稿可否は既存の独立した安全ゲートが決定"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_json", help="reviewer-supplied JSON; never a post command")
    args = parser.parse_args()
    payload = json.loads(Path(args.review_json).read_text(encoding="utf-8"))
    print(json.dumps(review(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
