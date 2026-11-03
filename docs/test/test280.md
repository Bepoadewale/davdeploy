# test280 — Durable cloud execution worker leases

Date: 2026-11-03

Execution type: Local database, worker-state and migration validation. No AWS
workload is created.

Customer repository: None.

Commit: `3f32dc9` for code and the clean-room cycle. Full local verification,
focused coverage and CI evidence are on subsequent PR commits.

AWS account: Not used.

AWS region: Not used.

## Resources created

Temporary SQLite databases, cloud execution run records, fake worker results,
and pytest temporary files.

## Commands executed

`.venv/bin/ruff check apps/api/src/davdeploy/service.py apps/api/src/davdeploy/models.py apps/api/src/davdeploy/db.py tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py` — passed.

`.venv/bin/python -m pytest tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py -q` — 50 passed; one existing Starlette deprecation warning.

`make verify` — 397 passed; Ruff/configuration checks, OpenAPI snapshot and
Compose configuration passed; one existing Starlette deprecation warning.

`python scripts/check_doc_conventions.py` and `git diff --check` — passed.

GitHub Actions run
[`41712556149`](https://github.com/Bepoadewale/davdeploy/actions/runs/41712556149)
passed all seven required jobs on the PR head after the evidence updates.

Fresh clean-room at commit `3f32dc9`, isolated worktree
`/tmp/davdeploy-cleanroom-pr280-20261103`, Compose project
`davdeploy-cleanroom-pr280-20261103`: bootstrap, smoke, API contract,
customer-plan E2E, seed, simple/complex/degraded/Day-2/canonical/failure/readiness
demos, trace check, full verification (396 tests), OPA (3/3), Terraform offline
validation, Kubernetes render, and scoped cleanup — passed. No AWS workload was
created. GitHub CI passed in run 41712556149.

## Observed result

One conditional database update owns the queued run. A second claim returns no
work. Expired leases move to `RECONCILIATION_REQUIRED`, clear claim credentials,
record that automatic replay is disabled, and reject late results from the old
owner. Adapter exceptions also require reconciliation. A pre-lease `RUNNING`
record with no token is left unchanged because an older worker might still own
it. Configured adapter results release the lease and preserve the separate
run-attempt counter.

## Teardown

Pytest temporary files and database connections are isolated. No AWS resource
is created or deleted. The clean-room Compose stack and its private local
PostgreSQL volume were stopped and removed by `make clean-local`.

## Final boundary

This evidence will cover atomic worker ownership and safe reconciliation for
uncertain worker outcomes only. It will not prove graph dispatch, customer
infrastructure execution, or deployment readiness.
