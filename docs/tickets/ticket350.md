# ticket350 — Reconcile Nova broker deployment evidence

PR: pending
Branch: docs/reconcile-nova-broker-deployed-350
Base: main

## Problem / goal

Update the execution-readiness matrix with authoritative merge and deployment evidence for the Nova run-scoped credential broker. Preserve the distinction between deployed control-plane code and a still-disabled, not-yet-used customer planning path.

## Current repo state

PR #348 was merged as a533d13. The exact saved Terraform plan was applied; migrations, Lambda status, package identity, and API health are being verified. The matrix still says PR #348 is under review and not deployed.

## Research / references used

- docs/product/EXECUTION_READINESS_MATRIX.md
- PR #348 and its saved plan/apply runs
- Protected Terraform deployment workflow logs
- AWS Lambda configuration and versioned release artifact metadata

## Work planned for the PR

- Replace stale review status with exact merged source and deployment evidence.
- Record the disabled feature gates, no customer workload, and the remaining pricing/plan/apply/lifecycle gaps.
- Keep the full strategy and operational access notes in the private local status file.

## Acceptance criteria

- [ ] Matrix cites exact commit, plan/apply runs, migration result, Lambda status, artifact identity, and health check.
- [ ] Matrix explicitly says the Nova broker and runner remain disabled and no customer plan/workload was created.
- [ ] Ticket records the exact PR number and final checks.
- [ ] Documentation conventions and required final-head CI pass.

## Acceptance status

Bootstrap only. Deployment evidence is available locally; matrix edit and final CI are pending.

## Tests / validation performed

No checks run yet.

## Evidence files produced

- No runtime evidence file is required because this PR only reconciles source/deployment documentation against already completed workflow and read-only runtime evidence.

## Boundaries

No AWS calls or resource changes are part of this documentation PR. It does not enable the Nova broker, plan runner, customer role verification, state API, approval, or apply path.

## Follow-up work

Continue toward trusted costed planning, exact-plan approval, scoped apply, customer health, recovery, teardown, and composed hosted workload certification.
