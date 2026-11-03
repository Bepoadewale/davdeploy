# ticket289 — Validate durable lifecycle dependency graphs

PR: https://github.com/Bepoadewale/davdeploy/pull/289
Branch: `fix/validate-dispatch-graph`

## Problem / goal

The trusted CodeBuild boundary revalidates individual lifecycle work fields but did not verify that the serialized list described one complete, uniquely identified dependency graph in operation-correct order. Malformed durable work should be rejected before selecting a renderer or submitting a build.

## Current repo state

The universal plan compiler validates module identifiers and graph references when the approved plan is first compiled. The dispatcher reloads persisted work and resolves fixed renderer bindings. CodeBuild still rejects composed work, and only checked-in renderer bindings can be selected.

## Research / references used

- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `tests/test_universal_execution.py`
- `tests/test_cloud_execution.py`
- Product rule: only typed, checked-in renderer work may cross the execution boundary.

## Work planned for the PR

- Validate serialized graph identity, dependency references, duplicate/self dependencies, operation consistency, cycles, and dependency order at the trusted execution boundary.
- Add positive and adversarial contract tests.
- Do not enable multi-module execution or additional renderers.

## Acceptance criteria

- [x] Invalid or ambiguous graphs fail before any renderer is selected or subprocess can run.
- [x] Valid dependency-ordered work remains accepted for forward and reverse operations.
- [x] No arbitrary command or provider input is introduced.
- [ ] GitHub CI passes before merge.
- [x] Evidence and limitations are recorded accurately.

## Acceptance status

Implementation and local verification pass. GitHub CI is pending.

## Tests / validation performed

`make verify` passed: Actions configuration, Ruff, 433 pytest cases, OpenAPI snapshot, and Docker Compose configuration. Focused lifecycle and cloud-dispatch tests passed: 76 tests. `git diff --check` passed. One existing Starlette `TestClient` deprecation warning about `httpx` appeared; tests passed.

## Evidence files produced

No AWS workload evidence is expected. This PR validates local typed graph inputs only; it does not execute cloud resources.

## Boundaries

No AWS resources or customer workloads were changed. No renderer is enabled. Multi-module CodeBuild execution remains disabled.

## Follow-up work

Implement durable dependency-aware scheduling, typed output bindings, partial-failure recovery and reverse graph cleanup as a separate step before composed customer execution.
