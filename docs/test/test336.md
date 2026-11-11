# test336 — Nova state workflow input wiring

Date: 2026-11-11
Execution type: Focused and full local tests plus isolated clean-room verification
Customer repository: N/A; no customer repository or workload was used
Commit: `eddfc92` (final implementation and contract-test head; clean-room proof at `b20b73d`)
AWS account: N/A; no AWS commands were required for this implementation
AWS region: N/A; no AWS commands were required for this implementation

## Resources created

No AWS resources or customer resources were created. The isolated local proof
used a unique Compose project named
`davdeploy-pr336-cleanroom-20261111`.

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_nova_plan_only_infra.py tests/test_terraform_workflows.py
uv run --locked python scripts/check_actions_configuration.py
uv run --locked python scripts/check_doc_conventions.py
git diff --check
make verify
COMPOSE_PROJECT_NAME=davdeploy-pr336-cleanroom-20261111 make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr336-cleanroom-20261111 make clean-local
docker ps -a --filter name=davdeploy-pr336-cleanroom-20261111 --format '{{.Names}}'
docker volume ls --filter name=davdeploy-pr336-cleanroom-20261111 --format '{{.Name}}'
docker network ls --filter name=davdeploy-pr336-cleanroom-20261111 --format '{{.Name}}'
```

## Observed result

- Focused infrastructure/workflow tests: 16 passed.
- Actions configuration and documentation convention checks passed; the
  allowlist reports 29 public metadata names and 3 secret names.
- `make verify` passed with 866 tests, Ruff, OpenAPI drift, and Compose config.
- The isolated local proof passed bootstrap, API contract, customer-plan E2E,
  demos, trace checks, and the same full verification (866 tests).
- Clean-room cleanup removed only the named Compose containers, volume,
  network, and its generated `.venv`/`.local`; absence checks returned no
  matching resources. One existing Starlette/httpx deprecation warning was
  emitted by the test suite.
- No Terraform or AWS deployment was run. State storage/API, the plan runner,
  pricing approval, and customer execution remain disabled in the hosted
  environment.

## Teardown

The exact PR-specific local Compose resources and generated worktree-local
`.venv` and `.local` data were removed and their absence verified. No AWS
resources were created, so no cloud teardown was required.

## Final boundary

This PR only passes the existing state configuration inputs through the
protected Terraform plan workflow, with enable flags defaulting to false and
the API origin defaulting to empty. It does not provision or enable Nova state,
run a customer plan, approve a costed plan, apply infrastructure, or certify
health/recovery/teardown.
