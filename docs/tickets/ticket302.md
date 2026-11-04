# PR #302 — Bind DynamoDB output into the Lambda API renderer

## Goal

Add a typed DynamoDB table-name binding to the checked-in Lambda/API renderer, with table-scoped permissions. Keep both renderers disabled for ordinary hosted customer execution until live composed lifecycle certification.

## Current repository state

PR #301 merged as `5b067b0`, adding the gated DynamoDB renderer. The typed port contract already declares `aws-nosql-data.table_name` and `aws-serverless-api.table_name`, but the API runner currently accepts only `uploads_bucket_name` and its Terraform has no DynamoDB input or IAM policy.

## Research and references

- `apps/api/src/davdeploy/module_ports.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `scripts/customer-workload-serverless-api.sh`
- `infrastructure/terraform/customer-workload-serverless-api/`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- AWS DynamoDB IAM actions should be restricted to the single bound table ARN; avoid `Scan` and wildcard resources.

## Work to be done

- Extend the API renderer input allowlist and validate the DynamoDB name against the account, project and region deterministic naming contract.
- Pass the table name to Terraform and the Lambda environment as `DYNAMODB_TABLE_NAME`.
- Add a least-privilege inline Lambda policy limited to that table for `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` and `Query`; do not grant `Scan`.
- Add focused contract tests for valid/mismatched table references, combined S3 and DynamoDB inputs, Terraform scope and IAM action boundaries.
- Reconcile PR #301 completion and current deployment boundaries in the product goal and readiness matrix.
- Keep the renderer gated; no AWS resource lifecycle is part of this PR.

## Acceptance criteria

- [ ] Only typed, deterministic same-project DynamoDB table names are accepted.
- [ ] The Lambda receives the validated table name and permissions are scoped to its exact ARN.
- [ ] Existing S3-to-Lambda binding behavior remains valid.
- [ ] Ordinary hosted execution remains disabled.
- [ ] Ticket and test evidence distinguish local/CI proof from AWS certification.
- [ ] Required focused validation and PR CI pass; clean-room cycle is completed because Terraform execution contracts change.

## Validation

Pending implementation.

## Evidence files

- `docs/test/test302.md` (to record validation; no AWS resources planned).

## Boundaries and follow-up

This PR will not enable customer execution or claim a live DynamoDB/Lambda composed deployment. A later controlled AWS certification must prove the same-project table binding, an actual API operation, health/output capture, destruction, and independent absence verification through the authorized execution path.
