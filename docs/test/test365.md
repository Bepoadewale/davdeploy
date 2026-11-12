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
- Required full clean-room cycle: passed from detached worktree `/private/tmp/davdeploy-pr365-cleanroom-20261112` at code commit `a3a5d6d0e70e0dcaaf4c6fa85e3296a7d116cf0b`, using project `davdeploy-pr365-cleanroom`, tmpfs Postgres override `/private/tmp/davdeploy-pr365-cleanroom-compose.yml`, and external venv `/private/tmp/davdeploy-pr365-venv`.
- Repository checks: `git diff --check` and `python3 scripts/check_doc_conventions.py` — passed.
- Hosted CI runs `43127441913` and `43129916298` passed all seven jobs on earlier heads. Follow-up compatibility and clean-room evidence updates await final-head verification.

## Observed result

Sensitive-valued proposal fields fail validation unless their value is a typed secret reference. Boolean controls, declared Cognito policy/configuration blocks, and numeric token validity values remain representable. Full verification and isolated local proof pass after the review corrections.

## Runtime boundary

The isolated local proofs used `davdeploy_nova_secret365`, `davdeploy_nova_secret365b`, and `davdeploy_nova_secret365c`; they did not use AWS, Bedrock, or create customer infrastructure. Their containers were stopped after proof; project networks and volumes are retained. The required clean-room cycle then ran in a separate fresh worktree and tmpfs Postgres configuration. It created no named volume; final clean removed its containers, network, `.local`, and external venv. Absence checks confirmed those artifacts are gone. The clean-room worktree and override are retained. No Nova-generated AWS plan or apply was run.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- The three initial isolated Compose proofs created project-scoped containers, networks, and PostgreSQL volumes. Containers are stopped; networks and volumes remain. The later clean-room cycle used tmpfs and created no named volume; its containers and network were removed by the required final clean, and absence checks passed.

## Commands executed

- `uv run pytest tests/test_generated_deployment_contract.py -q`
- `make verify`
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof` (initial implementation)
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365b make local-proof` (boolean-control correction)
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365c make local-proof` (policy/lifetime correction)
- `COMPOSE_FILE=docker-compose.yml:/private/tmp/davdeploy-pr365-cleanroom-compose.yml COMPOSE_PROJECT_NAME=davdeploy-pr365-cleanroom make VENV=/private/tmp/davdeploy-pr365-venv clean-local` (initial clean)
- `COMPOSE_FILE=docker-compose.yml:/private/tmp/davdeploy-pr365-cleanroom-compose.yml COMPOSE_PROJECT_NAME=davdeploy-pr365-cleanroom make VENV=/private/tmp/davdeploy-pr365-venv bootstrap-local`
- `COMPOSE_FILE=docker-compose.yml:/private/tmp/davdeploy-pr365-cleanroom-compose.yml COMPOSE_PROJECT_NAME=davdeploy-pr365-cleanroom make VENV=/private/tmp/davdeploy-pr365-venv smoke api-contract customer-plan-e2e`
- `COMPOSE_FILE=docker-compose.yml:/private/tmp/davdeploy-pr365-cleanroom-compose.yml COMPOSE_PROJECT_NAME=davdeploy-pr365-cleanroom make VENV=/private/tmp/davdeploy-pr365-venv seed-demo-data demo-simple demo-complex demo-degraded demo-day2 demo-failure demo-readiness-failure trace-check verify`
- `COMPOSE_FILE=docker-compose.yml:/private/tmp/davdeploy-pr365-cleanroom-compose.yml COMPOSE_PROJECT_NAME=davdeploy-pr365-cleanroom make VENV=/private/tmp/davdeploy-pr365-venv clean-local` (final clean)
- Absence check: no matching project containers, network, volumes, `.venv`, `.local`, or external venv.
- `git diff --check`
- `python3 scripts/check_doc_conventions.py`

## Teardown

- Stopped containers for `davdeploy_nova_secret365`, `davdeploy_nova_secret365b`, and `davdeploy_nova_secret365c` after local proof.
- Retained their project-scoped networks and PostgreSQL volumes; no deletion was requested or performed.
- The full clean-room cycle ran its required final clean; scoped containers/network, `.local`, and external venv were confirmed absent. The detached worktree, Compose override, and build images remain.

## Limitation

This proves contract-level rejection and typed-reference representation. It does not yet implement tenant-scoped secret resolution, customer runtime retrieval, or a hosted secret-backed application flow. Those remain required before the overall Nova goal can pass.

## Final boundary

This is local source and fixture evidence only. It does not show that a customer secret was resolved or that the Nova hosted workflow can apply, operate, recover, or destroy a workload.
