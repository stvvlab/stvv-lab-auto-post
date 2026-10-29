# Approved OH Leuven image: exact transfer handoff

## Why this exists
The ChatGPT-generated image is present in the conversation's working files but the connected GitHub API cannot read that local binary. **The image has not been uploaded to GitHub.** Do not claim otherwise.

## One-time transfer
1. Obtain the already-approved file `ohl_match_announcement_20261102.png` from the conversation (no regeneration or JPEG conversion).
2. In GitHub, switch from main to branch `fix/ohl-exact-image-transfer-gate-20261029`.
3. Open `generated/` on that branch, choose **Add file → Upload files**, select that PNG, and commit to **this branch**, never directly to main.
4. Verify with `python scripts/verify_ohl_image.py`. The exact SHA-256 must be `81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5`; format PNG; dimensions 1448×1086. Any mismatch is a hard stop.
5. After image transfer, recheck the current official article body, STVV LAB publication/Buffer duplicates and editorial approval. Only then prepare the reviewed `ready` card and source-body digest, preferably on this branch.
6. Squash-merge only the fully verified branch so that the binary and ready manifest appear together on main in **one final commit**. Normal seven scheduled delivery slots handle reservation after that; no manual dispatch, retries or altered publication slots.

The user-approved image and the existing draft caption do not by themselves authorize a new Buffer operation. The project must not silently adopt an alternate image, bypass media verification, or change pending/reserved records.

If the conversation cannot deliver binary bytes into GitHub through a connected API, the only supported current alternative is the one-time browser upload above. Do not state full automatic image delivery is implemented.
