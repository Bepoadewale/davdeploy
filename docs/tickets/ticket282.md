# ticket282 — Record deployment of durable worker claims

PR: https://github.com/Bepoadewale/davdeploy/pull/282
Branch: `docs/record-worker-lease-deployment`

## Problem / goal

Record the production deployment of the merged durable worker-claim and
module-outcome changes with verifiable Terraform, migration, AWS, and health
evidence.

## Current repo state

PR #280 is merged. The reviewed apply has deployed the module-outcome and worker
lease changes through schema version 24. App Runner remains the only enabled
hosted renderer, and multi-module customer execution is disabled. This PR
reconciles current status documentation with that deployment.

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

- [x] Applied plan and exact production changes are documented.
- [x] Migration version and live health check are recorded.
- [x] Current status docs no longer describe the older package as deployed.
- [x] No customer workload renderer or multi-module gate is enabled.
- [ ] Documentation checks and required CI pass.

## Acceptance status

Deployment and read-only post-deployment checks are complete. Documentation
updates are in progress; the PR is not ready until required checks pass.

## Tests / validation performed

Deployment and post-deployment observations are being recorded in
`docs/test/test282.md`.

- `git diff --check` — passed.
- `python scripts/check_doc_conventions.py` — passed.

## Evidence files produced

- `docs/test/test282.md`.

## Boundaries

This PR records the already completed protected control-plane deployment. It
does not authorize or enable customer workload execution.

## Follow-up work

Continue with the hosted Lambda/API lifecycle integration while keeping its
customer execution gate disabled until the renderer passes composed lifecycle
certification.
