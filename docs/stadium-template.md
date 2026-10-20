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
