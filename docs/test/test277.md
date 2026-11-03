# test277

Date: 2026-11-03

Execution type: local database/model and API-service validation. No AWS workload was created.

Customer repository: None.

Commit: `150b45f` (migration and final clean-room validation).

AWS account: Not used.

AWS region: Not used.

## Resources created

Local test database rows for cloud execution runs and module-instance records.

## Commands executed

`make verify` passed after the model, service and version 23 migration changes:
381 tests passed, Ruff and configuration checks passed, the OpenAPI snapshot
matched, and Compose configuration validated. One existing Starlette
deprecation warning was emitted. Focused cloud-execution and database tests
passed (35 total).

## Observed result

The fresh clean-room at `150b45f` passed in isolated worktree
`/tmp/davdeploy-cleanroom-pr277-20261103`, using Compose project
`davdeploy-pr277-20261103`. The fail-fast sequence included bootstrap, smoke,
API contract, customer-plan E2E, all simple/complex/degraded/Day-2/failure/
readiness demos, trace check, `make verify` (381 tests), OPA, Terraform
validation, Kubernetes render, and scoped cleanup. No AWS workload was run.

## Teardown

Local test databases are isolated by the test suite. No cloud resource teardown
was required.

## Final boundary

This PR persists run graph nodes as `NOT_DISPATCHED`. It does not schedule or
execute module work, enable Lambda, or prove a hosted customer deployment.
