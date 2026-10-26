"""Plan varied built-in imagegen artwork; never call a paid API or publish.

The preparation agent supplies verified copy, generates with ChatGPT imagegen,
reviews the finished image, then commits image bytes and the reviewed manifest.
"""
import hashlib
from collections import Counter
from urllib.parse import urlparse

ART_DIRECTIONS = {
    "comic-cover": "Bold comic cover, one strong focal point, dimensional English title and a short Japanese accent.",
    "ink-poster": "Expressive hand-inked football poster, asymmetrical balance and generous calm negative space.",
    "print-collage": "Retro football magazine collage, cut-paper shapes, halftone and restrained editorial captions.",
    "stadium-graphic": "Graphic novel empty-stadium illustration, dramatic perspective, restrained textured ink.",
}


def choose_art_direction(history, source):
    """Balance confirmed artwork use; pending or skipped items do not advance it."""
    used = [p.get("art_direction") for p in history.get("publication_log", [])
            if isinstance(p, dict) and p.get("art_direction") in ART_DIRECTIONS]
    counts = Counter(used)
    names = list(ART_DIRECTIONS)
    offset = int(hashlib.sha256(source.encode()).hexdigest()[:8], 16) % len(names)
    ordered = names[offset:] + names[:offset]
    pool = [name for name in ordered if not used or name != used[-1]]
    return min(pool, key=lambda name: counts[name])


def build_brief(source_url, reviewed_text, history):
    """Return a design brief, not a ready card or a factual verification result."""
    source = urlparse(source_url)
    if (source.scheme != "https" or source.netloc != "stvv.jp"
            or not source.path.startswith("/news/")):
        raise ValueError("Use a verified Japanese official article URL")
    if not isinstance(reviewed_text, str) or source_url not in reviewed_text:
        raise ValueError("Reviewed caption must contain its exact source URL")
    direction = choose_art_direction(history, source_url)
    return {
        "status": "brief_only",
        "art_direction": direction,
        "source_url": source_url,
        "reviewed_caption": reviewed_text,
        "generation_mode": "ChatGPT built-in imagegen",
        "prompt": (
            "Create a complete content-specific STVV LAB editorial image. "
            + ART_DIRECTIONS[direction]
            + " Navy and yellow; restrained red/pink accent; readable on mobile. "
            "Design the composition around the verified point rather than a fixed headline box. "
            "No speech bubbles, people, faces, invented players, official crests or unlicensed photos. "
            "Do not add dates, scores, opponent names, charts or statistics beyond the reviewed copy. "
            "If scores are shown, pair each score with its team explicitly; STVV-first means STVV score first. "
            "Use only short accurate English/Japanese wording derived from this reviewed caption:\n"
            + reviewed_text
        ),
        "required_review": ["official facts and team-score pairing", "exact Japanese and digits",
                            "safe crop and mobile readability", "caption-image agreement",
                            "no duplicate source or match", "asset SHA256 and public bytes"],
    }
