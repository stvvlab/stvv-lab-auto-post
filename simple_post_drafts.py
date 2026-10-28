"""Generate conservative, short STVV drafts from already collected official articles.

This produces review candidates only. It never marks an article reviewed,
generates images, reserves Buffer slots or changes the posting ledger.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED = ("game", "team", "uefa-news")
MAX_TITLE = 90


def draft_from_candidate(item):
    if not isinstance(item, dict) or item.get("status") != "needs_editorial_review":
        return None
    url = item.get("source_url")
    title = item.get("official_heading")
    body = item.get("source_body")
    day = item.get("date_jst")
    if not all(isinstance(x, str) for x in (url, title, body, day)):
        return None
    from urllib.parse import urlparse
    parsed = urlparse(url)
    category = parsed.path.split("/")[2] if parsed.path.startswith("/news/") else ""
    if parsed.scheme != "https" or parsed.netloc != "stvv.jp" or category not in ALLOWED:
        return None
    title = re.sub(r"\s+", " ", title).strip()
    if not title or len(title) > MAX_TITLE or len(body) < 60:
        return None
    # Reproduce the headline as an attributed official headline, not an
    # automatically inferred score, injury, availability or match date.
    message = f"📰 STVV公式情報｜{title}\n\n詳細・出典：{url}"
    from text_metrics import x_length
    if x_length(message + "\n\n#STVV #シントトロイデン") > 270:
        return None
    return {"source_url": url, "date_jst": day, "text": message,
            "kind": "official_headline", "status": "needs_review_and_image",
            "reviewed": False, "source_body_present": True}


def build_drafts(inventory):
    if not isinstance(inventory, dict):
        raise ValueError("Invalid inventory")
    items = inventory.get("candidates")
    if not isinstance(items, list):
        raise ValueError("Missing candidates")
    drafts = []
    seen = set()
    for item in items:
        draft = draft_from_candidate(item)
        if draft and draft["source_url"] not in seen:
            drafts.append(draft)
            seen.add(draft["source_url"])
    return {"source_inventory_checked_at": inventory.get("checked_at"),
            "publication_performed": False, "image_generation_performed": False,
            "drafts": drafts, "remaining": ["review headline and body",
            "generate and review an image", "register reviewed manifest card"]}


def main():
    inventory = json.loads((ROOT / "reports/preparation-latest.json").read_text(encoding="utf-8"))
    result = build_drafts(inventory)
    output = ROOT / "reports/simple-post-drafts.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Official headline drafts:", len(result["drafts"]), "— not published")


if __name__ == "__main__":
    main()
