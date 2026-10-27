# ticket187 — Explicit AWS connection access modes
PR: pending
Branch: `feat/aws-connection-access-options`
## Problem / goal
Offer separate existing-role, read-only, and administrator-pilot AWS access paths.
## Current repo state
Connection setup previously had one CloudFormation path.
## Research / references used
AWS cross-account role and external-ID model.
## Work planned for the PR
Add an explicit template access mode.
## Acceptance criteria
- [x] Discovery remains default.
- [x] AdministratorAccess requires administrator-pilot selection.
## Acceptance status
Locally verified; pending CI and deployment.
## Tests / validation performed
Recorded in `docs/test/test187.md`.
## Evidence files produced
- `docs/test/test187.md`
## Boundaries
No workload is deployed by setup.
## Follow-up work
Add pasted custom-role ARN attachment and verification.
