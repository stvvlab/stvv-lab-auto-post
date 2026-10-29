"""Fail-closed verification of the user-approved OH Leuven announcement PNG.

Does not approve publication, change manifest, send Buffer posts or use an API.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSET = Path("generated/ohl_match_announcement_20261102.png")
EXPECTED_SHA256 = "81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5"
EXPECTED_SIZE = (1448, 1086)


def verify_asset(root=ROOT):
    path = Path(root) / ASSET
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original approved PNG is missing or is a symlink")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Wrong image bytes; do not substitute or re-encode the approved PNG")
    with Image.open(path) as im:
        if im.format != "PNG" or im.size != EXPECTED_SIZE:
            raise ValueError("Wrong image type/dimensions")
        im.verify()
    return {"asset_path": ASSET.as_posix(), "sha256": digest,
            "dimensions": list(EXPECTED_SIZE), "bytes": len(raw),
            "verified": True, "publication_approved": False}


def main():
    print(json.dumps(verify_asset(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
