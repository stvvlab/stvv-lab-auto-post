# STVV LAB creative preview bridge (Adobe-free)

This is a **manual image handoff** from an original image produced outside GitHub
(e.g. ChatGPT built-in image generation) to a local, reproducible review poster.
GitHub Actions cannot call ChatGPT's built-in image generation tool. This bridge
does **not** add a paid API, generate player likenesses, or send posts.

## Example

```bash
python fixture_watch.py
python fixture_creative_preview.py --artwork generated/original_mascot.png
```

Outputs: `generated/fixture_creative_preview.png` and
`reports/fixture-creative-preview.json`. The output remains unapproved.
No file is added to `editorial/imagegen_cards.json`, and no Buffer call is made.

The poster uses only the verified STVV/OH Leuven fixture identity and date,
and deliberately omits the conflicting kickoff time. The caption in the
review packet is a **draft**, not fact-checked final editorial copy.
Review its source, novelty against `posted.json`, creative rights, text,
mobile crop, and image bytes before a separate explicit approval.

The supplied artwork must be an original, locally accessible PNG/JPEG/WebP
(15 MB maximum). A fictional mascot is not a likeness of a STVV player;
do not describe it as one. For an actual player caricature, use a legally
usable reference image and the separate player-artwork review process.

**Known limitation:** the current `fixture_watch.py` is a single-match
pilot for 2026-11-01. This bridge cannot keep generating future match
graphics without an additional source-verified fixture discovery pipeline.
