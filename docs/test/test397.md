# test397 — exact Nova execution workspace preservation

Date: 2026-11-13
Execution type: isolated local Docker and fixture execution only
Customer repository: `Bepoadewale/davdeploy`
Commit: `cb2bb2d889506884946fac6d2cc23d6da36f7c28`
AWS account: none (no AWS execution)
AWS region: none (no AWS execution)

## Run boundary

- Branch: `feat/nova-saved-plan-apply-records-397`
- No AWS API, Bedrock, Terraform plan/apply, or cloud workload was invoked.

## Resources created

The proof used Compose project `davdeploy-pr397`, a separate Postgres volume,
network, and dedicated DavDeploy images. Services used alternate host ports
18080, 18090, 18181, 19090, 13200, and 13000. A temporary Compose override at
`/tmp/davdeploy-pr397-isolated-compose.yml` set the project-specific network
and ports. The pre-existing `davdeploy` Compose project and database were not
restarted or modified.

After the proof, `docker compose stop` was run only for project
`davdeploy-pr397`. Its containers are stopped. The named Postgres volume,
Docker network, images, and temporary Compose file are retained; nothing was
deleted. The fixture state file `.local/customer-plan-e2e.json` was generated
by the local persistence test and remains present.

## Commands executed

- Built and started a new Compose project named `davdeploy-pr397` using the
  temporary port/network override. API base URL was `http://127.0.0.1:18080`.
- Ran the smoke script and API contract against that isolated API.
- Ran `customer_plan_e2e.py`, `seed_demo_data.py`, and `demo.py` in simple,
  complex, Day-2, degraded, policy-failure, and readiness-failure modes, with
  their API base URL redirected to the isolated API.
- Restarted only the isolated API and ran the customer-plan persistence check.
- Ran the Tempo trace check, `make verify`, focused PR suites, documentation
  conventions, Terraform formatting, and `git diff --check`.

## Observed result

- Fresh isolated image build and `docker compose config --quiet`: passed.
- Isolated smoke checks: API, worker, fixture executor, Prometheus, Grafana,
  Tempo, and OPA reported ready.
- API contract with base URL `http://127.0.0.1:18080`: passed.
- Local customer-plan fixture E2E: developer submission, administrator
  decision, self-approval, fixture dry-run, readiness failure, governed
  fixture destroy, and audit evidence passed.
- Seeded local demo records in the isolated database; no external writes.
- Simple, complex, Day-2, degraded, policy-failure, and readiness-failure
  fixture demos passed.
- Restarted only the isolated API container; customer-plan persistence check
  passed after restart.
- Tempo trace check: passed.
- `make verify`: 1,092 tests passed; Ruff, Actions configuration, OpenAPI, and
  Compose checks passed.
- Focused PR suites: 106 passed. Documentation convention, Terraform format,
  and `git diff --check` passed.

These checks exercise existing local fixtures and the new workspace archive
unit tests. They do not prove hosted Nova artifact persistence, customer
approval, Terraform apply, application health, recovery, teardown, or AWS
resource absence.

## Teardown

Stopped the containers with `docker compose stop` scoped to project
`davdeploy-pr397`. The named Postgres volume, network, images, and temporary
Compose file were retained. No Docker volume or network was removed.

## Final boundary

No customer AWS resources were created, modified, or deleted. This is local
fixture evidence only; it does not claim the hosted Nova customer deployment
workflow is ready.
