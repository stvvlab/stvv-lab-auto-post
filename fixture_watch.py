"""Read-only cross-check of two official club fixture kick-off listings.

This module never approves an image, caption, reservation, or publication.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
FIXTURE_DATE = date(2026, 11, 1)
SOURCES = {
    "stvv": "https://stvv.com/nl/wedstrijden?timeframe=upcoming",
    "ohl": "https://ohleuven.com/teams/a-ploeg/kalender/",
    "stvv_jp": "https://stvv.jp/news/event/20261002_2/",
}
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")


def page_text(markup):
    soup = BeautifulSoup(markup, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return " ".join(soup.stripped_strings)


def extract_stvv(markup):
    text = page_text(markup)
    found = set()
    for match in re.finditer(r"\b1\s+november\s+2026\b", text, re.I):
        nearby = text[match.end():match.end() + 450]
        teams = re.search(r"\bSTVV\b(?P<middle>.{0,220}?)\bOH Leuven\b",
                          nearby, re.I)
        if teams:
            found.update(TIME_RE.findall(teams.group("middle")))
    if len(found) != 1:
        raise ValueError("STVV listing fixture time missing or ambiguous")
    return found.pop()


def extract_ohl(markup):
    text = page_text(markup)
    found = set()
    for match in re.finditer(r"\b01/11/2026\s*-\s*(\d{1,2}:[0-5]\d)\b", text):
        nearby = text[match.end():match.end() + 340]
        if ("A-Team" in nearby[:120] and
                re.search(r"\bSTVV\b", nearby, re.I) and
                re.search(r"\bOH Leuven\b", nearby, re.I)):
            found.add(match.group(1).zfill(5))
    if len(found) != 1:
        raise ValueError("OHL listing fixture time missing or ambiguous")
    return found.pop()



def extract_stvv_jp(markup):
    text = page_text(markup)
    found = set()
    for match in re.finditer(
            r"2026年11月1日\s*[（(]日[)）]\s*(\d{1,2})時([0-5]\d)分キックオフ",
            text):
        nearby = text[match.end():match.end() + 180]
        if ("ベルギー時間" in nearby and "STVV" in nearby and
                "OHルーヴェン" in nearby):
            found.add(f"{int(match.group(1)):02d}:{match.group(2)}")
    if len(found) != 1:
        raise ValueError("Japanese official fixture time missing or ambiguous")
    return found.pop()


def fetch_official(session, url):
    expected = urlparse(url).hostname
    if expected not in {"stvv.com", "ohleuven.com", "stvv.jp"} or urlparse(url).scheme != "https":
        raise ValueError("Unapproved fixture source")
    response = session.get(url, timeout=20)
    response.raise_for_status()
    final = urlparse(response.url)
    if final.scheme != "https" or final.hostname not in {expected, "www." + expected}:
        raise ValueError("Official fixture source redirected elsewhere")
    if len(response.content) > 2_000_000:
        raise ValueError("Fixture page exceeds safe size")
    return response.text


def build_report(session, now):
    report = {
        "checked_at": now.isoformat(),
        "fixture_date_local": FIXTURE_DATE.isoformat(),
        "fixture": "STVV - OH Leuven",
        "source_times_local": {},
        "source_checks": [],
        "can_publish_kickoff_time": False,
        "can_publish_fixture_card": False,
        "publication_performed": False,
        "image_generation_performed": False,
        "buffer_called": False,
    }
    if now.date() > FIXTURE_DATE:
        report["status"] = "fixture_expired_no_publication"
        return report
    for name, url in SOURCES.items():
        try:
            markup = fetch_official(session, url)
            value = {"stvv": extract_stvv, "ohl": extract_ohl,
                     "stvv_jp": extract_stvv_jp}[name](markup)
            report["source_times_local"][name] = value
            report["source_checks"].append({"source": name, "url": url, "status": "ok"})
        except (requests.RequestException, ValueError, AttributeError) as error:
            report["source_checks"].append({
                "source": name, "url": url, "status": "unverified",
                "error_type": type(error).__name__,
            })
    times = report["source_times_local"]
    if len(times) != len(SOURCES):
        report["status"] = "source_incomplete_block_kickoff"
    elif len(set(times.values())) > 1:
        report["status"] = "official_sources_disagree_block_kickoff"
    else:
        report["status"] = "sources_agree_manual_review_required"
    report["note"] = (
        "Official fixture listings are evidence, not publishing instructions. "
        "Even agreement does not authorize a caption or image. "
        "Do not guess or silently select a kick-off time."
    )
    return report


def main():
    with requests.Session() as session:
        report = build_report(session, datetime.now(timezone.utc))
    output = ROOT / "reports/fixture-watch-latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("FIXTURE_WATCH " + json.dumps({
        "status": report["status"], "source_times_local": report["source_times_local"]
    }))
    return report


if __name__ == "__main__":
    main()
