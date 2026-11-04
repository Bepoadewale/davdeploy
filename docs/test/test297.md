# test297 — Typed renderer output normalization and persistence

Date: 2026-11-04
Execution type: Local tests and clean-room integration; no AWS customer workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `0bb426f` (`feat: persist typed renderer outputs per module`)
AWS account: Not applicable; no cloud credentials were used.
AWS region: Not applicable; no cloud credentials were used.

## Resources created

- A detached validation worktree at `/tmp/davdeploy-cleanroom-pr297-20261104`.
- Docker Compose project `davdeploy-pr297-20261104`, including containers,
  a network, and a fresh PostgreSQL volume.
- A generated `.venv` and `.local` directory inside the isolated worktree.
- No AWS resources.

## Commands executed

```text
uv run pytest -q tests/test_module_ports.py tests/test_cloud_execution.py
make verify
git worktree add --detach /tmp/davdeploy-cleanroom-pr297-20261104 0bb426f
COMPOSE_PROJECT_NAME=davdeploy-pr297-20261104 make bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr297-20261104 make smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
COMPOSE_PROJECT_NAME=davdeploy-pr297-20261104 make clean-local
```

## Observed result

- Focused tests: 66 passed, one existing Starlette deprecation warning.
- Full `make verify`: 478 passed, one existing Starlette deprecation warning.
- The clean-room cycle passed bootstrap, readiness, API contract, customer-plan
  E2E, seed, simple/complex/Day-2/degraded demos, policy and readiness failures,
  trace check, lint, full tests, OpenAPI snapshot, and Compose config.
- Tests confirm Terraform `api_endpoint` maps to typed `api_url`, the Lambda ARN
  maps to `lambda_arn`, and malformed or sensitive outputs fail without storing
  the raw artifact or typed outputs.
- Callback results update only the matched module instance. Legacy run-level
  artifacts are preserved. Multi-module CodeBuild requests remain rejected.

## Teardown

`make clean-local` removed only the project-specific test containers, network,
and PostgreSQL volume, plus the generated `.venv` and `.local` in the isolated
worktree. Docker images were retained. No AWS resources were created, changed,
or destroyed.

## Final boundary

This evidence is local only. It does not show the schema or code deployed to
Aurora/Lambda, enable a renderer, dispatch dependency waves, or prove a composed
AWS customer workload.
