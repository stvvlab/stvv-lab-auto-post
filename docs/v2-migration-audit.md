# STVV LAB v2 — safe migration audit (2026-10-29)

## Objective
Restore reliable, source-grounded, visually reviewed STVV posts via the existing seven JST slots, Buffer, and public X verification. This branch is documentation-only; it MUST NOT start a second publisher.

## Verified baseline
- Existing scheduled pipeline uses `delivery_run.py` -> `advance_reservations.py`, with `shareNow` disabled when advance reservations are enabled.
- `reports/delivery-latest.json` recorded 2026-10-29 10:30 slot starting at 16:26 JST (21,362 seconds late), skipped_no_verified_content. It still showed G-football reservation `6ae22a71c79ca14f286ed242` as scheduled at 18:00 JST, but this report predates the user's manual Move to Drafts action.
- User has subsequently moved that Buffer post to Drafts and saved it. **The local ledger must not be assumed to reflect this remote change.** Read the remote post state before any mutation; never resend it.
- `editorial/drafts/ohl_match_announcement_20261102.json` has `can_publish:false`, `reviewed:false`. Its exact image SHA256 is `81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5`, dimensions 1448x1086, and the image is not committed to GitHub.
- The Oct 2 Japan Day notice already announced the fixture. Distinct Oct 27 editorial angle is three successive home fixtures; any match card needs a fresh novelty review.
- `reports/imagegen-capability.json` documents a successful **conversation-side** built-in imagegen preview. This does not establish unattended imagegen inside GitHub Actions.
- Supplemental reply transport remains unavailable without separate authorized integration.

## Safety gates before activation
1. Capture main commit and read remote Buffer status for `6ae22a71c79ca14f286ed242`; reconcile Drafts vs scheduled ledger **without recreating or sending any post**. Preserve an audit record of manual cancellation.
2. Preserve `posted.json`, image manifest, existing published URLs and pending/reserved history. Never clear these to make v2 pass.
3. Transfer the exact approved OH Leuven PNG as binary (no transcoding), verify bytes and dimensions, and commit it together with a reviewed manifest only after official-body/novelty and text/image approval.
4. Keep exactly one active writer. v2 must remain disabled while legacy production is active; no new cron, dispatch, pilot or alternative Metricool post.
5. Use the existing future-slot reservation flow only after remote duplicate and capacity checks, with durable pending-before-send. A cancelled Buffer draft must not silently become a new reservation.
6. Validate with unit tests and PR CI before any production change. Distinguish GitHub success, Buffer scheduled, Buffer sent, and public X text/image verified.
7. Switch over only after a controlled, non-overlapping migration; require multiple verified real publications before declaring stable operation.

## Implementation order
- Phase A: read-only remote reservation reconciliation and regression tests for user-moved-to-Drafts.
- Phase B: exact PNG binary handoff and same-commit manifest; review fixture novelty (home three-game sequence).
- Phase C: safe single-writer scheduling and verification, no duplicate slots.
- Phase D: measure start delays, failures and real X rendering across multiple ordinary slots.

## Explicit non-goals
No paid API, secret extraction, manual sending, queue reset, quality-gate weakening, unauthorized new schedule, automatic retry on unknown outcomes, or premature completion claim.
