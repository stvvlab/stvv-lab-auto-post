"""Opt-in player caricature brief builder. Does not generate images or publish.

Only a previously approved likeness can enter the player-artwork workflow.
Player photos from official sites are reference material, not automatically
licensed assets for publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

def official_profile(url):
    p = urlparse(url)
    return p.scheme == "https" and p.hostname == "stvv.jp" and p.path.startswith("/team-member/") and p.path != "/team-member/"

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()

def prepare_player_artwork(manifest, *, root="."):
    """Produce an unapproved, unpublished brief, never a publish-ready asset."""
    if not isinstance(manifest, dict) or not official_profile(manifest.get("profile_url", "")):
        raise ValueError("A specific HTTPS stvv.jp player profile is required")
    for field in ("player_name", "reference_photo", "approved_portrait", "approved_portrait_sha256"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError("Missing required field: " + field)
    if manifest.get("likeness_approved") is not True:
        raise ValueError("Likeness must be explicitly approved before stylization")
    root = Path(root).resolve()
    paths = {}
    for field in ("reference_photo", "approved_portrait"):
        value = manifest[field]
        candidate = (root / value).resolve()
        if candidate == root or root not in candidate.parents or not candidate.is_file():
            raise ValueError("Missing or unsafe reference path: " + field)
        if candidate.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("Unsupported reference type")
        paths[field] = candidate
    actual = file_hash(paths["approved_portrait"])
    if actual != manifest["approved_portrait_sha256"]:
        raise ValueError("Approved portrait has changed; reapproval required")
    # Numbers and sponsors are never copied from AI-generated imagery.
    label = manifest.get("jersey_number")
    if label is not None and (not isinstance(label, int) or not 0 <= label <= 99):
        raise ValueError("Invalid jersey number")
    return {
        "status": "unreviewed_brief_only",
        "player": manifest["player_name"],
        "official_profile": manifest["profile_url"],
        "reference_photo": str(paths["reference_photo"].relative_to(root)),
        "approved_portrait": str(paths["approved_portrait"].relative_to(root)),
        "approved_portrait_sha256": actual,
        "style": "STVV LAB navy/yellow comic editorial, no speech bubbles",
        "art_direction": "Oversized 2-head-tall caricature, extremely large head and tiny body; expressive playful crazy face. Preserve the exact approved facial identity, eyebrows, nose, lips, hair texture and silhouette. Only expression and body proportions may change. Avoid unrelated monsters and excessive captions.",
        "prompt": "Use the approved portrait as an actual image reference (not text-only recreation). Preserve recognizable facial geometry, hair texture, hairline, and silhouette exactly as shown in the approved portrait; never invent hair type or facial traits. Create a 2-head-tall, intentionally unbalanced STVV LAB football caricature in navy/yellow comic style. Exaggerate expression only. No invented numbers, sponsors, matches, crests or statistics. Leave information text to a verified separate layout stage.",
        "verified_jersey_number": label,
        "publication_allowed": False,
        "required_review": ["image-to-image reference actually supplied", "recognizable likeness", "portrait identity fidelity", "copyright and image-use permission", "text and number accuracy", "mobile crop", "explicit final human review"],
    }

def prepare_player_preview_brief(manifest, *, root="."):
    """Prepare a first-pass likeness brief without requiring a preapproved portrait.

    This returns text instructions only. The reference image must actually be
    supplied to an image-to-image tool later; no tool is called here.
    """
    if not isinstance(manifest, dict) or not official_profile(manifest.get("profile_url", "")):
        raise ValueError("A specific HTTPS stvv.jp player profile is required")
    for field in ("player_name", "reference_photo"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError("Missing required field: " + field)
    root = Path(root).resolve()
    candidate = (root / manifest["reference_photo"]).resolve()
    if (candidate == root or root not in candidate.parents or not candidate.is_file()
            or candidate.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")):
        raise ValueError("Missing or unsafe player reference")
    return {
        "status": "unapproved_first_pass_brief",
        "player": manifest["player_name"],
        "official_profile": manifest["profile_url"],
        "reference_photo": str(candidate.relative_to(root)),
        "reference_photo_sha256": file_hash(candidate),
        "image_generation_performed": False,
        "publication_allowed": False,
        "likeness_approved": False,
        "prompt": (
            "Use the supplied player reference image as an actual image-to-image input. "
            "Create a wildly expressive, deliberately strange-but-cute football caricature: "
            "two-heads-tall, enormously oversized head, extremely tiny body. "
            "Preserve the player's identifiable face geometry, hairline, hairstyle, "
            "eyebrows, nose and mouth from the actual reference; do not invent a generic face. "
            "STVV LAB navy and yellow, dynamic comic editorial style, no speech bubbles. "
            "No logos, sponsors, jersey numbers, scores, dates, fake text or watermarks. "
            "Keep a safe crop and space for separately verified editorial text. "
            "This is an UNAPPROVED REVIEW DRAFT, not a publication asset."
        ),
        "required_review": [
            "confirm reference image may lawfully be used for this derivative work",
            "confirm the reference image was actually passed to image-to-image generation",
            "verify player likeness, hair, face, and distinctive features",
            "verify body proportions and appealing visual variety",
            "verify safe crop and no invented identifiers or text",
            "obtain explicit final image approval before adding any ready card",
            "hash the approved output bytes and independently verify public image delivery",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--brief-for-review", action="store_true",
                   help="Create unapproved first-pass instructions from a local player reference")
    p.add_argument("--root", default=".")
    p.add_argument("--output", default="reports/player-caricature-brief.json")
    args = p.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    result = (prepare_player_preview_brief(manifest, root=args.root)
              if args.brief_for_review else prepare_player_artwork(manifest, root=args.root))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Unapproved artwork instructions written. No image generation, Buffer call or X posting performed.")

if __name__ == "__main__":
    main()
