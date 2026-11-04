"""Fail-closed verification for the approved De Meyer news image."""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSET = Path("generated/de_meyer_departure_20261104.png")
EXPECTED_SHA256 = "d005a530f7586bc7290fac1050b96a6226410b2d9d74e5474b3ca8e1eba7250c"
EXPECTED_SIZE = (1672, 941)

def verify_asset(root=ROOT):
    path = Path(root) / ASSET
    if path.is_symlink() or not path.is_file():
        raise ValueError("Approved original PNG is missing or is a symlink")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Wrong image bytes; do not substitute or re-encode")
    with Image.open(path) as im:
        if im.format != "PNG" or im.size != EXPECTED_SIZE:
            raise ValueError("Wrong image type or dimensions")
        im.verify()
    return {"asset_path": ASSET.as_posix(), "sha256": digest,
            "dimensions": list(EXPECTED_SIZE), "bytes": len(raw),
            "verified": True, "publication_approved": False}

if __name__ == "__main__":
    print(json.dumps(verify_asset(), ensure_ascii=False, indent=2))
