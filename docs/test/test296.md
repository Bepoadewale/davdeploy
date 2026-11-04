# test296 — Durable per-module runner identity

Date: 2026-11-04
Execution type: Local clean-room integration; no AWS customer workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `9f14624` (`feat: bind runner callbacks to module instances`)
AWS account: Not applicable; no cloud credentials were used.
AWS region: Not applicable; no cloud credentials were used.

## Resources created

- Isolated Docker Compose containers and network named for `davdeploy-pr296-20261104`.
- A fresh project-scoped PostgreSQL volume.
- Local `.venv` and `.local` in `/tmp/davdeploy-cleanroom-pr296-20261104`.
- No AWS resources.

## Commands executed

```text
uv run pytest -q tests/test_db_config.py tests/test_invitation_email.py tests/test_cloud_execution.py
make verify
git worktree add --detach /tmp/davdeploy-cleanroom-pr296-20261104 9f14624
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
COMPOSE_PROJECT_NAME=davdeploy-pr296-20261104 make clean-local
```

## Observed result

All targets passed. The full suite reported 471 passed and one existing warning.
The project's containers, network and PostgreSQL volume were removed by
`make clean-local`; the isolated worktree's generated `.venv` and `.local` were
also removed. Test-created Docker images were retained. No AWS resources were
created, changed, or destroyed.

- The worker persists a submitted CodeBuild ID on the one exact module instance.
- Migration from schema version 24 adds the nullable unique build-ID index
  idempotently; duplicate build IDs are rejected.
- An EventBridge CodeBuild ARN resolves to its exact linked module row.
- Reconciling that callback leaves a different, undispatched module row
  unchanged.
- Legacy run-level reconciliation remains available for older rows without a
  per-module build ID.
- Multi-module CodeBuild requests remain rejected by the existing adapter.

Focused tests: 59 passed. Full verification and clean-room verification: 471
passed, one existing Starlette deprecation warning. Ruff, configuration,
OpenAPI, Compose configuration, API contract, local customer-plan, demo,
readiness, policy-denial, and trace checks passed.

## Teardown

The project's containers, network, and PostgreSQL volume were removed by
`make clean-local`; generated `.venv` and `.local` were also removed. Test-created
Docker images were retained. No AWS resources were created, changed, or
destroyed.

## Final boundary

This validates persistence and callback targeting locally. It does not wire
dependency waves into hosted scheduling, support multiple concurrent module
builds, enable additional renderers, deploy the schema to Aurora, or prove a
hosted AWS lifecycle. GitHub CI is tracked separately on PR #296. No customer
repository workload or AWS deployment was attempted.
