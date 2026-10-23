# Adopted stadium template

The approved flag, stadium and paint background is stored once in
`assets/stadium_background.jpg`. It is an illustrative background, not a
documentary photograph. The bundled Permanent Marker font is distributed
under the adjacent Apache license. Japanese uses Noto Sans CJK on the runner.

`content_card.render_content_card` places the actual caption into this layout.
Scores appear only when the supplied text has an explicit `STVV n–n opponent`
line; missing data never produces decorative values or a sample fixture.
No external generative or paid API is called during rendering. In particular,
the imagegen tool used to prepare the background is not needed on the runner.

The existing seven scheduled slots and content source policy stay in place.
The authoritative category mapping is `stvv_post.SLOTS`; workflow comments
show times only. Reports must use this mapping rather than infer a category.

| JST | Category |
| --- | --- |
| 08:00 | player |
| 10:30 | compare |
| 12:30 | data |
| 15:30 | analysis |
| 18:00 | news |
| 21:00 | vote |
| 23:00 | recap |

Each eligible post generates one JPEG, commits it, verifies identical public
bytes and sends it through Buffer. Posts without verified content are skipped
by the existing quality gate. Failed image generation/publication now skips
the post instead of reverting to an old fixed card or a text-only post.

`python render_stadium_preview.py` produces a preview without publication.
The safety workflow runs tests and uploads that preview on changes. The normal
scheduled workflow also runs the tests before allowing a Buffer send.

This is one reusable composition adapted to each category, not seven separate
AI illustrations. Only the source data already provided by the posting script
are visualized; it does not create new player scouting or tactical assessments.

## Quality pass 2

Lower panels are drawn only for actual supplied content, and expand to one,
two or three columns. Empty decorative columns are no longer baked into the
background. Japanese wrapping preserves names, katakana terms and number/unit
pairs when they fit, while avoiding leading punctuation. Brush headers have
controlled tilt and deterministic wear.

Every output has a `.layout.json` companion recording source text, font sizes,
line breaks, coordinates and whether a score was present in the caption. The
posting script commits this audit together with the image; CI also uploads it
with the preview. This gives each improvement run evidence instead of relying
on a successful file write as proof of visual quality.

## Quality pass 3

Short leads already separated from details by a source comma or colon can use
larger white text above smaller yellow details. The exact original text and
delimiter remain in the layout audit. Long copy falls back to the full-panel
layout rather than losing text or failing on a narrower detail area.

An explicit ISO match date plus home/away line is displayed as small match
metadata when the caption also supplies an explicit score. Without a score,
that line remains in the story content. No date is inferred.

## Quality pass 4

The large brush heading now ends in a deterministic tapered paint sweep and
five broken bristle trails. The accent stays above the information card and
is generated locally from the bundled assets; it carries no fixture or player
data. Its exact bounds and strokes are recorded in the layout audit.

## Scheduled result reporting

Every scheduled run emits one machine-readable `RUN_RESULT` and writes the
same result to the GitHub Actions step summary. Successful Buffer acceptance,
duplicate protection, missing verified content, missing vote candidates and
failed public-image byte verification have distinct statuses. An unexpected
exception still fails the workflow, so a safe skip is not confused with an
error.
Only the real posting step with a recognized `GITHUB_SCHEDULE` writes this
summary. Offline test results remain in test logs and cannot appear as actual
Buffer submissions in the posting summary.

## Punctuation at narrow widths

Trailing Japanese punctuation stays with the preceding intact name or term.
When that combined unit exceeds the current width, the fitter reduces type
size instead of moving only the last character of a name to the next line.

## Official scoring-time data

When the data slot lacks detailed statistics, a saved official match manifest
can supply scorer names and times. Every use fetches the live STVV official
article and checks its date, home opponent, score and complete scorer row.
Facts expire after seven days; missing or changed evidence blocks the card.
Identical text already published or pending is not reused. Four scorer rows
appear in chronological order across two panels; the source URL is credited
in the footer. No extra slot or test publication is created.
An exact published/pending official scorer caption reports
`skipped_repeated_content`, while absent verified facts report
`skipped_no_verified_content`; neither generates media or sends to Buffer.

## Repeated match coverage

Before image generation and Buffer submission, `content_guard.py` compares
the proposed caption with published and pending entries from the last seven
days. It ignores cosmetic punctuation, whitespace and hashtag changes;
canonical source URLs ignore query strings and trailing slashes. Shared
sources or recognized opponent/score combinations identify repeated match
coverage, including saved Japanese/English opponent aliases.

A second result/scorer/goal-minute recap is skipped with
`skipped_repeated_content`. A new structured shot, shots-on-target or
possession comparison can pass once; existing source verification remains
required. These are conservative local rules, not general semantic AI:
an update to the same article without a recognized new comparison is also
held back. Different official announcements remain eligible. Existing slot,
pending-before-send and public-image byte checks are unchanged.

News candidates are checked for repetition before selection. A repeated
match article is excluded and the remaining verified official articles are
considered in order; it cannot hide a later distinct announcement. When all
otherwise eligible candidates repeat published or pending content, the run
reports `skipped_repeated_content` before image creation or Buffer. The final
pre-media repetition gate still checks the selected caption for every slot.

The vote slot also requires a verified, nonrepeated match context. Missing
context skips as `skipped_no_verified_content`; repeated coverage skips as
`skipped_repeated_content`. Generic fan-question fallback selection is disabled
in the scheduled route. The seven slots remain, but do not impose a quota.

The official news list wraps a heading, `<time>` date and preview paragraph
inside one link. Article selection uses the supplied h2/h3 heading and
removes the time element, rather than accidentally treating the whole card
as a headline and rejecting it for length. Simple text links remain supported;
the domain, freshness, excluded-topic, weighted-length and repetition gates
still apply. No claim is rewritten or summarized by an external API.
Excluded-topic keywords are still checked across the original whole card,
so removing an excerpt from the displayed headline does not weaken filtering.

## Quality pass 5

One or two explicitly supplied `name：minute分` rows in a lower panel use
white intact names and larger yellow times aligned at the right edge. This
restores the scoring-time hierarchy of the approved review without adding
facts, icons or new copy. Names and times are fitted separately with a gap;
copy that cannot fit a single row falls back to the existing full-panel
layout. The layout audit retains the exact delimiter and both text boxes.
The CI preview artifact also includes `scorer_alignment_preview.jpg` and
its audit, rendered offline from the saved verified manifest. These design
previews are never sent to Buffer or exempted from the repetition gate.

## Quality pass 6

Body paragraphs that wrap to two very uneven lines can move intact tokens
to a supplied Japanese clause boundary. This avoids leaving a short ending
alone on the second line. The original characters, type size and line count
are preserved. Explicit newlines, headings, scorer rows and lead/detail
panels retain their existing layout; no copy is summarized or invented.

## Official source route for the player slot

The player slot checks the same live official article list as the news slot,
requiring `選手` in the supplied headline. Domain, freshness, excluded-topic,
caption length and source/content repetition checks apply before rendering.
An accepted source is recorded as used news across slots. Without a suitable
new article the player slot still skips; no generic scouting claim is added.
The offline player preview reuses the saved official headline only as design
evidence. It is not a publication candidate and cannot bypass source checks.

## Quality pass 7

Headlines without an explicit score are vertically centered within the existing
headline area. Short one- or two-line headlines no longer leave most of the
central card empty below the text. Copy, line breaks and type size are preserved;
score cards, lower panels and all publication gates retain their existing layout.
The audit records the actual centered text box for overflow and margin checks.

## Quality pass 8: participation cards

The vote composition places a large Japanese question above the supplied match
context and three equally sized choice panels. FAN VOICE is a compact single
line, rather than the dominant two-line headline. Choice labels describe what
the reader wants reviewed (attack, defence or players), not unverified claims
about the match. Line breaks keep `どこから` intact. Other categories retain
their existing composition. Offline previews reuse the saved verified match
only to review layout; repetition checks still prevent publishing it again.

Transport verification and editorial approval are separate: a successful X
image display does not establish that the image or question meets the quality
bar. The October 22 v7 vote passed transport but received negative user review;
v8 is a response to that review, not a claim of improved engagement.

## Quality pass 9: composition rotation

Accepted publication history selects stadium, split-photo and yellow-poster
compositions in order. A successful publication advances the cycle; skips,
pending entries and failed image checks do not. The same retry is deterministic.
The split-photo version crops the saved asset without mirroring crests or flags.
The poster version uses local colour blocks and typography. No additional
image-generation call, external asset or paid API is introduced.

The layout audit records `variant`. All compositions render the same supplied
headline, match context and details. Selection happens after editorial and
repetition gates; publication/pending and public-byte checks remain unchanged.
Three offline variant previews are included in the CI artifact and never posted
as tests. Variation does not establish editorial quality or improved engagement.

## Bounded runner font setup

The October 22 23:00 recap run was cancelled while downloading the 61.2 MB
Ubuntu font package; no posting step ran. `scripts/install-card-font.sh` now
reuses an installed Noto CJK Bold font, limits index refresh to 45 seconds,
and permits at most two 90-second package-install attempts (plus termination
grace). Connection timeouts are 20 seconds with no nested apt retries. If no
usable font exists afterwards, setup fails before tests or Buffer submission.
The posting and preview workflows use the same installer. This handles setup
stalls, not GitHub schedule creation delays; cancelled slots are not replayed.

## Quality pass 10: score contrast

For scored stadium cards, STVV's supplied score remains yellow while the dash
and opponent score are white, matching the approved review's hierarchy. Both
segments share one measured baseline and fitted type size, including two-digit
scores. The audit records exact segments, colours and baseline. No score is
created without an explicit caption score; vote and alternate layouts retain
their compositions. This is a colour/readability change, not a new fact or post.

The preview CI later exhausted both bounded font downloads, while the regular
October 23 08:00 job succeeded and passed104 tests before a duplicate-content
skip. Posting and preview CI now share `.cache/stvv-fonts` through Actions
cache. The installer copies an available system font into this directory and
exports `STVV_CARD_FONT`; a restored font skips apt entirely. Cache misses
retain bounded installation and fail-closed behavior. Cache storage/restoration
must still be verified in Actions; local cache reuse alone is not that proof.
