# ticket298 — Schedule composed lifecycle work one durable module at a time

PR: https://github.com/Bepoadewale/davdeploy/pull/298
Branch: `feat/durable-module-wave-scheduler`

## Problem / goal

Connect the already-validated dependency graph and per-module lifecycle rows to the hosted worker. Dispatch only one dependency-ready registered renderer at a time, persist its result on the exact module instance, and resume the same run for its next eligible module without replaying uncertain work.

## Current repo state

- PR #297 merged as `e28fa23`; Terraform outputs from the checked-in Lambda/API renderer are validated and stored as typed outputs on the exact callback module row.
- The execution graph compiler validates dependencies and computes deterministic dependency order.
- The CodeBuild adapter rejects graphs with more than one module; current worker transitions and callbacks still update every module row together.
- The dispatcher accepts typed instance/reference fields but intentionally rejects unresolved dependency/input bindings.
- Hosted multi-module execution remains disabled and no composed customer AWS workload is certified.

## Research / references used

- `apps/api/src/davdeploy/universal_execution.py`: graph validation, dispatch ordering, typed input resolver.
- `apps/api/src/davdeploy/cloud_execution.py`: fixed renderer registry and CodeBuild adapter.
- `apps/api/src/davdeploy/service.py`: worker claim, lease, callback reconciliation and per-module state transitions.
- `apps/api/src/davdeploy/models.py`: durable run/module rows and unique per-module CodeBuild build identity.
- `scripts/customer-workload-dispatcher.sh`: exact renderer allowlist and fail-closed input boundary.
- PRs #289–#297 and `docs/product/COMPOSED_EXECUTION_GOAL.md`.

## Work planned for the PR

- Select one dependency-ready module instance from the immutable lifecycle graph at each worker claim.
- Bind each CodeBuild build ID to only that selected module instance; never assign one runner result to all graph rows.
- On a successful terminal callback, durably mark only the exact module outcome and enqueue the next dependency-ready work item.
- Halt dependent work after failure or reconciliation-required status; do not automatically replay uncertain external operations.
- Preserve reverse dependency order for destroy/rollback/cleanup.
- Keep modules with input bindings fail-closed until their concrete renderer input resolver is implemented; no placeholder values or raw secret contents.
- Add state-machine and race/recovery tests, PR-numbered ticket/evidence, and update readiness documentation.

## Acceptance criteria

- [ ] The worker selects only nodes whose dependencies have operation-appropriate terminal outcomes.
- [ ] One CodeBuild build ID maps to one module instance, including duplicate module types with distinct instance IDs.
- [ ] A completed callback advances only its exact module row and deterministically wakes the next eligible node.
- [ ] Failed or uncertain work blocks dependent nodes and is not blindly retried.
- [ ] Reverse lifecycle ordering is preserved for cleanup operations.
- [ ] Unsupported bindings and renderer combinations remain fail-closed.
- [ ] Existing single-module App Runner and Lambda/API lifecycle contracts remain compatible.
- [ ] Focused tests, full verification, clean-room cycle, documentation checks, and GitHub CI pass.
- [ ] Hosted execution remains gated; this PR alone does not claim arbitrary AWS workload deployment.

## Acceptance status

Implementation has not started. Multi-module CodeBuild remains disabled while the PR adds durable per-instance scheduling and exact callback attribution.

## Tests / validation performed

Pending implementation.

## Evidence files produced

`docs/test/test298.md` will record local/clean-room validation. No real AWS resource mutation is planned for this scheduler-only change.

## Boundaries

This PR does not deliver resolved typed inputs to Terraform, add new renderer families, or enable general customer execution. Follow-up work must connect successful source outputs to validated renderer inputs and add/certify concrete renderers before composed AWS workloads can run.

## Follow-up work

Resolve typed dependency outputs into registered renderer inputs and implement/certify the concrete renderers needed for composed workloads.
