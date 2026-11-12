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

- Focused contract tests after review corrections: `uv run pytest tests/test_generated_deployment_contract.py -q` — 25 passed, including sensitive-value rejection, typed-reference acceptance, boolean-control compatibility, and policy/lifetime configuration.
- Full checks after review corrections: `make verify` — 1,011 tests passed; Ruff, OpenAPI snapshot, and Compose configuration passed. One existing Starlette/httpx deprecation warning remains.
- Isolated Compose proof after review corrections: `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365c make local-proof` — passed API/worker/executor readiness, API/CORS contract, customer-plan local E2E, traces, and full verification.
- Repository checks: `git diff --check` and `python3 scripts/check_doc_conventions.py` — passed.
- Hosted CI run `43127441913` passed all seven required jobs on the earlier implementation head. Follow-up compatibility corrections are awaiting final-head verification.

## Observed result

Sensitive-valued proposal fields fail validation unless their value is a typed secret reference. Boolean controls, declared Cognito policy/configuration blocks, and numeric token validity values remain representable. Full verification and isolated local proof pass after the review corrections.

## Runtime boundary

The isolated local proofs used `davdeploy_nova_secret365`, `davdeploy_nova_secret365b`, and `davdeploy_nova_secret365c`; they did not use AWS, Bedrock, or create customer infrastructure. All three projects' containers were stopped after proof. Their project-specific Docker networks and PostgreSQL volumes remain, preserving test data; no volume or unrelated resource was deleted. No Nova-generated AWS plan or apply was run.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- The isolated Compose projects created project-scoped containers, networks, and PostgreSQL volumes. Containers are stopped; networks and volumes remain. Nothing was deleted.

## Commands executed

- `uv run pytest tests/test_generated_deployment_contract.py -q`
- `make verify`
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof` (initial implementation)
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365b make local-proof` (boolean-control correction)
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365c make local-proof` (policy/lifetime correction)
- `git diff --check`
- `python3 scripts/check_doc_conventions.py`

## Teardown

- Stopped containers for `davdeploy_nova_secret365`, `davdeploy_nova_secret365b`, and `davdeploy_nova_secret365c` after local proof.
- Retained their project-scoped networks and PostgreSQL volumes; no deletion was requested or performed.

## Limitation

This proves contract-level rejection and typed-reference representation. It does not yet implement tenant-scoped secret resolution, customer runtime retrieval, or a hosted secret-backed application flow. Those remain required before the overall Nova goal can pass.

## Final boundary

This is local source and fixture evidence only. It does not show that a customer secret was resolved or that the Nova hosted workflow can apply, operate, recover, or destroy a workload.
