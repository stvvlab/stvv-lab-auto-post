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

# Intentionally no people or identifiable player faces. Fictional football creatures
# are permitted as non-human graphic motifs, never as factual player depictions.
COMPOSITIONS = (
    "A single oversized off-centre focal symbol with sweeping diagonal movement.",
    "Split-depth perspective with an enormous foreground object and tiny stadium.",
    "Tight editorial crop with strong negative space and a layered inset texture.",
    "Low-angle theatrical scene, irregular borders and a clear central silhouette.",
)
MOTIFS = (
    "A strange-but-adorable fictional football monster, expressive silhouette, 80 percent weird and 20 percent cute.",
    "A surreal football with quirky little limbs, playful but intentionally odd; not a human figure.",
    "A giant stylised boot and curling ink trails, no living character.",
    "An abstract mascot-like creature shaped from stadium lights and football geometry, no human traits.",
    "A dramatic empty goalmouth and handmade symbolic motion marks, no living character.",
)
TEXTURES = (
    "Rough ink cross-hatching and selective halftone, not an all-over dot filter.",
    "Screenprinted layered paper texture with crisp legible type.",
    "Hand-drawn imperfect comic linework with controlled clean negative space.",
    "Bold solid shapes, sparse distressed edges and deliberate editorial contrast.",
)


def visual_variation(source_url, direction, history):
    """Deterministic brief variety; do not advance based on pending/skipped work."""
    records = [p for p in history.get("publication_log", [])
               if isinstance(p, dict) and p.get("art_direction") == direction]
    digest = hashlib.sha256((source_url + "|" + direction).encode()).digest()
    result = {}
    for key, options, field, index in (
            ("composition", COMPOSITIONS, "composition", 0),
            ("motif", MOTIFS, "motif", 1),
            ("texture", TEXTURES, "texture", 2)):
        used = [p.get(field) for p in records if p.get(field) in options]
        counts = Counter(used)
        rotated = list(options)
        shift = digest[index] % len(options)
        rotated = rotated[shift:] + rotated[:shift]
        pool = [v for v in rotated if not used or v != used[-1]]
        result[key] = min(pool, key=lambda v: counts[v])
    return result


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
    variation = visual_variation(source_url, direction, history)
    return {
        "status": "brief_only",
        "art_direction": direction,
        "visual_variation": variation,
        "source_url": source_url,
        "reviewed_caption": reviewed_text,
        "generation_mode": "ChatGPT built-in imagegen",
        "prompt": (
            "Create a complete content-specific STVV LAB editorial image. "
            + ART_DIRECTIONS[direction]
            + " Composition: " + variation["composition"]
            + " Motif: " + variation["motif"]
            + " Texture: " + variation["texture"]
            + " Navy and yellow; restrained red/pink accent; readable on mobile. "
            "Design the composition around the verified point rather than a fixed headline box. "
            "No speech bubbles, real people, human faces, invented players, official crests or unlicensed photos. Fictional non-human creatures only. "
            "Do not add dates, scores, opponent names, charts or statistics beyond the reviewed copy. "
            "If scores are shown, pair each score with its team explicitly; STVV-first means STVV score first. "
            "Use only short accurate English/Japanese wording derived from this reviewed caption:\n"
            + reviewed_text
        ),
        "required_review": ["official facts and team-score pairing", "exact Japanese and digits",
                            "safe crop and mobile readability", "caption-image agreement",
                            "no duplicate source or match", "asset SHA256 and public bytes"],
    }
