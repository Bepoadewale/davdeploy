# PR 296 validation: durable per-module runner identity

## Scope and execution class

- Repository: `Bepoadewale/davdeploy`
- Commit validated: `9f14624` (`feat: bind runner callbacks to module instances`)
- Validation type: local clean-room integration; no AWS customer workload was run.
- AWS account and region: not applicable; no cloud credentials were used.

## Focused and full verification

Focused command:

```text
uv run pytest -q tests/test_db_config.py tests/test_invitation_email.py tests/test_cloud_execution.py
```

Result: 59 passed, with one existing Starlette deprecation warning.

Full verification:

```text
make verify
```

Result: 471 passed, with one existing Starlette deprecation warning. Ruff,
configuration validation, OpenAPI snapshot validation, and Docker Compose
configuration validation passed.

## Isolated clean-room cycle

The clean-room worktree was checked out at commit `9f14624` in
`/tmp/davdeploy-cleanroom-pr296-20261104`, with Compose project name
`davdeploy-pr296-20261104`.

Commands run:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make clean-local
```

All targets passed. The full suite reported 471 passed and one existing warning.
The project's containers, network and PostgreSQL volume were removed by
`make clean-local`; the isolated worktree's generated `.venv` and `.local` were
also removed. Test-created Docker images were retained. No AWS resources were
created, changed, or destroyed.

## Specific behavior covered

- The worker persists a submitted CodeBuild ID on the one exact module instance.
- Migration from schema version 24 adds the nullable unique build-ID index
  idempotently; duplicate build IDs are rejected.
- An EventBridge CodeBuild ARN resolves to its exact linked module row.
- Reconciling that callback leaves a different, undispatched module row
  unchanged.
- Legacy run-level reconciliation remains available for older rows without a
  per-module build ID.
- Multi-module CodeBuild requests remain rejected by the existing adapter.

## Limits

This validates persistence and callback targeting locally. It does not wire
dependency waves into hosted scheduling, support multiple concurrent module
builds, enable additional renderers, deploy the schema to Aurora, or prove a
hosted AWS lifecycle. GitHub CI is tracked separately on PR #296.
