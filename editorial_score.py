"""Advisory editorial scorecard; never authorizes or blocks publication.

Scores are supplied by a reviewer, not inferred from keywords or length.
Existing safety, source, image and delivery gates remain authoritative.
"""
from dataclasses import dataclass

WEIGHTS = {
    "accuracy": 25,
    "analysis": 20,
    "engagement": 15,
    "clarity": 15,
    "visual": 15,
    "variety": 10,
}
TARGETS = {"news": 85, "match": 85, "player": 90,
           "recap": 90, "feature": 95}


def evaluate(ratings, *, kind="news", text_only=False):
    """Return advisory score or unscored status for incomplete review.

    Each supplied rating is a 0..1 reviewer assessment. Missing dimensions
    are not silently awarded points. Text-only excludes visual and renormalizes.
    """
    if kind not in TARGETS:
        raise ValueError("unknown editorial type")
    weights = {k: v for k, v in WEIGHTS.items()
               if not (text_only and k == "visual")}
    if not isinstance(ratings, dict):
        raise ValueError("ratings must be a mapping")
    unknown = set(ratings) - set(weights)
    if unknown:
        raise ValueError("unexpected rating dimensions: " + ", ".join(sorted(unknown)))
    for value in ratings.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError("ratings must be numbers from 0 to 1")
    missing = sorted(set(weights) - set(ratings))
    if missing:
        return {"status": "unscored", "missing": missing, "target": TARGETS[kind],
                "publication_decision": "unchanged"}
    score = round(sum(weights[k] * ratings[k] for k in weights) /
                  sum(weights.values()) * 100, 1)
    return {"status": "target_met" if score >= TARGETS[kind] else "improve",
            "score": score, "target": TARGETS[kind],
            "publication_decision": "unchanged"}
