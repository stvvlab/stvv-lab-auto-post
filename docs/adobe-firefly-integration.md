# Adobe Firefly STVV LAB integration (opt-in)

Adobe Firefly image generation is staged, NOT a publication route. Existing Buffer/X posting and approved image manifest are unchanged.

## Prerequisites
- Adobe Firefly Services API entitlement and verified pricing (an ordinary Adobe subscription alone does not prove API access).
- In GitHub Actions secrets, configure `FIREFLY_SERVICES_CLIENT_ID` and `FIREFLY_SERVICES_CLIENT_SECRET` ONLY after entitlement approval.
- Never commit API credentials, bearer tokens, signed image URLs, or raw confidential data.

## Safe local preview
Prepare a UTF-8 caption file with the checked official `https://stvv.jp/news/...` URL included. Then:

```bash
python adobe_firefly_pipeline.py --source-url https://stvv.jp/news/game/20261026_1/ --caption-file /path/to/reviewed-caption.txt
python -m unittest tests.test_adobe_firefly_pipeline -v
```

This writes `reports/adobe-firefly-brief.json` but does not call Adobe or X.

## Explicit one-shot image generation
Only after checking usage charges, configure credentials in a secure execution environment and set `STVV_ADOBE_GENERATION_ENABLED=true`. Then add `--execute`. This makes a potentially billable Adobe API call, downloads an unreviewed staging PNG, and writes no ready manifest. Never retry an unknown async result automatically.

## Required before autonomous release
1. Obtain API entitlement and test authentication.
2. Confirm generated imagery is factually appropriate and legible, including Japanese and score pairing.
3. Add human review and approved asset registration with exact caption, article date, verified official body, dimensions, SHA256 and immutable public image URL.
4. Validate Buffer reservation and actual public X media display.
5. Only then consider a separately authorized scheduled generation job, cost/rate limits, and monitoring.

Current approval: **dry-run development only**. No generation schedule, no automatic publication.
