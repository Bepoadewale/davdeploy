# ticket291 — Persist per-module execution outcomes

PR: https://github.com/Bepoadewale/davdeploy/pull/291
Branch: `feat/persist-module-specific-outcomes`

## Problem / goal

Execution run transitions currently advance every persisted module row to the same state. A composed runner will need to persist each module's own terminal state, outputs, and evidence without changing unrelated nodes or overwriting an existing outcome.

## Current repo state

Per-module rows already exist with independent state, outputs, evidence, dependency and version fields. The current worker supports a single renderer and advances all rows from one run-level result. Dependency dispatch-wave calculation is implemented, but is not wired into cloud execution.

## Research / references used

- `apps/api/src/davdeploy/models.py` (`CloudExecutionModuleInstance`)
- `apps/api/src/davdeploy/service.py` (`_advance_cloud_execution_module_instances`)
- `apps/api/src/davdeploy/composed_deployment.py`
- `tests/test_cloud_execution.py`

## Work planned for the PR

- Add a typed module outcome value with state, outputs, and evidence.
- Extend the existing scoped, optimistic-concurrency transition helper to persist a selected set of per-module outcomes while preserving the existing run-wide call behavior.
- Reject unknown module keys, invalid terminal states, and conflicting/replayed outcomes.
- Add tests for independent row transitions, output/evidence persistence, idempotency and scope protection.

## Acceptance criteria

- [ ] A module-specific outcome updates only its matching run/project/workspace/digest-scoped row.
- [ ] Outputs and evidence are persisted with the state transition.
- [ ] Identical repeated outcomes are idempotent; conflicting state or payload replay is rejected.
- [ ] Existing run-wide transitions continue to pass.
- [ ] Focused and full verification plus GitHub CI pass.
- [ ] No worker scheduling, CodeBuild behavior, or renderer enablement changes.

## Acceptance status

Pending implementation.

## Tests / validation performed

Pending implementation.

## Evidence files produced

No AWS workload evidence is expected. This PR changes local persistence behavior only.

## Boundaries

No cloud resources, customer workloads, schema migrations, or renderer gates are changed.

## Follow-up work

Wire module-level outcome persistence into a durable worker scheduler only after independent renderer invocation and reconciliation are implemented.
