# ticket298 — Schedule composed lifecycle work one durable module at a time

PR: https://github.com/Bepoadewale/davdeploy/pull/298
Branch: `feat/durable-module-wave-scheduler`

## Problem / goal

Connect the already-validated dependency graph and per-module lifecycle rows to the hosted worker. Dispatch only one dependency-ready registered renderer at a time, persist its result on the exact module instance, and resume the same run for its next eligible module without replaying uncertain work.

## Current repo state

- PR #297 merged as `e28fa23`; Terraform outputs from the checked-in Lambda/API renderer are validated and stored as typed outputs on the exact callback module row.
- The execution graph compiler validates dependencies and computes deterministic dependency order.
- The CodeBuild adapter previously rejected graphs with more than one module; this PR now selects one ready node at a time and binds the build to that instance.
- Per-instance callbacks can enqueue the next node, while unresolved input bindings, repeated renderer types and shared Terraform state roots remain fail-closed.
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

- [x] The worker selects only nodes whose dependencies have operation-appropriate terminal outcomes.
- [x] One CodeBuild build ID maps to one module instance; duplicate types remain rejected until their renderer state is instance-scoped.
- [x] A completed callback advances only its exact module row and deterministically wakes the next eligible node.
- [x] Failed or uncertain work blocks dependent nodes and is not blindly retried.
- [x] Reverse lifecycle ordering is preserved for cleanup operations.
- [x] Unsupported bindings and renderer combinations remain fail-closed.
- [x] Existing single-module App Runner and Lambda/API lifecycle contracts remain compatible.
- [ ] Focused tests, full verification, clean-room cycle, documentation checks, and GitHub CI pass.
- [x] Hosted execution remains gated; this PR alone does not claim arbitrary AWS workload deployment.

## Acceptance status

The worker now selects one dependency-ready module row, assigns only that row the worker state/build identity, and queues the next dependency after a successful callback. Uncertain outcomes reconcile only the active module and leave undispatched rows untouched. Renderer inputs, repeated renderer types, and shared Terraform state roots remain fail-closed. Focused tests, `make verify`, and the isolated clean-room cycle pass; GitHub CI is pending.

## Tests / validation performed

Focused tests: `uv run pytest -q tests/test_universal_execution.py tests/test_cloud_execution.py tests/test_renderer_dispatcher.py` passed (114 passed; one existing Starlette deprecation warning). `make verify` passed (485 tests; one existing warning). `bash -n scripts/customer-workload-dispatcher.sh`, OpenAPI snapshot, Compose configuration, Ruff, documentation conventions, and `git diff --check` passed. The clean-room validation passed on `b2f8a27`; GitHub CI is pending.

## Evidence files produced

`docs/test/test298.md` records local and clean-room validation. No real AWS resource mutation is planned for this scheduler-only change.

## Boundaries

This PR does not deliver resolved typed inputs to Terraform, add new renderer families, or enable general customer execution. Follow-up work must connect successful source outputs to validated renderer inputs and add/certify concrete renderers before composed AWS workloads can run.

## Follow-up work

Resolve typed dependency outputs into registered renderer inputs and implement/certify the concrete renderers needed for composed workloads.
