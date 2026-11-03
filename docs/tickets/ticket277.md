# ticket277 — Persist deployment module-instance state

PR: https://github.com/Bepoadewale/davdeploy/pull/277

Branch: `feat/durable-module-instance-state`

## Problem / goal

`CloudExecutionRun` stores a graph and whole-run outputs, but there is no
durable row per module instance. Add tenant/project/run-scoped module-instance
records as the persistence foundation for dependency scheduling, health
observations and exact cleanup. This PR persists the rows during actual run
creation and exposes them in that run's history. It does not claim to implement
module scheduling or state transitions.

## Current repo state

PR #274 validates serverless lifecycle results; #275 added connection/project
artifact and state isolation. App Runner remains the only hosted renderer and
multi-module customer execution is still rejected. `CloudExecutionRun` is
durable but has only whole-run JSON command/evidence/output fields. Database
startup uses SQLAlchemy metadata creation for new tables and must remain safe
for existing databases.

## Research / references used

- `apps/api/src/davdeploy/models.py` (`CloudExecutionRun`)
- `apps/api/src/davdeploy/service.py` run creation and worker result reconciliation
- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/db.py` schema creation/migration compatibility
- `tests/test_cloud_execution.py`

## Work planned for the PR

- Persist stable module-instance identity, owner workspace/project/run, typed
  module ID, state, operation attempt, input digest, outputs and evidence.
- Enforce unique instance identity within a run and idempotent record creation.
- Create rows from the actual compiled run graph and expose only rows associated
  with the requested run and tenant.
- Keep module dispatch and additional renderer execution disabled.

## Acceptance criteria

- [x] Each module in a compiled run has durable, tenant/project-bound initial instance state.
- [x] Instance identity and idempotency key uniqueness are enforced by the database.
- [x] Run history exposes its own persisted module instances, not another run's instances.
- [x] Fresh-database creation and existing-database upgrade from schema version 22 are tested.
- [ ] Focused tests, full verification, clean-room cycle and CI pass.
- [x] Existing execution gates and renderer count remain unchanged.

## Acceptance status

Implementation, focused tests, full repository verification and fresh
clean-room validation passed. PR CI remains pending.

## Tests / validation performed

- `.venv/bin/ruff check apps/api/src/davdeploy/db.py apps/api/src/davdeploy/models.py apps/api/src/davdeploy/service.py tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py` — passed.
- `.venv/bin/python -m pytest tests/test_db_config.py tests/test_cloud_execution.py -q` — 35 passed; one Starlette deprecation warning.
- `make verify` — passed: configuration check, Ruff, 381 tests, OpenAPI snapshot and Compose config; one Starlette deprecation warning.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Fresh clean-room at commit `150b45f`, isolated worktree
  `/tmp/davdeploy-cleanroom-pr277-20261103`, Compose project
  `davdeploy-pr277-20261103`: bootstrap, smoke, API contract, customer-plan
  E2E, all demos, trace check, full verification (381 tests), OPA, Terraform
  validation, Kubernetes render, and scoped cleanup — passed. Local-only; no
  AWS workload was created.

## Evidence files produced

Runnable database and execution behavior will require `docs/test/test277.md`.
No AWS workload is planned unless later code changes require it.

## Boundaries

Do not enable Lambda hosted execution, permit multi-module CodeBuild runs,
broaden IAM or create AWS resources. Do not delete existing database data.

## Follow-up work

Build durable scheduling, leases, dependency outputs, retry/resume, partial
failure recovery and independent cleanup verification on top of these records.
