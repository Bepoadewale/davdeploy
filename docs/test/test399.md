# test399 — isolated local apply-state authorization groundwork

Date: 2026-11-13
Execution type: isolated local Docker and fixture execution only
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

The proof used a separate Compose project named `davdeploy-pr399`, with its own
Postgres volume, network, and project-specific API, worker, and fixture-executor
images. Ports were isolated at 18080, 18090, 18181, 19090, 13200, and 13000.
`/tmp/davdeploy-pr399-isolated-compose.yml` and the fixture state file
`/tmp/davdeploy-pr399-customer-plan-e2e.json` are retained. A dedicated
`.venv-pr399` was created and retained.

Only the `davdeploy-pr399` containers were stopped with `docker compose stop`.
Its containers remain stopped. Its named volume, network, images, temporary
Compose file, state file, and virtual environment were not deleted. The
pre-existing `davdeploy` Compose stack and database were not restarted or
modified.

## Commands executed

- `make local-proof VENV=.venv-pr399`, with the `davdeploy-pr399` Compose
  project, alternate ports, and temporary fixture state path: passed.

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
- A separate `make verify`, documentation convention check, and
  `git diff --check` also passed for the current working-tree implementation.

The local proof uses the existing fixture executor. It is not evidence that a
customer AWS plan was applied, that application health was observed, or that
hosted update, recovery, teardown, or independent AWS absence checks work.

## Teardown

Stopped only the containers in Compose project `davdeploy-pr399`. Kept its
volume, network, images, fixture state, temporary override, and virtual
environment. No customer AWS resource was created, changed, or deleted.

## Final boundary

This records local fixture evidence only. It does not claim hosted customer
apply, health, recovery, or teardown readiness.
