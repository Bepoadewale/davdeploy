# ticket282 — Record deployment of durable worker claims

PR: https://github.com/Bepoadewale/davdeploy/pull/282
Branch: `docs/record-worker-lease-deployment`

## Problem / goal

Record the production deployment of the merged durable worker-claim and
module-outcome changes with verifiable Terraform, migration, AWS, and health
evidence.

## Current repo state

PR #280 is merged and its code is not yet in the deployed Lambda package.
Production runs the #270 package; App Runner is the only enabled hosted renderer,
and multi-module customer execution is disabled.

## Research / references used

- PR #280 merge commit `ef60ac36d135b8b47242a1a7ffefa92c18d1d165`.
- Plan run `41716352953` and apply run `41716835229`.
- `docs/TERRAFORM_GITHUB_OPERATIONS.md`, `docs/IMPLEMENTATION_STATUS.md`,
  `docs/product/EXECUTION_READINESS_MATRIX.md`, and
  `docs/product/COMPOSED_EXECUTION_GOAL.md`.
- Read-only AWS Lambda, Aurora schema migration, and public health checks after
  apply.

## Work planned for the PR

- Record the exact saved-plan and apply results and deployed commit.
- Record schema version 24, Lambda package verification, and API health.
- Reconcile all current deployment/status documents.
- Preserve all customer workload execution gates and historical evidence.

## Acceptance criteria

- [ ] Applied plan and exact production changes are documented.
- [ ] Migration version and live health check are recorded.
- [ ] Current status docs no longer describe the older package as deployed.
- [ ] No customer workload renderer or multi-module gate is enabled.
- [ ] Documentation checks and required CI pass.

## Acceptance status

Implementation in progress.

## Tests / validation performed

Deployment and post-deployment observations are being recorded in
`docs/test/test282.md`.

## Evidence files produced

- `docs/test/test282.md`.

## Boundaries

This PR records the already completed protected control-plane deployment. It
does not authorize or enable customer workload execution.

## Follow-up work

Continue with the hosted Lambda/API lifecycle integration while keeping its
customer execution gate disabled until the renderer passes composed lifecycle
certification.
