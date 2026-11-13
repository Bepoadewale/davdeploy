# test399 — isolated local apply-state authorization groundwork

Date: 2026-11-13
Execution type: two isolated local Docker and fixture proofs only
Customer repository: `Bepoadewale/davdeploy`
Branch: `feat/nova-exact-plan-apply-399`
Commit: pending (working tree based on `fadaa5a`)
AWS account: none (no AWS execution)
AWS region: none (no AWS execution)

## Run boundary

The run exercised the local fixture application and schema/authentication tests.
It did not invoke AWS, Bedrock, Terraform plan/apply, or customer workload
resources. The apply-run state credential code is source-only and remains
behind disabled runtime gates; no apply request or CodeBuild apply run exists.

## Resources created and retained

The first proof used Compose project `davdeploy-pr399`; the second used a fresh
project and database, `davdeploy-pr399-status`. Each has a separate Postgres
volume, network, and project-specific API, worker, and fixture-executor images.
The first used ports 18080, 18090, 18181, 19090, 13200, and 13000. The second
used ports 18180, 18190, 18281, 19190, 13210, and 13100. The retained
overrides are `/tmp/davdeploy-pr399-isolated-compose.yml` and
`/tmp/davdeploy-pr399-status-compose.yml`. Their fixture state files are
`/tmp/davdeploy-pr399-customer-plan-e2e.json` and
`/tmp/davdeploy-pr399-status-customer-plan-e2e.json`. A dedicated
`.venv-pr399` was created and retained.

Only the containers in `davdeploy-pr399` and `davdeploy-pr399-status` were
stopped with `docker compose stop`. Their containers remain stopped. Both
projects' named volumes, networks, images, temporary Compose files, and fixture
state files, along with `.venv-pr399`, were retained. The pre-existing
`davdeploy` Compose stack and database were not restarted or modified.

## Commands executed

- `make local-proof VENV=.venv-pr399`, with the `davdeploy-pr399` Compose
  project, alternate ports, and temporary fixture state path: passed.
- Repeated `make local-proof VENV=.venv-pr399` with fresh project
  `davdeploy-pr399-status`, ports 18180/18190/18281/19190/13210/13100, and a
  separate fixture state path: passed.

## Observed result

- Fresh isolated image build and Compose configuration: passed.
- Smoke check: API, worker, fixture executor, Prometheus, Grafana, Tempo, and
  OPA reported ready.
- API contract: passed against `http://127.0.0.1:18080`.
- Customer-plan fixture flow: developer submission, administrator decision,
  self-approval, local dry-run, readiness failure, governed fixture destroy,
  and audit checks passed.
- Demo data seeding and Tempo trace check: passed against the isolated stack.
- `make verify`: 1,113 tests passed; Ruff, Actions configuration, OpenAPI, and
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- Latest focused apply-run status/access tests: `2 passed`; Ruff passed.
- Latest `make verify`: 1,115 tests passed; Ruff, Actions configuration,
  OpenAPI, and Compose checks passed. One existing Starlette/httpx deprecation
  warning. Documentation convention and `git diff --check` also passed.

The local proof uses the existing fixture executor. It is not evidence that a
customer AWS plan was applied, that application health was observed, or that
hosted update, recovery, teardown, or independent AWS absence checks work.

## Teardown

Stopped only the containers in Compose projects `davdeploy-pr399` and
`davdeploy-pr399-status`. Kept their volumes, networks, images, fixture state,
temporary overrides, and the virtual environment. No customer AWS resource
was created, changed, or deleted.

## Final boundary

This records local fixture evidence only. It does not claim hosted customer
apply, health, recovery, or teardown readiness.
