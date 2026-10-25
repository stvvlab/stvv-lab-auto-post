"""Optional image-generation backgrounds for verified text-only STVV cards.

Image AI is forbidden from producing facts, stats, club badges or typography.
The existing deterministic renderer overlays all approved source text.
"""
import base64
import io
import os
from pathlib import Path

import requests
from PIL import Image, ImageOps
from visual_rotation import VISUAL_POLICY

DIRECTIONS = VISUAL_POLICY["future_art_directions"]


def build_art_background(slot, day, variant, destination, ordinal=0):
    """Return a validated local background or None if API not configured.

    API failures fail closed: caller must *not* publish any AI-generated image
    on a partial/invalid response. Existing verified static renderer remains.
    """
    key = os.getenv("OPENAI_API_KEY")
    if os.getenv("STVV_AI_ART_ENABLED", "false").lower() != "true" or not key:
        return None
    direction = DIRECTIONS[ordinal % len(DIRECTIONS)]
    prompt = (
        "Original professional retro comic book illustration BACKGROUND for "
        "a Japanese fan-made football data magazine about Sint-Truiden, Belgium. "
        f"Artwork direction: {direction}. "
        "Use expressive imperfect hand-inked characters, sometimes charmingly "
        "weird goofy monsters, but vary species, expressions, poses and linework. "
        "Football stadium, kinetic motion, 60s-70s underground comics, vintage "
        "halftone, screenprint textures, rich clean yellow and navy blue, white "
        "negative space. Prioritize safe readability: keep center-right "
        "and lower third subdued so text overlays are clear. NO words, letters, "
        "numbers, logos, watermarks, speech bubbles, team badges, scoreboards, "
        "sports results or brand/sponsor markings. No specific real person. "
        f"Card topic is {slot}; layout variation {variant}. "
        "Creative editorial art only, no factual claims."
    )
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": os.getenv("STVV_IMAGE_MODEL", "gpt-image-2.5-flare"),
              "prompt": prompt, "size": "1536x1024",
              "quality": os.getenv("STVV_IMAGE_QUALITY", "medium"),
              "output_format": "png", "n": 1},
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    encoded = data["data"][0]["b64_json"]
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 20_000_000:
        raise ValueError("Generated image exceeds safety size cap")
    with Image.open(io.BytesIO(raw)) as original:
        original.verify()
    with Image.open(io.BytesIO(raw)) as original:
        if original.format != "PNG":
            raise ValueError("Unexpected generated image format")
        if min(original.size) < 768:
            raise ValueError("Generated image is too small")
        art = ImageOps.fit(original.convert("RGB"), (1374, 1145))
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        art.save(path, "PNG", optimize=True)
        return path
