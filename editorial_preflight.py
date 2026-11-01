"""Offline candidate review: safety decision plus advisory editorial score.

This tool never submits, schedules, edits or reserves posts.
"""
import argparse
import json
from pathlib import Path
from quality_gate import classify
from editorial_review import review


def preflight(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    post = candidate.get("post")
    if not isinstance(post, dict):
        raise ValueError("candidate.post must be an object")
    safety = classify(post)
    assessment = candidate.get("review")
    editorial = review(assessment) if assessment is not None else {
        "status": "unscored", "suggestions": ["編集評価は未入力"],
        "publication_decision": "unchanged"
    }
    return {
        "safety_audit": safety,
        "editorial": editorial,
        "publication_decision": safety["status"],
        "note": "オフライン事前確認のみ。公式出典・重複・画像・配信の独立ゲートは別途必須",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_json")
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate_json).read_text(encoding="utf-8"))
    print(json.dumps(preflight(candidate), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
