"""Adobe Firefly integration: safe, opt-in reviewed-content image staging.

Dry-run by default. Generation never edits the approved manifest or posts to X.
Uses only verified editorial input, and outputs an unreviewed local image.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests

from design_brief import build_brief

TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
GENERATE_URL = "https://firefly-api.adobe.io/v3/images/generate-async"
SCOPE = "openid,AdobeID,session,additional_info,read_organizations,firefly_api,ff_apis"


def approved_status_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "firefly-api.adobe.io" and parsed.path.startswith("/v3/status/")


def request_token(session, client_id, client_secret):
    response = session.post(TOKEN_URL, data={
        "grant_type": "client_credentials", "client_id": client_id,
        "client_secret": client_secret, "scope": SCOPE,
    }, timeout=20)
    response.raise_for_status()
    return response.json()["access_token"]


def generate(session, prompt, client_id, client_secret, *, max_checks=20):
    import time
    token = request_token(session, client_id, client_secret)
    headers = {"x-api-key": client_id, "Authorization": "Bearer " + token,
               "Accept": "application/json", "Content-Type": "application/json"}
    response = session.post(GENERATE_URL, headers=headers,
                            json={"prompt": prompt, "contentClass": "art"}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("statusUrl"):
        url = payload["statusUrl"]
        if not approved_status_url(url):
            raise ValueError("Untrusted Adobe job status URL")
        for _ in range(max_checks):
            result = session.get(url, headers=headers, timeout=30)
            result.raise_for_status()
            payload = result.json()
            if payload.get("status") in ("failed", "error", "canceled"):
                raise RuntimeError("Adobe generation failed")
            if payload.get("status") in ("succeeded", "completed"):
                break
            time.sleep(3)
        else:
            raise TimeoutError("Adobe image job unfinished; never automatically resubmit")
    outputs = payload.get("outputs") or []
    if not outputs or not isinstance(outputs[0], dict):
        raise RuntimeError("Adobe returned no image")
    image = outputs[0].get("image") or {}
    image_url = image.get("url")
    if not image_url or urlparse(image_url).scheme != "https":
        raise RuntimeError("Adobe returned no secure image URL")
    return image_url


def prepare(source_url, caption, history):
    if not isinstance(history, dict) or not isinstance(history.get("publication_log"), list):
        raise ValueError("Publication history required")
    return build_brief(source_url, caption, history)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--caption-file", required=True)
    parser.add_argument("--history", default="posted.json")
    parser.add_argument("--output", default="reports/adobe-firefly-brief.json")
    parser.add_argument("--execute", action="store_true",
                        help="Consume Adobe API only when manually opted in and credentials configured")
    args = parser.parse_args()
    caption = Path(args.caption_file).read_text(encoding="utf-8")
    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    brief = prepare(args.source_url, caption, history)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {"status": "dry_run", "reviewed_asset": False,
              "publication_performed": False, "brief": brief}
    if args.execute:
        if os.getenv("STVV_ADOBE_GENERATION_ENABLED") != "true":
            raise RuntimeError("Adobe image generation is disabled")
        client_id = os.getenv("FIREFLY_SERVICES_CLIENT_ID")
        secret = os.getenv("FIREFLY_SERVICES_CLIENT_SECRET")
        if not client_id or not secret:
            raise RuntimeError("Adobe Firefly API credentials are missing")
        # Keep signed download URLs and access tokens out of persisted reports.
        image_url = generate(requests.Session(), brief["prompt"], client_id, secret)
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        data = response.content
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(data)) as pic:
            pic.verify()
        staged = output.with_suffix(".unreviewed.png")
        with Image.open(BytesIO(data)) as pic:
            pic.convert("RGB").save(staged, format="PNG")
        import hashlib
        result.update(status="generated_requires_human_review",
                      staged_asset=str(staged),
                      sha256=hashlib.sha256(staged.read_bytes()).hexdigest())
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"] + ": no X publication or manifest approval performed")


if __name__ == "__main__":
    main()
