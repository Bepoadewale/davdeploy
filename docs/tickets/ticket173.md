# ticket173 — Document reproducible email operations

PR: [#173](https://github.com/Bepoadewale/davdeploy/pull/173)
Branch: `docs/email-operations-runbook`

## Problem / goal

The active Resend/Cloudflare email system was operational but its setup, alias inventory, testing
method, secret boundary, rotation procedure, and provider-change path were spread across prior PRs
and stale status documents.

## Current repo state

The hosted API sends invitations through Resend using a Standard SSM SecureString. Cloudflare Email
Routing explicitly forwards four verified aliases, including founder, support, notification, and
Eniola correspondence. Direct sender delivery and independent Cloudflare forwarding were confirmed.

## Research / references used

- Deployed Lambda configuration and least-privilege IAM policy after PR #171.
- Cloudflare Email Routing active rule/destination state and controlled forwarding tests.
- Resend verified-domain direct-send tests.
- Existing product, deployment, identity, provider and security documentation.

## Work planned for the PR

- Add one operational source of truth for aliases, responsibilities, tests, rotation and migration.
- Reconcile current backend status documents without changing historical ticket/test evidence.
- Mark older strategy review material as historical where it predates deployed status.

## Acceptance criteria

- [x] Operators can add and independently test a new alias without a catch-all rule.
- [x] Operators can rotate the sending key or change outbound providers without exposing a secret.
- [x] Current documentation consistently identifies `davdeploy.tech`, Aurora, Resend, Cloudflare,
  and the remaining browser-acceptance boundary.
- [x] Historical evidence remains dated rather than being rewritten as current evidence.

## Acceptance status

Documentation reconciliation is complete pending review.

## Tests / validation performed

See `docs/test/test173.md`.

## Evidence files produced

- `docs/test/test173.md`

## Boundaries

This documentation PR does not create, change, or remove email, DNS, Cloudflare, Resend, AWS, or
customer resources. The active aliases and sender configuration were established and tested before
this documentation change.

## Follow-up work

Run and record the full production browser invitation-to-workspace acceptance journey before broad
customer onboarding.
