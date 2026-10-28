"""Opt-in, single-image AI pilot. Never publishes or auto-approves.

STVV_IMAGE_PILOT=1 and OPENAI_API_KEY are required. There is no retry.
The local allowance is NOT an account-wide hard spending limit.
"""
import base64
import io
import json
import os
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-image-2"


def select_candidate(report):
    for entry in report.get("drafts", []):
        if (entry.get("status") == "needs_review_and_image"
                and entry.get("reviewed") is False
                and str(entry.get("source_url", "")).startswith("https://stvv.jp/news/")):
            return entry
    return None


def request_background(report, *, http_post=requests.post):
    if os.getenv("STVV_IMAGE_PILOT") != "1":
        raise RuntimeError("Pilot disabled")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("API key missing")
    entry = select_candidate(report)
    if entry is None:
        return {"status": "no_candidate", "generated": 0}
    response = http_post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": "Bearer " + api_key},
        json={"model": MODEL, "size": "1536x1024", "quality": "low", "n": 1,
              "prompt": ("Create an original, editorial graphic background for a "
                         "football fan news card. Modern expressive composition, "
                         "visually appealing, varied colors. No people, no letters, "
                         "no words, no numbers, no logos, no crests, no scores. "
                         "Leave ample clear space for exact Japanese text overlay.")},
        timeout=180,
    )
    response.raise_for_status()
    raw = base64.b64decode(response.json()["data"][0]["b64_json"], validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        image.verify()
    output = ROOT / "generated/draft-previews/ai_pilot.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return {"status": "needs_visual_review", "generated": 1,
            "source_url": entry["source_url"], "preview_path": str(output),
            "approved": False, "published": False}


def main():
    path = ROOT / "reports/simple-post-drafts.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    result = request_background(report)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
