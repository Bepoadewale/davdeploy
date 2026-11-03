# test280 — Durable cloud execution worker leases

Date: 2026-11-03

Execution type: Local database, worker-state and migration validation. No AWS
workload is created.

Customer repository: None.

Commit: Pending final PR commit.

AWS account: Not used.

AWS region: Not used.

## Resources created

Temporary SQLite databases, cloud execution run records, fake worker results,
and pytest temporary files.

## Commands executed

`.venv/bin/ruff check apps/api/src/davdeploy/service.py apps/api/src/davdeploy/models.py apps/api/src/davdeploy/db.py tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py` — passed.

`.venv/bin/python -m pytest tests/test_cloud_execution.py tests/test_db_config.py tests/test_invitation_email.py -q` — 49 passed; one existing Starlette deprecation warning.

`make verify` — 396 passed; Ruff/configuration checks, OpenAPI snapshot and
Compose configuration passed; one existing Starlette deprecation warning.

`python scripts/check_doc_conventions.py` and `git diff --check` — passed.

Clean-room and GitHub CI are pending.

## Observed result

One conditional database update owns the queued run. A second claim returns no
work. Expired leases move to `RECONCILIATION_REQUIRED`, clear claim credentials,
record that automatic replay is disabled, and reject late results from the old
owner. Adapter exceptions also require reconciliation. Configured adapter
results release the lease and preserve the separate run-attempt counter.

## Teardown

Pytest temporary files and database connections are isolated. No AWS resource
is created or deleted.

## Final boundary

This evidence will cover atomic worker ownership and safe reconciliation for
uncertain worker outcomes only. It will not prove graph dispatch, customer
infrastructure execution, or deployment readiness.
