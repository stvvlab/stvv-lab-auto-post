"""Stage a local reviewed image for a single manual draft; never publish.

Usage:
  python scripts/stage_manual_image.py IMAGE_PATH
Writes a local staging report with digest/dimensions and a copy of the image.
No GitHub, Buffer, or X network calls are made.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "generated" / "manual_ohl_20261102.png"
REPORT = ROOT / "editorial" / "manual_ohl_20261102_image_metadata.json"

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/stage_manual_image.py IMAGE_PATH")
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file():
        raise SystemExit("Image not found")
    with Image.open(source) as im:
        im.verify()
    with Image.open(source) as im:
        width, height = im.size
        if im.format not in {"PNG", "JPEG"}:
            raise SystemExit("Only PNG/JPEG supported")
        if width < 600 or height < 400:
            raise SystemExit("Image resolution too small")
        rgb = im.convert("RGB")
        DEST.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(DEST, "PNG")
    digest = hashlib.sha256(DEST.read_bytes()).hexdigest()
    data = {"status": "staged_unreviewed_do_not_publish",
            "asset_path": DEST.relative_to(ROOT).as_posix(),
            "dimensions": [width, height], "sha256": digest,
            "required_next_steps": [
                "Visually verify exact Japanese time and fixture against official source",
                "Commit image bytes and metadata together",
                "Perform existing publication safety checks before any Buffer send"]}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
