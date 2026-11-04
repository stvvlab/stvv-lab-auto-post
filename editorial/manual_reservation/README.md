# Manual reservation — isolated from scheduled STVV LAB posts

This directory is for one-off, human-approved reservations. It is **not** consumed by `delivery_run.py`, `advance_reservations.py`, or the three daily cron slots.

## 2026-11-04 De Meyer departure

Approved request: `editorial/reservation_requests/2026-11-04_de_meyer_departure.json`.

Target: 2026-11-04 18:00 JST, @stvvlabo. The approved post image has **not** been linked to a verified public asset; no Buffer reservation has been submitted.

## Required before an isolated send

1. Verify the official article, approved text, image URL and its immutable bytes, and exact target time.
2. Query Buffer's actual @stvvlabo channel, queue and sent posts to prevent duplicate caption and occupied-slot submission.
3. Check the target is still in the future and has sufficient lead time.
4. Persist a unique pending-send intent **before** the one and only Buffer createPost call. An unknown outcome must block retries.
5. Verify Buffer's returned post ID, caption, channel, media, due time and `scheduled` status; persist the receipt.
6. Have the operator visually verify Buffer Queue. A Buffer receipt is not proof of publication on X.

**Do not** remove the `schedule` event guards from the existing publisher or invoke it with a fabricated schedule event. The manual procedure must be separately implemented and tested before use.
