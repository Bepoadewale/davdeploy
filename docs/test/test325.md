# test325 - durable hosted Nova plan requests

Date: 2026-11-05
Execution type: Local unit, API-code, and database-migration validation; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: Retry/fairness follow-up on `feat/nova-plan-request-api`; no customer workload was used
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_nova_plan_runs.py tests/test_lambda_worker.py
make openapi-update PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
make verify PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The first full verification during the worker-queue change reported 692 passed and 4 failures; all four migration assertions still expected schema version 26. After correcting those assertions and adding durable queueing, retry binding, and fair dispatch, the focused suite passed 13 tests. The latest `make verify` passed with 703 tests, Ruff, config checks, OpenAPI snapshot validation, and Compose configuration validation. Documentation conventions and `git diff --check` also passed. No AWS calls or customer resources were used.

## Resources created

No AWS resources. Unit tests use isolated in-memory SQLite databases and mocked S3/CodeBuild clients.

## Teardown

Not applicable; no cloud workload or persistent local service stack is in scope.

## Final boundary

The route is disabled unless `DAVDEPLOY_NOVA_PLAN_RUNNER_READY=true` and the exact project, artifact bucket, KMS key, and bucket owner are configured. The isolated CodeBuild project from PR #324 currently fails closed. Migration 29 backfills existing run keys and records each accepted key in `generated_plan_run_idempotency_keys`, so a later request cannot reuse a key with different content. Explicit retries require a fresh idempotency key and are limited to confirmed `FAILED` runs; `RECONCILIATION_REQUIRED` work cannot be retried. The worker guarantees one fair dispatch slot per queue kind before it repeats a queue. Even if a build reports `SUCCEEDED`, this code records `BUILD_SUCCEEDED_UNVERIFIED` until a trusted result and saved-plan artifact verifier exists. This PR does not apply, destroy, or create customer AWS resources.

## Known limitations

The customer-side plan-only role, its CodeBuild trust and broker permissions, the fixed runner result contract, verified saved-plan persistence, tenant-scoped remote state and lock, and regional pricing integration remain follow-up work. The current request record deliberately cannot be approved or used for deployment.
