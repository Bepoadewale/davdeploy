# test326 - customer Nova plan-role boundary and migration

Date: 2026-11-05
Execution type: Local database migration, API contract and Terraform policy validation; no customer workload
Repository: `Bepoadewale/davdeploy`
Customer repository: N/A; no customer repository or workload was used
Branch: `feat/customer-nova-plan-role-326`, stacked on `feat/nova-plan-request-api` (PR #325)
Commit: PR #326 source revision; see the pull request for the exact commit
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Verify that PR #325's schema version 31 remains intact and PR #326 adds version 32 only for the separate customer plan-role columns. A fresh schema records version 32. An existing v31 database adds `plan_role_arn` and `plan_role_setup_state`, preserves existing connection data, and records v32 idempotently. A malformed v31 schema without `cloud_connections` fails closed without advancing its version. Plan-role verification is disabled by default, and the list/detail API reports trust/account verification separately from unattested effective policy. Plan-only setup works when the runner is off, omitting its unused broker principal; when enabled, Terraform wires the CodeBuild role ARN.

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_db_config.py tests/test_invitation_email.py
uv run --locked --extra dev pytest -q tests/test_product.py tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py tests/test_nova_plan_only_infra.py tests/test_connection_experience.py tests/test_serverless_runtime.py
terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf infrastructure/terraform/serverless-control-plane/variables.tf
terraform init -backend=false -lockfile=readonly && terraform validate
make verify
GITHUB_PR_NUMBER=326 uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The focused plan-role, list response, migration and Terraform policy suite passed 123 tests. `terraform fmt` and `terraform validate` passed. `make verify` passed 772 tests plus Ruff, Actions configuration, the OpenAPI snapshot, and Compose configuration. Documentation conventions and diff checks passed. A pre-existing Starlette/httpx deprecation warning remains. No AWS calls were made. Coverage includes fresh schema v32, existing v31→v32 with only plan-role columns added, idempotence, malformed-schema failure, default-off plan verification, optional broker trust, and truthful `POLICY_UNATTESTED` list/detail output.

## Resources created

No AWS resources or customer workloads. Tests use in-memory SQLite databases; no teardown is needed.

## Teardown

Not applicable; no cloud resources or persistent test services were created.

## Limits

This evidence proves local migration, policy configuration and API response contracts only. It does not verify live customer role trust, installed AWS policies, CloudFormation onboarding, or any Nova plan execution.

## Final boundary

The v32 migration only records a separate plan-role ARN and setup state. `VERIFIED` proves role trust and account identity only; effective AWS permissions remain unattested. Plan-only role setup remains plan-only, with no customer resource mutation and no AWS deployment validation from this test.
