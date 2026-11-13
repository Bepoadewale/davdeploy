# ticket392 — record disposable Nova plan-role policy validation

PR: https://github.com/Bepoadewale/davdeploy/pull/392
Branch: `docs/record-nova-plan-role-validation-392`

## Problem / goal

Record a disposable AWS validation of the published Nova plan-only customer
role template, its read/deny policy behavior, and exact teardown.

## Current repo state

Backend `main` is at `8f17c4809bd0ad7fdc3cc4851bfc2241e5cb28d5` (PR #391).
The 2026-11-13 test created and then deleted one temporary IAM role using the
published plan-only template. No customer plan or workload was run.

## Research / references used

- `infrastructure/cloudformation/customer-discovery-role.yaml`
- Published immutable template content hash
  `8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e`.
- PRs #369, #381, and #390; `docs/product/EXECUTION_READINESS_MATRIX.md`.

## Work planned for the PR

- Record exact test ID, account, region, CloudFormation change set, temporary
  role, IAM simulator decisions and absence verification.
- Clarify that simulator evidence is not a complete hosted customer-role,
  real-assumption or workload-plan verification.
- Update product status and backlog without marking the role or plan flow
  customer-ready.

## Acceptance criteria

- [ ] Exact temporary resource manifest and teardown evidence are recorded in
  `docs/test/test392.md`.
- [ ] Current status documents distinguish policy simulation from a real
  customer connection and effective account permissions.
- [ ] No customer plan or workload readiness is claimed.
- [ ] Documentation checks and required CI pass; PR merges.

## Acceptance status

- [ ] Evidence and status changes pending.

## Tests / validation performed

- Pending.

## Evidence files produced

- `docs/tickets/ticket392.md`
- `docs/test/test392.md` (to be added).

## Boundaries

The exact disposable IAM role and CloudFormation stack were deleted after
validation. No customer workload, persistent customer role, or existing
connection was changed. The generated external ID is intentionally not
recorded.

## Follow-up work

Verify the role through a real authenticated DavDeploy customer connection,
then separately establish effective AWS permissions and run a successful
saved-plan workflow before any customer apply is considered.
