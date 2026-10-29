# STVV LAB editorial repeat policy (opt-in proposal)

**Principle:** A repeated topic is not automatically low-value. A reminder at a new moment, a lineup, a result and an evidence-based analysis can each be valuable.

## Four separate gates

1. **Truth and source:** verified official information, correct date/score/participants, no invented statistics. Reusing a source URL is permitted; verification remains mandatory.
2. **Editorial value:** a reviewed card may explicitly declare `editorial_purpose: {kind, phase, event_id}` with a stable event identity. Supported kinds: fixture, lineup, result, analysis, player, news. Supported phases: initial, reminder, matchday, lineup, final, review, update.
3. **Repetition:** same exact normalized caption is blocked; same event+kind+phase pending/reserved is blocked; same event+kind+phase published within 24 hours is blocked. Different phases or kinds are allowed *only when explicitly reviewed*. Unknown metadata fails closed. Untagged cards keep the old duplicate gate until migrated.
4. **Delivery:** exact reviewed image bytes, official body, source freshness, GitHub history, remote Buffer preflight, slot occupancy and pending-before-send behavior remain mandatory. Never auto-resend a questionable Buffer outcome.

Examples: a first fixture announcement, next-day reminder, matchday guide, lineup, result and next-day analysis are distinct purposes. A news article already present on the club's website is not evidence that STVV LAB has posted it.

**Rollout:** This change introduces only opt-in support; it does **not** reapprove old content, upload an image, grant OH Leuven readiness, schedule posts, call Buffer or prove an X publication. Review and tag future cards separately. The currently pending OH Leuven artwork transfer and image manifest registration must still be resolved. Existing 7 slots and no paid services remain unchanged.
