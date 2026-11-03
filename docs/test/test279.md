# test279 — Terraform monitor exit and lock handling

Date: 2026-11-03

Execution type: Local process and filesystem validation. No AWS or Terraform
infrastructure operations are performed.

Customer repository: None.

Commit: `5f85f1c`.

AWS account: Not used.

AWS region: Not used.

## Resources created

Temporary local files and fake Terraform executables under pytest's isolated
temporary directory.

## Commands executed

`.venv/bin/ruff check scripts/terraform_run_monitor.py tests/test_terraform_run_monitor.py` —
passed.

`.venv/bin/python -m pytest tests/test_terraform_run_monitor.py -q` — 8 passed.

`make verify` — 390 passed, Ruff/configuration checks, OpenAPI snapshot, and
Compose configuration passed. One existing Starlette deprecation warning.

`python scripts/check_doc_conventions.py` and `git diff --check` — passed.

GitHub Actions run
[`41705992991`](https://github.com/Bepoadewale/davdeploy/actions/runs/41705992991)
passed all seven required jobs on commit `0819c62`.

Fresh clean-room at commit `5f85f1c`, isolated worktree
`/tmp/davdeploy-cleanroom-pr279-20261103`, Compose project
`davdeploy-cleanroom-pr279-20261103`: bootstrap, smoke, API contract,
customer-plan E2E, seed, simple/complex/degraded/Day-2/failure/readiness demos,
trace check, full verification (390 tests), OPA (3/3), Terraform offline
validation, Kubernetes render, and scoped cleanup — passed. No AWS workload was
created.

## Observed result

The fake Terraform process returned exit code 0 and was recorded as
`SUCCEEDED`; a process returning 23 was recorded as `FAILED` with exit code 23.
Two simultaneous starts against one root allowed only one mutation. Runs on two
different roots both completed and both remained in the registry. A secret-like
Terraform variable value was absent from persisted metadata. A vanished legacy
run remained explicitly `FINISHED_UNKNOWN_EXIT`, not success.

## Teardown

Pytest temporary directories are isolated and removed by the test runner.
The existing Terraform run registry and all AWS resources are unchanged.

## Final boundary

Tests verify process outcome recording, metadata handling, and local state-root
locking only. They do not validate Terraform resource behavior, an AWS account,
a customer workload, or the product's hosted deployment runner.
