# ticket293 — Support multiple instances of one module type

PR: https://github.com/Bepoadewale/davdeploy/pull/293
Branch: `feat/module-instance-identities`

## Problem / goal

The lifecycle compiler currently treats a module type identifier as the graph node identity and rejects duplicates. A real workload may need multiple instances of the same type, such as separate upload and archive buckets. Persisted rows already have distinct `instance_id` and `module_id` fields, but the compiler and evidence contract do not use them separately.

## Current repo state

PRs #289–#291 validate lifecycle graph inputs, compute dependency waves and persist per-module outcomes, but the compiler still requires unique module identifiers. The hosted worker remains single-renderer and fails closed for multi-module work.

## Research / references used

- `apps/api/src/davdeploy/domain.py` (`ArchitectureModule`)
- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/composed_deployment.py`
- `apps/api/src/davdeploy/service.py` module-instance persistence
- `apps/api/src/davdeploy/cloud_execution.py`
- `tests/test_universal_execution.py`, `tests/test_cloud_execution.py`

## Work planned for the PR

- Add optional instance identity to architecture modules while preserving old plans that use one instance per module type.
- Key dependencies, lifecycle ordering, serialized work, evidence and dispatch waves by instance ID, while resolving renderer capability by module type.
- Persist distinct type and instance identities and idempotency keys in existing module-instance rows.
- Reject duplicate instance IDs, ambiguous type-based dependency references and invalid dependency graphs.
- Add tests for two instances of one module type, dependencies between instances, duplicate type evidence and backward compatibility.

## Acceptance criteria

- [x] Two or more nodes may use the same module type when each has a unique instance ID.
- [x] Dependencies and observations bind to instance IDs; renderer selection uses module type.
- [x] Legacy single-instance plans remain valid without an explicit instance ID.
- [x] Invalid or ambiguous identities fail before dispatch.
- [x] Worker dispatch remains single-module and no new renderer is enabled.
- [ ] Focused tests, full verification and required GitHub CI pass.

## Acceptance status

Implementation is complete. Instance identity is now carried from architecture compilation
through ordered lifecycle work, runner validation, dispatch state, observation evidence,
execution-run persistence, and per-instance idempotency keys. Existing single-module plans
continue to use their module type as the default instance ID.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_universal_execution.py tests/test_composed_deployment.py tests/test_cloud_execution.py tests/test_customer_plan_review.py` — **125 passed**.
- `make verify` — configuration check passed; Ruff passed; **449 tests passed**; OpenAPI snapshot matched; Docker Compose configuration passed.
- `.venv/bin/ruff check ...` on all changed Python files — passed.
- `git diff --check` — passed.
- Full local clean-room lifecycle cycle — pending.
- Required GitHub PR checks — pending.

## Evidence files produced

No AWS workload evidence is expected. This PR changes the local lifecycle graph and persistence contract without dispatching a customer workload. No AWS resources were created or changed.

## Boundaries

No database schema migration or AWS mutation is expected; existing `instance_id` and `module_id` columns are used. Multi-module hosted execution remains disabled.

## Follow-up work

Wire independently claimed module instances and outputs into durable worker scheduling and composed renderer execution.
