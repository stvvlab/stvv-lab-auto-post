"""Compatibility guard: paid image APIs are not authorized for STVV LAB.

Prepare complete artwork with ChatGPT built-in imagegen, visually review it,
and commit the asset and editorial/imagegen_cards.json together instead.
"""
import os


def build_art_background(slot, day, variant, destination, ordinal=0):
    """Never contact an image API or silently substitute legacy artwork."""
    if os.getenv("STVV_AI_ART_ENABLED", "false").lower() == "true":
        raise RuntimeError(
            "Paid image API generation is disabled by policy; "
            "use a reviewed ChatGPT built-in imagegen manifest asset"
        )
    return None
