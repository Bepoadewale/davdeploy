# ticket280 — Durable cloud execution worker leases

PR: https://github.com/Bepoadewale/davdeploy/pull/280

Branch: `feat/durable-worker-claims`

## Problem / goal

Give a worker exclusive, durable ownership of a queued cloud execution run and
prevent a stale worker from overwriting a newer result. A lease expiring must
not itself replay external infrastructure work: the run must become explicitly
reconciliation-required until the exact external operation is known.

## Current repo state

- Backend main is `07e3916` after PR #279 and preserves historical Terraform
  monitor results accurately.
- PRs #277/#278 persist module-instance outcomes for the App Runner-only hosted
  execution path. The database does not yet persist worker claim identity or
  lease expiry.
- `ProductService.run_next_cloud_execution()` currently selects the oldest
  `QUEUED` run and changes it to `RUNNING` without an atomic claim predicate.
- The worker loops every 250 ms, so two workers can select the same queued row.
- PR #280 will not broaden the renderer registry or lift the product execution
  gate.

## Research / references used

- `apps/api/src/davdeploy/models.py` — `CloudExecutionRun`
- `apps/api/src/davdeploy/service.py` — queue and run worker methods
- `apps/api/src/davdeploy/db.py` — versioned schema migrations through v23
- `apps/api/src/davdeploy/worker.py` — durable worker loop
- `tests/test_cloud_execution.py`
- `docs/product/COMPOSED_EXECUTION_GOAL.md` and
  `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

- Add migration-backed claim owner, lease expiry and claim-version fields.
- Atomically claim only a queued row using a conditional state/version update;
  concurrent workers must never both own the same claim.
- Make worker completion conditional on the same claim token/version.
- Detect expired claims and mark the run for reconciliation without resubmitting
  apply/destroy work or asserting success/failure without evidence.
- Leave pre-lease `RUNNING` rows without a claim token untouched during rolling
  deployment; their owner status cannot be inferred from the new lease fields.
- Preserve audit history, tenant/project/plan digest scope, and the current
  single-renderer fail-closed behavior.
- Test migration upgrade, concurrent claims, stale completion rejection,
  expired-lease behavior, and non-replay of external operations.
- Run focused/full verification and the required local clean-room cycle; update
  goal/readiness/backlog documents with exact boundaries.

## Acceptance criteria

- [x] Existing databases migrate idempotently and the latest schema is v24.
- [x] Only one worker can claim a given queued run.
- [x] Only the current claim owner can persist worker completion.
- [x] An expired claim is visible for reconciliation and is never blindly replayed.
- [x] Existing single-renderer execution and fail-closed gates remain intact.
- [x] Tenant, project and approved digest checks remain enforced.
- [x] Focused tests, full verification and documentation checks pass.
- [x] Clean-room cycle passes.
- [x] Required PR CI passes.

## Acceptance status

Focused worker and migration tests, full verification, the isolated clean-room
cycle and all seven required PR CI jobs pass.

## Tests / validation performed

- `.venv/bin/ruff check apps/api/src/davdeploy/service.py apps/api/src/davdeploy/models.py apps/api/src/davdeploy/db.py tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py` — passed.
- `.venv/bin/python -m pytest tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py -q` — 50 passed; one existing Starlette deprecation warning.
- `make verify` — 397 passed; Ruff/configuration checks, OpenAPI snapshot and Compose configuration passed; one existing Starlette deprecation warning.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Fresh clean-room at commit `3f32dc9`, isolated worktree
  `/tmp/davdeploy-cleanroom-pr280-20261103`, Compose project
  `davdeploy-cleanroom-pr280-20261103`: bootstrap, smoke, API contract,
  customer-plan E2E, seed, simple/complex/degraded/Day-2/canonical/failure/readiness
  demos, trace check, full verification (396 tests), OPA (3/3), Terraform offline
  validation, Kubernetes render and scoped cleanup — passed. No AWS workload was
  created.
- GitHub Actions run
  [41711545894](https://github.com/Bepoadewale/davdeploy/actions/runs/41711545894)
  passed all seven required jobs on commit `4787798`.

## Evidence files produced

`docs/test/test280.md`.

## Boundaries

No AWS resource changes or customer workload execution. No widening of renderer
support, IAM permissions, trust policies or Terraform authority. No automatic
replay of an uncertain apply or destroy. No deletion of customer or existing
local data.

## Follow-up work

Reconcile expired leases against authenticated CodeBuild/SQS evidence. Add
dependency-aware graph dispatch only after claim/reconciliation semantics are
validated end to end.
