# ticket188 — Customer-managed AWS role setup
PR: pending
Branch: `feat/customer-managed-aws-roles`
## Problem / goal
Support customer-managed discovery and optional execution roles.
## Current repo state
Only CloudFormation setup existed.
## Research / references used
AWS role trust and external-ID model.
## Work planned for the PR
Attach and later verify customer role ARNs.
## Acceptance criteria
- [x] Role ARNs are account-scoped.
- [x] External ID is stored only as a secret reference.
## Acceptance status
Locally validated; pending CI.
## Tests / validation performed
Recorded in `docs/test/test188.md`.
## Evidence files produced
- `docs/test/test188.md`
## Boundaries
No customer role is assumed during attachment.
## Follow-up work
Live role verification.
