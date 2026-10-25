# Reviewed imagegen delivery

The approved baseline is `generated/approved_midtjylland_20261023.png`,
visually verified on X at https://x.com/stvvlabo/status/2113772119062372376.
The earlier fixed headline layout is not the quality target.

## Split execution

ChatGPT's scheduled preparation task researches fresh official information,
edits concise Japanese copy, invokes the built-in imagegen tool when available,
and visually checks the resulting image. GitHub Actions does not call a paid
image-generation API. Built-in generation and reviewed queue preparation were
verified for the Hajduk closed-doors card on 2026-10-24. Its existing scheduled
news-slot delivery and actual X image display were also verified; see
`reports/imagegen-capability.json` for asset hashes and evidence.

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

The Hajduk card completed built-in generation, visual review, queue registration,
and existing 18:00 JST news-slot delivery on 2026-10-24. Actions run
https://github.com/stvvlab/stvv-lab-auto-post/actions/runs/40081188399
recorded Buffer acceptance; X text and image display were verified at
https://x.com/stvvlabo/status/2113922269583917472.
This evidence applies to that card, not to future comic-style variants.
Comic diversity still requires a fresh reviewed ready card and regular-slot
publication verification. Paid image API generation is blocked in `ai_art.py`
and disabled in the scheduled posting workflow. Supplemental reply safety
is implemented separately, but its sending transport remains unavailable.

## Varied built-in design preparation

Use `design_brief.build_brief(source_url, reviewed_text, history)` after verifying
the source and ruling out published/pending duplicates. This produces `brief_only`
planning data for ChatGPT built-in imagegen; it never generates, reviews or publishes
an asset. Five directions balance confirmed publication history and avoid repeating
the last recorded direction. Pending and skipped attempts do not consume a style.

After generating the complete artwork and visually checking facts, Japanese, digits,
team-score pairing, safe crop and caption agreement, add the returned `art_direction`
to the ready manifest card with its usual digest and dimensions. Only exact matching
reviewed ready-card metadata enters pending and publication history. Do not register
a brief as ready or count offline/CI mocks as a public delivery. Source freshness,
270 weighted characters including tags, public bytes and all existing guards remain.
