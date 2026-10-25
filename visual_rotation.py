"""Safe, deterministic visual rotation for STVV LAB posts.

Only approved renderer variants are eligible. Future illustrated styles must
be explicitly implemented and audited before joining APPROVED_VARIANTS.
"""
from collections import Counter

APPROVED_VARIANTS = ("stadium", "split", "poster")
VISUAL_POLICY = {
    "brand": "STVV LAB",
    "english_first": True,
    "japanese_accent": True,
    "speech_bubbles": False,
    "invent_match_facts": False,
    "unapproved_faces": False,
    "future_art_directions": (
        "retro-underground-comic",
        "quirky-friendly-monster",
        "surreal-collage",
        "vintage-cartoons",
        "graphic-novel",
        "printmaking",
        "football-silhouettes",
        "abstract-pop",
        "dramatic-match-action",
        "hand-drawn-characters",
        "retro-football-magazine",
        "editorial-data-art",
    ),
}


def choose_variant(history):
    """Prefer a different variant than the last post, balancing historic use.

    Count only confirmed submissions; pending posts cannot consume a design.
    Legacy publication_log entries may lack a variant. For those, preserve
    the previous len(log) % 3 rotation to avoid migration churn.
    """
    published = [x for x in history.get("publication_log", []) if isinstance(x, dict)]
    explicit = [x.get("visual_variant") for x in published
                if x.get("visual_variant") in APPROVED_VARIANTS]
    if not explicit:
        return APPROVED_VARIANTS[len(published) % len(APPROVED_VARIANTS)]
    counts = Counter(explicit)
    last = explicit[-1]
    pool = [name for name in APPROVED_VARIANTS if name != last]
    return min(pool, key=lambda name: (counts[name], APPROVED_VARIANTS.index(name)))
