# STVV LAB approved likeness → caricature workflow

This is an **opt-in, review-only** addition. No scheduled generation and no change to the existing publication route.

## Source of truth

* Start from a player's specific official `https://stvv.jp/team-member/<slug>/` profile, not an inferred name, number or role.
* Download official head-and-body images only as internal reference material where legally permitted; **public display and derivative rights are not implied by public access**.
* Produce a neutral likeness portrait **using the photo as actual image input**. Do not rely only on a text description.
* Obtain explicit approval of that specific neutral portrait. Save its SHA256. An edited portrait must be approved again.
* The approved portrait is the identity anchor. For the character variant, change the expression and proportions, not the facial identity. STVV LAB target: 2–3 heads tall, with a deliberately oversized face and a tiny body, weird-cute/crazy expression, navy and yellow.
* Place verified names, shirt numbers, typography and logos in a separate layout operation. Do not trust AI-generated numbers or marks.
* Final output is blocked from X until a separate human review confirms likeness, facts, permissions, and presentation.

## Developer dry run

Create local image files `assets/reference-hata.png` and `assets/approved-hata.png` (do not assume the model has downloaded them) and an **untracked local** manifest:

```json
{
  "player_name": "Taiga Hata",
  "profile_url": "https://stvv.jp/team-member/taiga-hata/",
  "reference_photo": "assets/reference-hata.png",
  "approved_portrait": "assets/approved-hata.png",
  "approved_portrait_sha256": "<SHA256 of locally approved portrait>",
  "likeness_approved": true,
  "jersey_number": 3
}
```

Then execute:

```bash
python player_artwork.py --manifest /path/to/local-manifest.json
python -m unittest tests.test_player_artwork -v
```

The JSON brief intentionally contains `publication_allowed: false`. It is **not** a ready image or a publication manifest. The portrait's approval is not approval for every new caricature. Adobe Firefly API entitlement and human review are still required for unattended end-to-end Adobe generation; no cost-bearing API call is made by this module.

**Limitation:** This feature implements secure reference validation and prompt preparation, not direct image-to-image generation, approval UI, GitHub binary upload, Buffer scheduling, or X publishing.
