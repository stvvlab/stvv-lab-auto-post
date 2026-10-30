#!/usr/bin/env python3
"""Single-post preflight for publishing integrations.

Reads one JSON post from stdin. Exit 0 = eligible for publishing;
exit 1 = blocked or invalid. JSON status is returned on stdout.
No network calls and no posts are published.
"""
import json
import sys
from quality_gate import audit, CRITICAL


def main():
    try:
        post = json.load(sys.stdin)
        if not isinstance(post, dict):
            raise ValueError("Post must be a JSON object")
        findings = audit(post)
        blocking = [p for p in findings if p in CRITICAL]
        warnings = [p for p in findings if p not in CRITICAL]
        decision = "block" if blocking else ("pass_with_warnings" if warnings else "pass")
        print(json.dumps({"allowed": not blocking, "decision": decision,
                          "blocking": blocking, "warnings": warnings},
                         ensure_ascii=False))
        return 1 if blocking else 0
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"allowed": False, "decision": "block",
                          "blocking": ["invalid_input"], "warnings": [],
                          "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
