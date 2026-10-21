# Ethics & Compliance

## Purpose

This project is for authorized coursework/research only. Do not collect or redistribute group content without the required permission and a clear lawful basis.

## Pre-crawl checklist

- [ ] The instructor/project owner permits this collection; retain written confirmation if required.
- [ ] Confirm whether the group is public or private. Membership alone does not imply permission to redistribute posts.
- [ ] Use your own account and a visible browser. Never store passwords in code.
- [ ] Do not bypass CAPTCHA, login walls, checkpoints, rate limits, or other safeguards.
- [ ] If a restriction appears, stop, preserve the checkpoint, and exit with code 3; switch to an authorized import dataset.
- [ ] Collect only necessary text and metadata. Do not collect profiles, friend lists, or member lists.
- [ ] Hash author IDs with HMAC-SHA256 using `FBPIPE_SALT`; redact emails, phone numbers, and URLs in text.
- [ ] Never commit `.env`, `.auth/`, real posts, cookies, tokens, or unreviewed probe samples.
- [ ] Review every report and figure for personal information before publishing.
- [ ] Check current Vietnamese personal-data law and platform terms before collection; this document is not legal advice.

## Data handling

The repository should contain only code, synthetic data, and reviewed anonymized examples. Keep raw data locally and restrict access. Document retention and delete data when no longer needed.

## Parser status

`graphql_parser.py` currently uses a self-authored generic fixture. It is not a verified Facebook schema. Replace or extend extraction rules only after a human-reviewed, anonymized `probe_report.md` and samples exist.
