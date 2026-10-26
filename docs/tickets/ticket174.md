# ticket174 — Record Gmail sender identities

PR: [#174](https://github.com/Bepoadewale/davdeploy/pull/174)
Branch: `docs/gmail-sender-identities`

## Problem / goal

The email runbook covered Cloudflare forwarding and product delivery but not the completed Gmail
SMTP sender identities required for founders to compose ordinary mail as DavDeploy aliases.

## Current repo state

`bepoadewale1@gmail.com` has verified Resend SMTP sender identities for `bepoadewale@`, `support@`,
and `notify@davdeploy.tech`. Manual sends from the Gmail From menu succeeded.

## Research / references used

- Gmail Accounts and Import sender-identity configuration.
- Resend SMTP configuration: `smtp.resend.com`, port 465, `resend` username, SSL.
- Controlled sender tests performed after each Gmail identity was verified.

## Work planned for the PR

- Record current sender identities, Gmail behavior, SMTP settings, and alias-specific Reply-To.
- Add Gmail SMTP identity ordering to the key-rotation procedure.

## Acceptance criteria

- [x] A future operator can add a Gmail sender identity without confusing Cloudflare MX with SMTP.
- [x] The three verified Gmail identities and reply behavior are recorded.
- [x] Key rotation cannot revoke Gmail sending before its identities are updated and tested.

## Acceptance status

Documentation is complete pending review.

## Tests / validation performed

See `docs/test/test174.md`.

## Evidence files produced

- `docs/test/test174.md`

## Boundaries

This PR does not modify Gmail, Resend, Cloudflare, AWS, or any sender credential. It records
already completed configuration and controlled manual sender tests.

## Follow-up work

Create a dedicated Gmail-only Resend sending key at the next credential rotation, then update all
Gmail sender identities before revoking the current key.
