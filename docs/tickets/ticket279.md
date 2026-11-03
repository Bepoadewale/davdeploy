# ticket279 — Make Terraform mutation monitoring authoritative

PR: https://github.com/Bepoadewale/davdeploy/pull/279

Branch: `fix/terraform-monitor-exit-locks`

## Problem / goal

The local Terraform run monitor currently launches Terraform detached, records
only its PID, and changes any vanished PID to `FINISHED_UNKNOWN_EXIT`. The local
registry has 40 such historical records and no active Terraform processes.
Unknown means exactly that: those records must not be interpreted as success.
The monitor also rewrites its JSON registry non-atomically and has no OS-level
lock preventing two simultaneous starts from mutating the same state root.

Make future runs observable from an independently supervised child process,
record exact exit status, serialize registry updates, and hold a per-root lock
for the complete apply/destroy. Keep uncertainty explicit if the monitor itself
cannot prove the child result.

## Current repo state

- Backend main includes PR #278 (`8868836`), which persists per-module outcome
  transitions for the current single-renderer worker.
- `scripts/terraform_run_monitor.py` stores `RUNNING` and later infers only
  `FINISHED_UNKNOWN_EXIT` from a missing PID.
- Its current test checks only that a nonexistent PID becomes unknown.
- Existing account/profile: AWS account `654654474502`, profile
  `ai-platform-pilot-key`; this PR will not call AWS or mutate Terraform state.

## Research / references used

- `scripts/terraform_run_monitor.py` and `tests/test_terraform_run_monitor.py`
- `docs/tickets/ticket247.md` and `docs/test/test247.md`
- `~/.codex/AGENTS.md` Terraform monitoring requirements
- `docs/product/COMPOSED_EXECUTION_GOAL.md` monitor reliability requirement

## Work planned for the PR

- Run Terraform under a detached supervisor that waits for the exact child and
  records terminal state and exit code.
- Write the run registry atomically under a process-safe file lock.
- Hold an operating-system per-root lock for the duration of the mutation and
  reject a second start for that root.
- Reject duplicate run IDs and preserve unknown outcomes as unknown.
- Avoid persisting secret-bearing argument values in registry metadata.
- Add integration tests using a temporary fake Terraform executable for both
  zero and nonzero exit codes, concurrent same-root starts, and safe metadata.
- Reconcile the goal handoff with merged PR #278, live PR #270 deployment and
  health evidence, and remaining hosted-execution gaps.

## Acceptance criteria

- [x] A successful child records a terminal success state and exit code 0.
- [x] A failing child records a terminal failure state and its nonzero exit code.
- [x] A monitor/process disappearance cannot be mistaken for a successful
  Terraform exit; the result remains explicitly unknown.
- [x] Registry replacement is atomic and concurrent updates do not overwrite
  one another.
- [x] Concurrent mutations for the same resolved root are refused while a run
  holds its lock; different roots remain independent.
- [x] Secret-like argument values are not persisted in registry metadata.
- [x] Existing historical `FINISHED_UNKNOWN_EXIT` entries are not rewritten
  as success without authoritative evidence.
- [x] Focused tests, full verification and documentation checks pass.
- [x] Full clean-room cycle passes.
- [x] Required CI passes.
- [x] Goal handoff accurately records #278 and the remaining execution work.

## Acceptance status

Focused tests, full verification, documentation checks, isolated clean-room
validation and all seven required PR CI jobs pass. This PR changes local
operator tooling only and creates no AWS resources.

## Tests / validation performed

- `.venv/bin/ruff check scripts/terraform_run_monitor.py tests/test_terraform_run_monitor.py` — passed.
- `.venv/bin/python -m pytest tests/test_terraform_run_monitor.py -q` — 8 passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- `make verify` — 390 passed, Ruff/configuration checks, OpenAPI snapshot and
  Compose configuration passed; one existing Starlette deprecation warning.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Fresh clean-room at commit `5f85f1c`, isolated worktree
  `/tmp/davdeploy-cleanroom-pr279-20261103`, Compose project
  `davdeploy-cleanroom-pr279-20261103`: bootstrap, smoke, API contract,
  customer-plan E2E, seed, simple/complex/degraded/Day-2/failure/readiness demos,
  trace check, full verification (390 tests), OPA (3/3), Terraform offline
  validation, Kubernetes render and scoped cleanup — passed. No AWS workload
  was created.
- GitHub Actions run
  [41705992991](https://github.com/Bepoadewale/davdeploy/actions/runs/41705992991)
  passed all seven required jobs on commit `0819c62`.

## Evidence files produced

`docs/test/test279.md`.

## Boundaries

No AWS calls, Terraform apply/destroy, mutation of the existing run registry,
rewriting of historical unknown results, or deletion of existing files.

## Follow-up work

Use the corrected monitor for every later controlled Terraform apply/destroy.
Then continue durable hosted worker leases, restart/resume and composed graph
execution under the main execution-engine goal.
