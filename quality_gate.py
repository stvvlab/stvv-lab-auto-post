#!/usr/bin/env python3
"""STVV LAB: pre-publication content audit (stdlib only).

Usage:
  python quality_gate.py --posts posts.json
  python quality_gate.py --posts posts.json --strict

Without --strict the command only reports problems and exits successfully.
Integrate --strict into publishing only after reviewing existing posts.
"""
import argparse
import json
import re
from pathlib import Path

BLOCKED = ("スポンサー", "協賛", "パートナー契約", "グッズ販売", "販売開始")
GENERIC = ("見ると", "見えてきます", "重要", "追っていきます", "どう評価", "面白いところ")
EVIDENCE = ("source_url", "source", "match_id", "event_id", "official_url")
URL = re.compile(r"^https?://[^\s]+$", re.I)


def audit(post):
    problems = []
    body = post.get("text", "")
    if not isinstance(body, str) or not body.strip():
        return ["missing_text"]
    if len(body) > 280:
        problems.append("over_280_characters")
    if any(word in body for word in BLOCKED):
        problems.append("excluded_promotion")
    if any(word in body for word in GENERIC):
        problems.append("generic_language_review")
    if post.get("type") in {"news", "match", "matchlab", "result", "player"}:
        refs = [post.get(k) for k in EVIDENCE if post.get(k)]
        if not refs:
            problems.append("missing_source_reference")
        if any(k.endswith("url") and post.get(k) and not URL.match(str(post[k]))
               for k in EVIDENCE):
            problems.append("malformed_source_url")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", default="posts.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    data = json.loads(Path(args.posts).read_text(encoding="utf-8"))
    posts = data.get("posts", []) if isinstance(data, dict) else data
    if not isinstance(posts, list):
        raise SystemExit("posts must be a list")
    flagged = 0
    for idx, post in enumerate(posts):
        problems = audit(post) if isinstance(post, dict) else ["not_an_object"]
        if problems:
            flagged += 1
            print(f"POST {idx}: {', '.join(problems)}")
    print(f"Audited {len(posts)} posts; flagged {flagged}.")
    if args.strict and flagged:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
