# ticket278 — Persist verified module lifecycle outcomes

PR: https://github.com/Bepoadewale/davdeploy/pull/278

Branch: `feat/persist-module-run-outcomes`

## Problem / goal

PR #277 persists module graph instances, but they remain `NOT_DISPATCHED` after
the current single-module worker/CodeBuild path finishes. Advance only the
module rows attached to that run from durable queue, worker and verified
CodeBuild outcomes. Preserve idempotency and never treat plan approval or
resource creation as health evidence.

## Current repo state

Backend main includes PR #277 (`6c39ad3`), which adds the module-instance table,
schema migration 23, graph persistence at run creation and run-scoped history.
App Runner remains the only hosted renderer. CodeBuild rejects mixed/multiple
module work, and the Lambda renderer remains disabled.

## Research / references used

- `apps/api/src/davdeploy/models.py` (`CloudExecutionRun`, `CloudExecutionModuleInstance`)
- `apps/api/src/davdeploy/service.py` queue, worker and CodeBuild reconciliation
- `apps/api/src/davdeploy/cloud_execution.py` bounded result states
- `tests/test_cloud_execution.py`

## Work planned for the PR

- Define legal durable node-state transitions and idempotent same-result replay.
- Persist queue/submission, worker start, trusted completion and failure states
  only for instances belonging to the exact run, workspace, project and plan digest.
- Store operation-level status/evidence without copying secret or raw output
  payloads into module records.
- Test cross-run/cross-project mismatch, duplicate completion and no terminal
  state overwrite.
- Keep renderer and multi-module execution gates unchanged.

## Acceptance criteria

- [x] Existing single-renderer runs persist truthful module queue/start/terminal outcomes.
- [x] Duplicate events are idempotent and stale/different terminal results cannot overwrite evidence.
- [x] Cross-run or digest-mismatched module state is rejected.
- [x] Tests prove submission/plan and apply-awaiting-health states remain distinct.
- [ ] Focused tests, full verification, clean-room cycle and CI pass.
- [x] No additional customer renderer or mixed-module execution is enabled.

## Acceptance status

Implementation, focused tests, full repository verification and fresh
clean-room validation passed. PR CI remains pending.

## Tests / validation performed

- `.venv/bin/ruff check apps/api/src/davdeploy/service.py tests/test_cloud_execution.py` — passed.
- `.venv/bin/python -m pytest tests/test_cloud_execution.py -q` — 33 passed; one Starlette deprecation warning.
- `make verify` — passed: configuration check, Ruff, 383 tests, OpenAPI snapshot and Compose config; one Starlette deprecation warning.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Fresh clean-room at commit `46f673b`, isolated worktree
  `/tmp/davdeploy-cleanroom-pr278-20261103`, Compose project
  `davdeploy-pr278-20261103`: bootstrap, smoke, API contract, customer-plan
  E2E, all demos, trace check, full verification (383 tests), OPA, Terraform
  validation, Kubernetes render and scoped cleanup — passed. Local-only; no
  AWS workload was created.

## Evidence files produced

Runnable execution behavior requires `docs/test/test278.md`. No AWS workload is
planned for this PR.

## Boundaries

No AWS mutation, renderer enablement, IAM expansion, worker arbitrary command,
or multi-module dispatch.

## Follow-up work

Add durable leases, worker restart/resume, bounded retry, dependency scheduling,
partial-failure compensation and cleanup verification across composed graphs.
