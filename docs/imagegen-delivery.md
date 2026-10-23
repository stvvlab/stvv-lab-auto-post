# Reviewed imagegen delivery

The approved baseline is `generated/approved_midtjylland_20261023.png`,
visually verified on X at https://x.com/stvvlabo/status/2113772119062372376.
The earlier fixed headline layout is not the quality target.

## Split execution

ChatGPT's scheduled preparation task researches fresh official information,
edits concise Japanese copy, invokes the built-in imagegen tool when available,
and visually checks the resulting image. GitHub Actions does not call a paid
image-generation API. A scheduled imagegen run has not yet been demonstrated;
saving a task prompt does not prove imagegen is available to that run.

The preparer commits reviewed image bytes and `editorial/imagegen_cards.json`
together. The existing seven scheduled posting slots consume ready entries.
No manual pilot or extra post is triggered by queue preparation.

## Manifest

`enabled: true` disables legacy rendering fallback. Each card has:

- `status`: `ready` for a reviewed candidate, `published` for historical assets.
- `source_url`: the exact official `https://stvv.jp/news/.../` article read.
- `date_jst`: the article's date in YYYY-MM-DD format; only past seven days accepted.
- `text`: reviewed caption, containing the exact source URL, without the fixed hashtags.
- `slots`: relevant existing slot names, never all slots solely to fill a quota.
- `reviewed`: true only after visual inspection against the official facts.
- `asset_path`: direct child PNG or JPEG of `generated/`.
- `sha256`, `dimensions`: exact reviewed file metadata.
- `review_note`: design choices, checked facts, any unresolved issue.

Use content-specific composition and concise copy. Do not place an entire
article headline into a fixed box. Align scores with their team labels;
STVV-first ordering is allowed even for away games, but must be explicit.
No invented faces, statistics, crests, venue claims or unverified photographs.

The runner checks freshness, source, slot, caption length, pending and published
duplicates before preparing media. It requires an unambiguous exact match of
caption/source/slot, reviewed digest, image dimensions and public asset bytes
at the immutable git revision. Missing or invalid assets produce a skip, not
a redraw or a text-only post. The existing send-before-pending prohibition and
uncertain-send retry protection remain intact.

## Status

One manually initiated imagegen-to-X publication succeeded on 2026-10-24.
Prepared-asset ingestion is covered by offline tests. Successful unattended
image generation, queue registration and scheduled delivery still require a
real scheduled run. Supplemental reply transport is separate and unimplemented.
