"""Rename only the exact approved De Meyer JPEG on its isolated upload branch."""
import hashlib
import json
from pathlib import Path

try:
    from scripts.verify_de_meyer_image import ASSET, EXPECTED_SHA256, verify_asset
except ModuleNotFoundError:
    from verify_de_meyer_image import ASSET, EXPECTED_SHA256, verify_asset

ROOT = Path(__file__).resolve().parents[1]

def normalize(root=ROOT):
    root = Path(root)
    target = root / ASSET
    if target.exists() or target.is_symlink():
        proof = verify_asset(root)
        return {"status": "already_canonical", **proof}
    directory = root / "generated"
    if not directory.is_dir():
        raise ValueError("generated/ directory is missing")
    matches = []
    for p in directory.iterdir():
        if not p.is_file() or p.is_symlink() or p.stat().st_size > 8_000_000:
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() == EXPECTED_SHA256:
            matches.append(p)
    if len(matches) != 1:
        raise ValueError("Expected exactly one approved image upload; found " + str(len(matches)))
    source = matches[0]
    source.rename(target)
    try:
        proof = verify_asset(root)
    except Exception:
        target.rename(source)
        raise
    return {"status": "renamed_exact_original", "original_name": source.name, **proof}

if __name__ == "__main__":
    print(json.dumps(normalize(), ensure_ascii=False, indent=2))
