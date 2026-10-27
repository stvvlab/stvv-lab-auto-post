"""Generate varied, Adobe-free, UNAPPROVED artwork from fresh official fixture inventory.

This module only creates review assets. It never approves imagery, changes the
posting manifest/ledger, calls Buffer, or claims a public X publication.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

JST = timezone(timedelta(hours=9))
W, H = 1200, 1500
NAVY, YELLOW, WHITE = (7, 21, 43), (255, 219, 40), (246, 249, 253)
SOURCE = "https://stvv.jp/game/2026-2027/"


def font(size, bold=True):
    candidates = [
        os.getenv("STVV_CARD_FONT", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for name in candidates:
        if name and Path(name).is_file():
            return ImageFont.truetype(name, size)
    raise RuntimeError("A Japanese-capable Noto CJK font is required; never draw tofu")


def text_width(draw, text, face):
    bounds = draw.textbbox((0, 0), text, font=face)
    return bounds[2] - bounds[0]


def centered(draw, text, y, size, color, max_width=1060, min_size=34):
    # Wrap long Japanese opponent names rather than clipping them off the card.
    face = font(size)
    while text_width(draw, text, face) > max_width and size > min_size:
        size -= 2
        face = font(size)
    if text_width(draw, text, face) <= max_width:
        draw.text(((W - text_width(draw, text, face)) // 2, y), text, font=face, fill=color)
        return
    half = (len(text) + 1) // 2
    for i, line in enumerate((text[:half], text[half:])):
        centered(draw, line, y + i * (min_size + 18), min_size, color, max_width)


def validated_fixture(report, now):
    if not isinstance(report, dict) or not isinstance(report.get("candidates"), list):
        raise ValueError("Complete fixture inventory required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware now required")
    if report.get("source_url") != SOURCE:
        raise ValueError("Unrecognized official schedule source")
    if report.get("status") not in ("fixture_evidence_available", "no_upcoming_unrecorded_league_fixture"):
        raise ValueError("Unverified official schedule inventory status")
    valid = []
    for item in report["candidates"]:
        if not isinstance(item, dict):
            continue
        if (item.get("source_url") != SOURCE
                or item.get("status") != "fixture_evidence_only"
                or item.get("reviewed") is not False
                or item.get("can_publish") is not False
                or item.get("competition") != "Belgian Pro League"
                or item.get("venue") not in ("HOME", "AWAY")
                or not isinstance(item.get("round"), int)
                or not 1 <= item["round"] <= 40
                or not re.fullmatch(r"[0-9a-f]{24}", str(item.get("fixture_id", "")))):
            continue
        opponent = item.get("opponent")
        if (not isinstance(opponent, str) or not 2 <= len(opponent) <= 45
                or re.search(r"[\r\n<>]", opponent)):
            continue
        try:
            kickoff = datetime.fromisoformat(item["kickoff_jst"])
        except (KeyError, ValueError, TypeError):
            continue
        if (kickoff.utcoffset() != timedelta(hours=9)
                or not now.astimezone(JST) < kickoff <= now.astimezone(JST) + timedelta(days=7)):
            continue
        valid.append((kickoff, item))
    return min(valid, key=lambda pair: pair[0])[1] if valid else None


def render(fixture, path, variant):
    if variant not in range(3):
        raise ValueError("Unknown concept")
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(7 + int(11*t), 21 + int(19*t), 43 + int(24*t)))
    if variant == 0:
        # Editorial diagonal: no photo or club crest, only original geometry.
        for x in range(-650, 1550, 230):
            d.polygon([(x, 0), (x+90, 0), (x+760, H), (x+670, H)], fill=(18, 49, 78))
        d.polygon([(0, 420), (1200, 130), (1200, 360), (0, 650)], fill=(26, 62, 93))
        d.line((65, 610, 1135, 610), fill=YELLOW, width=12)
        d.rectangle((0, 0, W, 20), fill=YELLOW)
    elif variant == 1:
        # Abstract stadium floodlights, no claim about the actual venue.
        for cx in (170, 1030):
            for r in (85, 160, 250, 350):
                d.ellipse((cx-r, 350-r, cx+r, 350+r), outline=(31, 69, 100), width=8)
            for dx in (-48, 0, 48):
                d.ellipse((cx+dx-18, 330-18, cx+dx+18, 330+18), fill=YELLOW)
        for y in range(1120, 1500, 62):
            d.line((0, y, W, y), fill=(31, 69, 100), width=4)
        d.rounded_rectangle((54, 590, 1146, 1200), radius=32, fill=(9, 27, 51),
                            outline=YELLOW, width=8)
    else:
        # Opposing panels and pitch perspective: a third visual hierarchy.
        d.polygon([(0, 0), (720, 0), (470, 1500), (0, 1500)], fill=(23, 57, 88))
        d.polygon([(720, 0), (1200, 0), (1200, 1500), (470, 1500)], fill=(244, 205, 30))
        for y in (620, 760, 900, 1040):
            d.line((0, y, W, y+190), fill=(7, 21, 43), width=10)
        d.rounded_rectangle((54, 600, 1146, 1220), radius=28, fill=NAVY,
                            outline=WHITE, width=7)
    d.rounded_rectangle((60, 66, 380, 137), radius=12, fill=YELLOW)
    d.text((84, 76), "STVV LAB", font=font(46), fill=NAVY)
    d.text((65, 190), "BELGIAN PRO LEAGUE", font=font(36), fill=WHITE)
    d.text((65, 265), "FIXTURE / " + str(fixture["round"]).zfill(2),
           font=font(58), fill=YELLOW)
    centered(d, "STVV", 670, 170, WHITE)
    centered(d, "VS", 870, 72, YELLOW)
    centered(d, fixture["opponent"], 1020, 108, WHITE)
    d.line((70, 1265, 1130, 1265), fill=YELLOW, width=6)
    d.text((72, 1305), "HOME" if fixture["venue"] == "HOME" else "AWAY",
           font=font(55), fill=YELLOW)
    d.text((72, 1420), "REVIEW DRAFT / KICKOFF OMITTED", font=font(25), fill=WHITE)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG", optimize=True)
    return path


def prepare(report, output_dir, now):
    fixture = validated_fixture(report, now)
    if fixture is None:
        return {"status": "no_eligible_fixture_for_draft", "reviewed": False,
                "auto_publish": False, "image_generation_performed": False,
                "buffer_called": False, "x_publication_performed": False}
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    variants = []
    images = []
    for index, name in enumerate(("diagonal-editorial", "stadium-light", "split-duel")):
        path = render(fixture, directory / f"fixture_schedule_{index}.png", index)
        images.append(path)
        variants.append({"name": name, "path": str(path),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "dimensions": [W, H], "reviewed": False})
    sheet = Image.new("RGB", (1180, 565), NAVY)
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(images):
        with Image.open(path) as im:
            sheet.paste(im.resize((352, 440)), (20 + i*390, 20))
        draw.text((20 + i*390, 480), variants[i]["name"].upper(),
                  font=font(23), fill=YELLOW)
    draw.text((20, 530), "UNAPPROVED / NO BUFFER OR X POST",
              font=font(21), fill=WHITE)
    contact = directory / "fixture_schedule_contact_sheet.png"
    sheet.save(contact, "PNG", optimize=True)
    # Date is evidence metadata only; kickoff and date do not appear on the artwork.
    local_date = datetime.fromisoformat(fixture["kickoff_jst"]).astimezone(
        ZoneInfo("Europe/Brussels")).date().isoformat()
    caption = (f"⚽ ベルギーリーグ第{fixture['round']}節\n"
               f"STVV 対 {fixture['opponent']}\n"
               "注目するポイントは？\n\n"
               f"公式日程：{SOURCE}")
    return {
        "status": "unapproved_fixture_review_packet", "reviewed": False,
        "auto_publish": False, "image_generation_performed": True,
        "buffer_called": False, "x_publication_performed": False,
        "fixture_id": fixture["fixture_id"], "fixture_round": fixture["round"],
        "fixture_identity": f"belgian-pro-league:2026-2027:round:{fixture['round']}",
        "opponent": fixture["opponent"], "venue": fixture["venue"],
        "source_url": SOURCE, "fixture_date_local_evidence_only": local_date,
        "kickoff_omitted": True, "date_omitted_from_artwork": True,
        "caption_draft": caption, "caption_reviewed": False,
        "variants": variants, "contact_sheet": str(contact),
        "required_review": [
            "Recheck match and round in current official schedule",
            "Reconcile previous posts, Buffer and X before reusing a fixture",
            "Resolve conflicting official kickoff times or keep kickoff omitted",
            "Inspect mobile crop, Japanese text, originality and artwork rights",
            "Approve selected original image and caption explicitly",
            "Register immutable image bytes and integrate strict fixture publication gate",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="reports/fixture-schedule-latest.json")
    parser.add_argument("--output-dir", default="generated/fixture_schedule_review")
    parser.add_argument("--metadata", default="reports/fixture-schedule-review.json")
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = prepare(report, args.output_dir, datetime.now(JST))
    destination = Path(args.metadata)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(result["status"], "images:", len(result.get("variants", [])),
          "publishing: false")


if __name__ == "__main__":
    main()
