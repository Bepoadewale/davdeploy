# test326 - customer Nova plan-only role migration

Date: 2026-11-05
Execution type: Local database migration and contract tests; no customer workload
Repository: `Bepoadewale/davdeploy`
Customer repository: N/A; no customer repository or workload was used
Branch: `feat/customer-nova-plan-role-326`, stacked on `feat/nova-plan-request-api` (PR #325)
Commit: Includes the final #325 base head `1c3f7b8`; PR #326 implementation commit pending
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Verify that PR #325's schema version 31 remains intact and PR #326 adds version 32 only for the separate customer plan-role columns. A fresh schema records version 32. An existing v31 database adds `plan_role_arn` and `plan_role_setup_state`, preserves existing connection data, and records v32 idempotently. A malformed v31 schema without `cloud_connections` fails closed without advancing its version.

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_db_config.py tests/test_invitation_email.py
uv run --locked --extra dev pytest -q tests/test_product.py tests/test_connection_experience.py tests/test_customer_aws_connection_contract.py tests/test_db_config.py tests/test_invitation_email.py tests/test_cloud_execution.py
make verify
GITHUB_PR_NUMBER=326 uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The database and invitation migration suite passed 15 tests. The broader focused feature suite passed 142 tests, and `make verify` passed 764 tests plus Ruff, Actions configuration, the OpenAPI snapshot, and Compose configuration. Documentation conventions and diff checks passed. A pre-existing Starlette/httpx deprecation warning remains. Coverage includes fresh schema version 32, migration history through v31, existing v31 to v32 with only plan-role columns added, preservation of discovery/execution connection values, idempotent rerun, and fail-closed behavior when a v31 database lacks `cloud_connections`.

## Resources created

No AWS resources or customer workloads. Tests use in-memory SQLite databases; no teardown is needed.

## Teardown

Not applicable; no cloud resources or persistent test services were created.

## Limits

This evidence proves the schema migration behavior only. It does not verify live customer role trust, installed AWS policies, CloudFormation onboarding, or any Nova plan execution.

## Final boundary

The v32 migration only records a separate plan-role ARN and setup state. Plan-only role setup remains plan-only, with no customer resource mutation and no AWS deployment validation from this test.
