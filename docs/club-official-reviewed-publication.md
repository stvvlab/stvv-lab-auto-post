# Reviewed Belgian STVV official article gate (2026-10-28)

This change expands **eligible source evidence**, not the posting schedule or approval rules. Only exact HTTPS `https://stvv.com/nl/nieuws/artikel/<slug>` pages may enter the reviewed image queue. The existing Japanese STVV source gate remains in place.

For each Belgian-source card, a human/editorial preparation step must verify the original Dutch body, translate only directly supported facts into short Japanese, check novelty against the published/pending/reserved ledger, generate one original built-in image, visually approve its text and crop, and commit its bytes and manifest in one revision. No automatically translated headline, unreviewed image, promotional article or slot-filling post is allowed.

Additional manifest fields for a Belgian card:
- `source_body_sha256`: exact SHA-256 of the extracted official article body returned by `club_official_inventory.article_evidence`.
- `date_jst`: exact article publication date displayed immediately after its H1, not a date guessed from its slug or a kickoff date. This existing field name is retained for compatibility.
- Existing `source_url`, `text`, `slots`, `reviewed: true`, `status: ready`, `asset_path`, `sha256`, `dimensions`, and `review_note` remain mandatory.

Before creating a Buffer pending intent, the regular scheduled runner fetches the exact official page again, rejects off-host redirects, checks its displayed publication date, its seven-day freshness and the entire reviewed body digest. The reviewed media loader checks the same digest again before validating the immutable public image bytes. No Belgian `editorial_fact` override is allowed, so a previously used article is never republished as an allegedly new milestone. The remote Buffer duplicate scan includes both official domains.

As of 2026-10-28, the official Belgian club site contains two new 2026-10-27 articles, including `https://stvv.com/nl/nieuws/artikel/de-week-van-de-waarheid` (three upcoming home fixtures, including Japan Day against OH Leuven) and `https://stvv.com/nl/nieuws/artikel/g-voetballers-beleven-droomdag-op-stayen` (a community football day). These are **editorial research candidates only**, not ready cards or permission to publish. Fixture times must be checked against the Japanese official schedule before any date/time appears in an image or caption.

This change does not send a post, start a manual run, purchase an API, relax the 270-character limit, bypass the reviewed image requirement, or prove Buffer reservation/X display. Live reservation and public X verification remain separate outstanding tasks.
