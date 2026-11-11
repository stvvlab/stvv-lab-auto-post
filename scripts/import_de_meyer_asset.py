"""Import only the byte-identical approved JPEG from a temporary HTTPS handoff."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import requests
from scripts.verify_de_meyer_image import ASSET, EXPECTED_SHA256, verify_asset

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "editorial/manual_reservation/de_meyer_image_source.json"

def import_asset():
    info = json.loads(SOURCE.read_text(encoding="utf-8"))
    url = info["url"]
    if urlparse(url).scheme != "https" or urlparse(url).hostname != "at.adobe.com":
        raise ValueError("Unapproved source hostname")
    response = requests.get(url, timeout=50, allow_redirects=True)
    response.raise_for_status()
    raw = response.content
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Source did not deliver exact approved bytes")
    dest = ROOT / ASSET
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return verify_asset(ROOT)  # no re-encoding or overwrite
    dest.write_bytes(raw)
    return verify_asset(ROOT)

if __name__ == "__main__":
    print(json.dumps(import_asset(), ensure_ascii=False))
