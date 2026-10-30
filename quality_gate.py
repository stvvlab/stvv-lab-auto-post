#!/usr/bin/env python3
"""STVV LAB: pre-publication content audit (stdlib only).

Usage:
  python quality_gate.py --posts posts.json
  python quality_gate.py --posts posts.json --strict
  python quality_gate.py --posts posts.json --strict-all

By default, findings are reported without failing the command.
--strict and --enforce-critical fail only on publish-blocking findings.
--strict-all explicitly opts into failing on stylistic warnings too.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from text_metrics import x_length

BLOCKED = ("スポンサー", "協賛", "パートナー契約", "グッズ販売", "販売開始")
GENERIC = ("見ると", "見えてきます", "重要", "追っていきます", "どう評価", "面白いところ")
EVIDENCE = ("source_url", "source", "match_id", "event_id", "official_url")
URL = re.compile(r"^https?://[^\s]+$", re.I)


def valid_source_url(value):
    if not isinstance(value, str) or not URL.fullmatch(value):
        return False
    try:
        parsed = urlparse(value)
        return bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def audit(post, *, max_length=280):
    if not isinstance(post, dict):
        return ["not_an_object"]
    problems = []
    body = post.get("text", "")
    if not isinstance(body, str) or not body.strip():
        return ["missing_text"]
    if x_length(body) > 280:
        problems.append("over_280_characters")
    promotion_mentioned = any(word in body for word in BLOCKED)
    if promotion_mentioned:
        # Editorial topic warning, not a factual or delivery safety failure.
        problems.append("excluded_promotion")
    if any(word in body for word in GENERIC):
        problems.append("generic_language_review")
    if max_length < 280 and x_length(body) > max_length:
        problems.append("over_safe_x_length")
    if post.get("type") in {"news", "match", "matchlab", "result", "player"}:
        refs = [post.get(k) for k in EVIDENCE if post.get(k)]
        if not refs:
            problems.append("missing_source_reference")
        if any(k.endswith("url") and post.get(k) and not valid_source_url(post[k])
               for k in EVIDENCE):
            problems.append("malformed_source_url")
    # A promotional claim still needs a traceable URL, even in vote/recap slots.
    # Verified-source, image, novelty and delivery gates remain separate.
    if promotion_mentioned and not any(
            valid_source_url(post.get(key)) for key in ("source_url", "official_url", "source")):
        if "missing_source_reference" not in problems:
            problems.append("missing_source_reference")
    return problems


CRITICAL = {"missing_text", "over_280_characters", "over_safe_x_length",
            "missing_source_reference", "malformed_source_url", "not_an_object"}


def can_publish(post):
    """Fail closed on critical issues; stylistic warnings remain nonblocking."""
    return not any(problem in CRITICAL for problem in audit(post))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", default="posts.json")
    parser.add_argument("--strict", action="store_true",
                        help="Fail only on publish-blocking findings; warnings are advisory")
    parser.add_argument("--strict-all", action="store_true",
                        help="Opt into failing on all findings, including stylistic warnings")
    parser.add_argument("--enforce-critical", action="store_true",
                        help="Exit with error only for publish-blocking findings")
    args = parser.parse_args()
    data = json.loads(Path(args.posts).read_text(encoding="utf-8"))
    posts = data.get("posts", []) if isinstance(data, dict) else data
    if not isinstance(posts, list):
        raise SystemExit("posts must be a list")
    flagged = 0
    critical_count = 0
    for idx, post in enumerate(posts):
        problems = audit(post) if isinstance(post, dict) else ["not_an_object"]
        if problems:
            flagged += 1
            if any(p in CRITICAL for p in problems):
                critical_count += 1
            print(f"POST {idx}: {', '.join(problems)}")
    print(f"Audited {len(posts)} posts; flagged {flagged}; "
          f"publish-blocking {critical_count}.")
    if (args.enforce_critical or args.strict) and critical_count:
        raise SystemExit(1)
    if args.strict_all and flagged:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
