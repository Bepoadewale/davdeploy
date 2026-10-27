# ticket189 — Verified AWS administrator-pilot setup

PR: [#189](https://github.com/Bepoadewale/davdeploy/pull/189)
Branch: `feat/deployment-access-verification`

## Problem / goal

Prevent accidental administrator-pilot setup and prove an optional customer execution role can be assumed before it is marked verified.

## Current repo state

The three AWS connection paths existed, but pilot setup had no server-side acknowledgement requirement and verification checked only discovery access.

## Research / references used

AWS STS AssumeRole and ExternalId cross-account trust model; the existing versioned customer CloudFormation contract.

## Work planned for the PR

Require a pilot acknowledgement in the API, verify the optional execution role with STS, record that verification in the audit trail, and reconcile customer-access documentation.

## Acceptance criteria

- [x] Administrator-pilot setup is rejected until the client sends an explicit acknowledgement.
- [x] A configured execution role must assume into the selected customer account before the connection is verified.
- [x] No temporary customer credentials are persisted.
- [x] Status documentation distinguishes setup from workload execution.

## Acceptance status

Local automated validation passed; pending CI, review, merge, and hosted deployment.

## Tests / validation performed

Recorded in `docs/test/test189.md`.

## Evidence files produced

- `docs/test/test189.md`

## Boundaries

No CloudFormation stack, customer role, workload, plan, apply, or destroy operation is created by this change.

## Follow-up work

Run an explicitly authorised, billable customer-cloud pilot only after the guarded execution path and customer acceptance criteria are separately approved.
