# test365 — local verification evidence

Date: 2026-11-12
Execution type: Isolated local Compose proof; no AWS execution
Customer repository: `Bepoadewale/davdeploy`
Commit: PR #365 implementation branch
AWS account: Not accessed
AWS region: Not accessed

## Change

The Nova proposal contract now rejects common literal credential and secret values across case and separator variants, including secret-like environment variable names nested in environment lists. Secret values in those fields must be typed `resource_reference` objects with `value_type: secret_reference`; boolean configuration controls such as `manage_master_user_password` remain allowed. Provider-schema sensitivity checks remain as a second guard. The plan runner and all hosted execution gates remain unchanged.

## Verification

- Focused contract tests after review correction: `uv run pytest tests/test_generated_deployment_contract.py -q` — 21 passed, including sensitive-value rejection, typed-reference acceptance, and boolean-control compatibility.
- Full checks after review correction: `make verify` — 1,007 tests passed, Ruff passed, OpenAPI snapshot matched, and Docker Compose configuration passed. One existing Starlette/httpx deprecation warning remains.
- Isolated Compose proof: `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365b make local-proof` — passed API readiness, worker/executor readiness, API/CORS contract, customer-plan local E2E, trace check, and the full verification suite.
- Repository checks: `git diff --check` and `python3 scripts/check_doc_conventions.py` — passed.
- Hosted CI run `43127441913` passed all seven required jobs on the earlier implementation head. The review correction is awaiting its final-head run.

## Observed result

Sensitive-looking proposal fields fail validation unless their value is a typed secret reference or a boolean configuration control. Existing ordinary values and graph references continue to validate. Full verification and isolated local proof pass after the review correction.

## Runtime boundary

The isolated local proofs used `davdeploy_nova_secret365` and `davdeploy_nova_secret365b`; they did not use AWS, Bedrock, or create customer infrastructure. Both projects' containers were stopped after proof. Their project-specific Docker networks and PostgreSQL volumes remain, preserving test data; no volume or unrelated resource was deleted. No Nova-generated AWS plan or apply was run.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- The isolated Compose projects created project-scoped containers, networks, and PostgreSQL volumes. Containers are stopped; networks and volumes remain. Nothing was deleted.

## Commands executed

- `uv run pytest tests/test_generated_deployment_contract.py -q`
- `make verify`
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof` (initial implementation)
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365b make local-proof` (review correction)
- `git diff --check`
- `python3 scripts/check_doc_conventions.py`

## Teardown

- Stopped containers for `davdeploy_nova_secret365` and `davdeploy_nova_secret365b` after local proof.
- Retained their project-scoped networks and PostgreSQL volumes; no deletion was requested or performed.

## Limitation

This proves contract-level rejection and typed-reference representation. It does not yet implement tenant-scoped secret resolution, customer runtime retrieval, or a hosted secret-backed application flow. Those remain required before the overall Nova goal can pass.

## Final boundary

This is local source and fixture evidence only. It does not show that a customer secret was resolved or that the Nova hosted workflow can apply, operate, recover, or destroy a workload.
