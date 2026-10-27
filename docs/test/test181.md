# test181 — Cognito delivery through Resend

Date: 2026-10-27
Execution type: focused local Lambda sender and static Terraform validation
Customer repository: none
Commit: pending PR merge
AWS account: not contacted by validation
AWS region: us-east-1 static configuration only

## Resources created

None.

## Commands executed

- `uv run pytest -q tests/test_cognito_resend_email_sender.py`
- `uv run ruff check apps/api/src/davdeploy/lambda_cognito_email_sender.py tests/test_cognito_resend_email_sender.py`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane init -backend=false`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate`

## Observed result

The focused sender tests passed (2 tests). Lint passed. Terraform formatting and static validation passed. No AWS API operation, email send, or deployment was performed by these checks.

## Teardown

No resources, workloads, credentials, or customer data were created or changed.

## Final boundary

Local/static validation only. A protected Terraform apply is required to create the KMS key and sender Lambda; a live Cognito sign-up/sign-in test is required afterward.
