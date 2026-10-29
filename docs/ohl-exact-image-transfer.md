# Approved OH Leuven image: exact transfer handoff

## Why this exists
The ChatGPT-generated image is present in the conversation's working files but the connected GitHub API cannot read that local binary. **The image has not been uploaded to GitHub.** Do not claim otherwise.

## One-time transfer
1. Obtain the already-approved file `ohl_match_announcement_20261102.png` from the conversation (no regeneration or JPEG conversion).
2. In GitHub, switch from main to branch `fix/ohl-exact-image-transfer-gate-20261029`.
3. Open `generated/` on that branch, choose **Add file → Upload files**, select the original PNG, and commit to **this branch**, never directly to main. **An iPhone-generated UUID filename is fine**; do not edit or re-encode the image to rename it. The branch-only GitHub Action `ohl-image-normalize.yml` identifies the exact approved bytes by SHA-256 and moves the committed upload to the canonical filename.
4. Wait for the branch-only `Normalize approved OH Leuven mobile upload` Action to finish. It must succeed and commit the verified rename. Verify with `python scripts/verify_ohl_image.py`. The exact SHA-256 must be `81eaf83c89e1a63593fcdf8dd222b7f5fee387cf3bac7cd65a9920c8e402afa5`; format PNG; dimensions 1448×1086. Any mismatch is a hard stop.
5. After image transfer, recheck the current official article body, STVV LAB publication/Buffer duplicates and editorial approval. Only then prepare the reviewed `ready` card and source-body digest, preferably on this branch.
6. Squash-merge only the fully verified branch so that the binary and ready manifest appear together on main in **one final commit**. Normal seven scheduled delivery slots handle reservation after that; no manual dispatch, retries or altered publication slots.

The user-approved image and the existing draft caption do not by themselves authorize a new Buffer operation. The project must not silently adopt an alternate image, bypass media verification, or change pending/reserved records.

If the conversation cannot deliver binary bytes into GitHub through a connected API, the only supported current alternative is the one-time browser upload above. Do not state full automatic image delivery is implemented.

The GitHub Action does not change the manifest, approve a post, reserve a slot or merge the PR. It only normalizes the original upload. If it fails, leave the PR draft and inspect its log. Never bypass the hash gate.
