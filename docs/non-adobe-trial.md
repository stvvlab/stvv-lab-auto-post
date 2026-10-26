# STVV LAB: Adobe-free trial

This trial uses the already deployed GitHub + reviewed image cards + Buffer path. Adobe's Firefly API is **not required**, called, or billed. Existing Adobe integration remains disabled unless separately opted in using `--execute`, credentials and `STVV_ADOBE_GENERATION_ENABLED=true`.

**Operational boundaries:** Do not mistake this for unattended AI illustration generation. Images are produced separately, reviewed for factual accuracy, player likeness, permissions, numbers and cropping, then committed as immutable files with a matching reviewed manifest record. No approved player image can be inferred from a conversation-only thumbs-up: the exact final artifact must be registered and approved.

## Non-publishing preflight

```bash
python non_adobe_trial.py
python -m unittest tests.test_non_adobe_trial -v
```

This writes a read-only report and performs **no Buffer or X action**. A candidate means metadata is complete; it does not mean the image passed real-world editorial checks. Existing `prepared_media.py` checks local asset bytes, sha256, dimensions and actual immutable public image bytes again; other guards verify source, duplicate and freshness.

## First live trial
1. Choose a new, verified STVV news event not previously published; past cards and duplicate facts are never reused.
2. Produce and review a single original image. For any player likeness, use the official profile as a source and obtain appropriate image-use rights; do not publish an unlicensed photo as artwork.
3. Register matching original article URL, exact caption, slots, JST date, real path, SHA256, dimensions, `reviewed: true`, `status: ready` in `editorial/imagegen_cards.json`.
4. Ensure no pending duplicate or ambiguous Buffer outcome exists.
5. Allow the **existing scheduled posting workflow**, not a new parallel sender, to submit it. Verify Buffer acceptance **and** real X display before declaring success.
6. If any prerequisite fails, do not send or silently fall back to unapproved imagery.

Adobe-free **image delivery** can work with the current system; **automatic high-quality likeness generation** remains a separate unresolved capability.
