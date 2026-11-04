# ticket296 — Persist module build identity for safe reconciliation

PR: https://github.com/Bepoadewale/davdeploy/pull/296
Branch: `feat/durable-module-build-identity`

## Problem / goal

Persist the identity of the CodeBuild operation on the exact module instance it executes, so callback reconciliation can progress from run-level records toward safe per-module scheduling without applying one result to every graph node.

## Current repo state

- Backend main includes PR #295 (`464dd0b`), which validates typed outputs and provides a reference resolver.
- The hosted worker still submits/reconciles one build per run and currently advances every module row together.
- The CodeBuild adapter rejects multi-module runs.

## Research / references used

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- PRs #289–#295 and `apps/api/src/davdeploy/service.py`

## Work planned for the PR

- Add a durable, unique CodeBuild identity to a module instance and migrate the database schema safely.
- Associate only the dispatched module with its build and completion result.
- Validate result identity against the run, module instance, operation, and immutable input digest before persisting outcomes.
- Preserve single-renderer behavior and fail closed for unsupported composed dispatch. This PR must not enable a new hosted renderer or workload.
- Update the execution goal and readiness matrix with exact status.

## Acceptance criteria

- [x] Module build identity is durable and unique; legacy rows migrate safely.
- [x] Reconciliation updates only the matching module instance.
- [x] Duplicate, stale, mismatched, or ambiguous callback results cannot overwrite terminal module outcomes.
- [x] Existing single-module behavior remains compatible, including legacy runs without per-module rows.
- [x] Multi-module work remains fail-closed until durable scheduling is complete.
- [x] PR-numbered test/evidence and status documentation are present and accurate.
- [x] Full isolated clean-room cycle passes.
- [ ] GitHub CI passes.

## Acceptance status

Locally verified. CodeBuild submission persists a unique ID on a single module row. SQS/EventBridge reconciliation locates that row and only advances its state. Legacy rows retain the prior run-level fallback. Multi-module submissions remain rejected. PR CI and review remain pending.

## Tests / validation performed

- `uv run pytest -q tests/test_db_config.py tests/test_invitation_email.py tests/test_cloud_execution.py` — 59 passed, one existing Starlette deprecation warning.
- `make verify` — config check, Ruff, full suite (471 passed), OpenAPI snapshot, and Compose config passed.
- `uv run ruff check apps/api/src tests scripts` and `git diff --check` — passed.
- Isolated clean-room cycle passed: `make bootstrap-local`; then smoke, API contract, customer-plan E2E, seed, simple/complex/Day-2/degraded/success/failure/readiness demos, trace check, and `make verify`; then cleanup. See `docs/test/test296.md`.
- PR CI is running; the first `docs-conventions` attempt failed because the ticket headings did not match the repository's required template. The ticket and evidence headings are being corrected.

## Evidence files produced

- `docs/test/test296.md` records local focused/full/clean-room evidence. No AWS workload evidence is claimed or required for this persistence-only change.

## Boundaries

No AWS resources were created, changed, or destroyed. The migration has not been applied to hosted Aurora. This PR does not wire dependency waves into hosted scheduling, support concurrent module builds, enable additional renderers, or prove a composed AWS workload.

## Follow-up work

Wire dependency-ready per-module claims and scheduling into the durable worker. Add concrete input-reference delivery to renderer configuration, safe worker resume, bounded retry/partial-failure handling, reverse cleanup, and hosted AWS certification for supported compositions.
