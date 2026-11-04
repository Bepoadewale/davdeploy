# test302 — Typed DynamoDB-to-Lambda renderer binding

Date: 2026-11-04
Execution type: Local unit/contract tests, Terraform validation and fixture-backed clean-room cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: Pending implementation commit.
AWS account: Not applicable; this PR creates no AWS resources.
AWS region: Not applicable.

## Resources created

- No AWS resources.
- All configured Terraform roots were initialized and validated by `scripts/terraform-validate.sh`.
- Focused test run: 85 passed.
- `make verify`: 506 passed; OpenAPI and Compose config checks passed; one existing Starlette/httpx warning.

## Commands executed

- `bash -n scripts/customer-workload-serverless-api.sh` — passed.
- `.venv/bin/ruff check apps/api/src/davdeploy/cloud_execution.py tests/test_cloud_execution.py tests/test_serverless_renderer_contract.py` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api fmt -check` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api validate` — passed.
- `scripts/terraform-validate.sh` — all configured roots passed.
- `make verify` — 506 passed, with the warning noted above.
- Clean-room cycle, documentation conventions and PR CI: pending.

## Observed result

The Lambda/API runner accepts only the declared S3 bucket and DynamoDB table input references, and validates each against the deterministic account/project/region naming contract before making AWS calls. The Terraform configuration passes the table name to the Lambda environment and grants only item-level/query actions on the exact table ARN. The DynamoDB renderer and API renderer remain disabled for ordinary hosted customer execution.

## Teardown

No AWS workload was deployed. Local ephemeral resource cleanup will be recorded after the clean-room cycle.

## Final boundary

This PR adds typed composition wiring and scoped IAM configuration. It does not prove that an application artifact uses DynamoDB successfully, does not certify the hosted CodeBuild runner, and does not enable customer deployment. A real composed AWS test remains required.
