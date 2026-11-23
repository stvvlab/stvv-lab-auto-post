"""Read-only live official-list discovery probe; never publishes or writes ledgers.

Run from repository root: python -m scripts.probe_live_official_discovery
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo
import requests
from official_sources import scan_articles

EXPECTED_URL = "https://stvv.jp/news/game/20261122_1/"

def main():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    articles, checks = scan_articles(now, requests.Session())
    for check in checks:
        print(check)
    for url, (day, title) in articles:
        print(f"{day} | {url} | {title}")
    if any(check["status"] != "ok" for check in checks):
        raise SystemExit("FAIL: official list acquisition incomplete")
    if date(2026, 11, 22) <= now.date() <= date(2026, 11, 29):
        if EXPECTED_URL not in dict(articles):
            raise SystemExit("FAIL: known Nov 22 match report not extracted")
    print(f"PASS: {len(articles)} eligible articles; no posting performed")

if __name__ == "__main__":
    main()
