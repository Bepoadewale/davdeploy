# test365 — local verification evidence

Date: 2026-11-12
Execution type: Isolated local Compose proof; no AWS execution
Customer repository: `Bepoadewale/davdeploy`
Commit: PR #365 implementation branch
AWS account: Not accessed
AWS region: Not accessed

## Change

The Nova proposal contract now rejects common literal credential and secret fields across case and separator variants, including secret-like environment variable names nested in environment lists. These fields are accepted only as typed `resource_reference` objects with `value_type: secret_reference`. Provider-schema sensitivity checks remain as a second guard. The plan runner and all hosted execution gates remain unchanged.

## Verification

- Focused contract tests: `uv run pytest tests/test_generated_deployment_contract.py -q` — 18 passed.
- Full checks: `make verify` — 1,004 tests passed, Ruff passed, OpenAPI snapshot matched, and Docker Compose configuration passed. One existing Starlette/httpx deprecation warning remains.
- Isolated Compose proof: `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof` — passed API readiness, worker/executor readiness, API/CORS contract, customer-plan local E2E, trace check, and the full verification suite.
- Repository checks: `git diff --check` and `python3 scripts/check_doc_conventions.py` — passed.

## Observed result

Sensitive-looking proposal fields fail validation unless their value is a typed secret reference. Existing ordinary values and graph references continue to validate. Full verification and isolated local proof pass.

## Runtime boundary

The local proof used the unique Compose project `davdeploy_nova_secret365`; it did not use AWS, Bedrock, or create customer infrastructure. Its project containers were stopped after proof. The project-specific Docker network and PostgreSQL volume remain, preserving test data; no volume or unrelated resource was deleted. No Nova-generated AWS plan or apply was run.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- The isolated Compose project created project-scoped containers, a network, and a PostgreSQL volume. Containers are stopped; the network and volume remain. Nothing was deleted.

## Commands executed

- `uv run pytest tests/test_generated_deployment_contract.py -q`
- `make verify`
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof`
- `git diff --check`
- `python3 scripts/check_doc_conventions.py`

## Teardown

- Stopped containers for `davdeploy_nova_secret365` after local proof.
- Retained its project-scoped network and PostgreSQL volume; no deletion was requested or performed.

## Limitation

This proves contract-level rejection and typed-reference representation. It does not yet implement tenant-scoped secret resolution, customer runtime retrieval, or a hosted secret-backed application flow. Those remain required before the overall Nova goal can pass.

## Final boundary

This is local source and fixture evidence only. It does not show that a customer secret was resolved or that the Nova hosted workflow can apply, operate, recover, or destroy a workload.
