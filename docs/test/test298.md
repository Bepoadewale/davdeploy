# test298 — Durable dependency wave scheduling

Date: 2026-11-04
Execution type: Local tests and clean-room integration; no AWS customer workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `b2f8a27` (`feat: schedule durable module dependency waves`)
AWS account: Not applicable; no cloud credentials were used.
AWS region: Not applicable; no cloud credentials were used.

## Resources created

- No AWS resources or external customer resources.
- Detached worktree `/tmp/davdeploy-cleanroom-pr298-20261104`.
- Docker Compose project `davdeploy-pr298-20261104`, with project-scoped containers, network, and a fresh PostgreSQL volume.
- Generated `.venv` and `.local` directories inside the isolated worktree.

## Commands executed

```text
uv run ruff format apps/api/src/davdeploy/universal_execution.py apps/api/src/davdeploy/cloud_execution.py apps/api/src/davdeploy/service.py tests/test_universal_execution.py tests/test_cloud_execution.py tests/test_renderer_dispatcher.py
bash -n scripts/customer-workload-dispatcher.sh
uv run pytest -q tests/test_universal_execution.py tests/test_cloud_execution.py tests/test_renderer_dispatcher.py
make verify
GITHUB_PR_NUMBER=298 python3.12 scripts/check_doc_conventions.py
git diff --check
git worktree add --detach /tmp/davdeploy-cleanroom-pr298-20261104 b2f8a27
cd /tmp/davdeploy-cleanroom-pr298-20261104
COMPOSE_PROJECT_NAME=davdeploy-pr298-20261104 make clean-local
COMPOSE_PROJECT_NAME=davdeploy-pr298-20261104 make bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr298-20261104 make smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
COMPOSE_PROJECT_NAME=davdeploy-pr298-20261104 make clean-local
```

## Observed result

Focused lifecycle scheduling, CodeBuild selection, callback advancement,
fail-closed input binding, and renderer dispatch tests passed: 114 passed with
one existing Starlette deprecation warning. `make verify` passed: 485 tests with
the same warning. Ruff, shell syntax, OpenAPI snapshot, Compose configuration,
documentation conventions, and `git diff --check` passed. The clean-room cycle
on `b2f8a27` passed bootstrap, readiness, API contract, customer-plan E2E, seed,
all simple, complex, Day-2, degraded, failure and readiness-failure demos, trace
check, full verification, and cleanup. GitHub CI is pending.

## Teardown

The clean-room command removed only the `davdeploy-pr298-20261104` containers,
network, and PostgreSQL volume, plus `.venv` and `.local` in the isolated
worktree. Docker images were retained. No AWS resources were created.

## Final boundary

This evidence does not show a composed AWS customer workload. Typed reference
values are still not passed to Terraform, repeated renderer roots remain
blocked, and the hosted feature gate remains off.
