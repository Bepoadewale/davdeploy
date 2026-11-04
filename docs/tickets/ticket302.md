# ticket302 — Bind DynamoDB output into the Lambda API renderer

PR: #302 (draft)
Branch: `feat/dynamodb-lambda-binding`

## Problem / goal

Add a typed DynamoDB table-name binding to the checked-in Lambda/API renderer, with table-scoped permissions. Keep both renderers disabled for ordinary hosted customer execution until live composed lifecycle certification.

## Current repo state

PR #301 merged as `5b067b0`, adding the gated DynamoDB renderer. The typed port contract already declares `aws-nosql-data.table_name` and `aws-serverless-api.table_name`, but the API runner currently accepts only `uploads_bucket_name` and its Terraform has no DynamoDB input or IAM policy.

## Research / references used

- `apps/api/src/davdeploy/module_ports.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `scripts/customer-workload-serverless-api.sh`
- `infrastructure/terraform/customer-workload-serverless-api/`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- AWS DynamoDB IAM actions should be restricted to the single bound table ARN; avoid `Scan` and wildcard resources.

## Work planned for the PR

- Extend the API renderer input allowlist and validate the DynamoDB name against the account, project and region deterministic naming contract.
- Pass the table name to Terraform and the Lambda environment as `DYNAMODB_TABLE_NAME`.
- Add a least-privilege inline Lambda policy limited to that table for `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` and `Query`; do not grant `Scan`.
- Add focused contract tests for valid/mismatched table references, combined S3 and DynamoDB inputs, Terraform scope and IAM action boundaries.
- Reconcile PR #301 completion and current deployment boundaries in the product goal and readiness matrix.
- Keep the renderer gated; no AWS resource lifecycle is part of this PR.

## Acceptance criteria

- [x] Only typed, deterministic same-project DynamoDB table names are accepted.
- [x] The Lambda receives the validated table name and permissions are scoped to its exact ARN.
- [x] Existing S3-to-Lambda binding behavior remains valid.
- [x] Ordinary hosted execution remains disabled.
- [x] Ticket and test evidence distinguish local/CI proof from AWS certification.
- [x] Required focused validation and PR CI pass; clean-room cycle is completed because Terraform execution contracts change.

## Acceptance status

- Implementation commit: `18d33e9`.

- `.venv/bin/pytest tests/test_serverless_renderer_contract.py tests/test_cloud_execution.py tests/test_module_ports.py -q` — 85 passed.
- `make verify` — 506 passed; OpenAPI snapshot and Compose configuration passed; one existing Starlette/httpx deprecation warning.
- `scripts/terraform-validate.sh` — passed for all configured roots.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api validate` — passed; `terraform fmt -check` passed.
- Ruff and shell syntax checks passed.
- Clean-room cycle at `18d33e9` — bootstrap, smoke, API contract, customer-plan E2E, seed, simple/complex/Day-2/degraded/failure/readiness-failure demos, trace check and `make verify` passed; 506 tests passed.
- Clean-room teardown removed only its project containers and network; no project containers or named volumes remain.
- `GITHUB_PR_NUMBER=302 .venv/bin/python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- PR CI run `41779922484` — all seven required checks passed on the preceding committed revision; the final evidence update is revalidated by current PR checks.

## Tests / validation performed

Exact commands and results are recorded in `docs/test/test302.md`.

## Evidence files produced

- `docs/test/test302.md` (to record validation; no AWS resources planned).

## Boundaries

This PR will not enable customer execution or claim a live DynamoDB/Lambda composed deployment. A later controlled AWS certification must prove the same-project table binding, an actual API operation, health/output capture, destruction, and independent absence verification through the authorized execution path.

## Follow-up work

- Deploy the compatible executor package only through the reviewed release workflow.
- Perform real composed AWS certification through the authorized runner before enabling this renderer.
