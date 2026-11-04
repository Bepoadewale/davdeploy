# ticket290 — Compute dependency-safe dispatch waves

PR: https://github.com/Bepoadewale/davdeploy/pull/290
Branch: `feat/dependency-dispatch-waves`

## Problem / goal

The durable execution rows record dependencies, but there is no shared deterministic helper that identifies which modules can safely begin after their prerequisites have completed. Implement a fail-closed scheduling contract before wiring it into the worker.

## Current repo state

The worker currently advances module rows together with one renderer run, and CodeBuild rejects multi-module runs. Dependency-aware scheduling is not active. This PR must not change that behavior or enable customer graph execution.

## Research / references used

- `apps/api/src/davdeploy/composed_deployment.py`
- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/models.py` (`CloudExecutionModuleInstance`)
- `tests/test_universal_execution.py`
- `tests/test_cloud_execution.py`

## Work planned for the PR

- Add a deterministic pure helper that returns the current dispatch wave from a compiled plan, operation, and persisted per-module states.
- Require complete state coverage, known states, and successful prerequisite outcomes; keep unresolved, failed, and reconciliation-required dependencies blocked.
- Reverse prerequisite ordering for rollback and destroy operations.
- Add tests for chains, independent parallel nodes, cleanup order, and fail-closed states.

## Acceptance criteria

- [x] Only undispatched nodes with successful prerequisites are returned.
- [x] Independent nodes may share a wave; dependent nodes cannot.
- [x] Cleanup operations schedule dependents before their dependencies.
- [x] Missing/extra state rows and unknown states fail closed; failed and uncertain prerequisites remain blocked.
- [x] The helper does not submit cloud work or alter worker behavior.
- [x] GitHub CI run [41745014343](https://github.com/Bepoadewale/davdeploy/actions/runs/41745014343) passes all seven jobs.

## Acceptance status

`make verify` passed: Actions configuration, Ruff, 441 pytest cases, OpenAPI snapshot and Docker Compose configuration. `scripts/check_doc_conventions.py` and `git diff --check` passed. One existing Starlette `TestClient` deprecation warning about `httpx` appeared; tests passed.

## Tests / validation performed

Implementation, local verification and all seven GitHub CI jobs pass.

## Evidence files produced

No AWS workload evidence is expected; this is a deterministic local scheduling contract.

## Boundaries

No customer execution, CodeBuild dispatch, database migration, AWS resource, or renderer gate is changed.

## Follow-up work

Wire per-module claims, outcomes, outputs, retries and compensation into durable orchestration only after module-level dispatcher support is implemented.
