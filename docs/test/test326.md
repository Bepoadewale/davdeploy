# test326 - customer Nova plan-role boundary and migration

Date: 2026-11-10
Execution type: Local database migration, API contract and Terraform policy validation; no customer workload
Repository: `Bepoadewale/davdeploy`
Customer repository: N/A; no customer repository or workload was used
Branch: `feat/customer-nova-plan-role-326` (refreshed after PR #325 merged)
Commit: full-cycle proof after template-address fix at `6bc9668` (merged main `47d932e`); evidence updated at the final PR commit
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Verify that PR #325's schema version 31 remains intact and PR #326 adds version 32 only for the separate customer plan-role columns. A fresh schema records version 32. An existing v31 database adds `plan_role_arn` and `plan_role_setup_state`, preserves existing connection data, and records v32 idempotently. A malformed v31 schema without `cloud_connections` fails closed without advancing its version. Plan-role verification is disabled by default, and the list/detail API reports trust/account verification separately from unattested effective policy. The Terraform plan workflow maps `NOVA_PLAN_ROLE_VERIFICATION_ENABLED`, defaulting to false when unset; this PR does not enable it in hosted AWS. Plan-only setup works when the runner is off, omitting its unused broker principal; when enabled, Terraform wires the CodeBuild role ARN.

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_db_config.py tests/test_invitation_email.py
uv run --locked --extra dev pytest -q tests/test_product.py tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py tests/test_nova_plan_only_infra.py tests/test_connection_experience.py tests/test_serverless_runtime.py
terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf infrastructure/terraform/serverless-control-plane/variables.tf
terraform init -backend=false -lockfile=readonly && terraform validate
make verify
GITHUB_PR_NUMBER=326 uv run --locked python scripts/check_doc_conventions.py
git diff --check
uv run --locked --extra dev pytest -q tests/test_nova_plan_only_infra.py tests/test_terraform_workflows.py
uv run --locked python scripts/check_actions_configuration.py
GITHUB_PR_NUMBER=326 uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The focused plan-role, list response, migration and Terraform policy suite passed 123 tests. `terraform fmt` and `terraform validate` passed. `make verify` passed 772 tests plus Ruff, Actions configuration, the OpenAPI snapshot, and Compose configuration. Documentation conventions and diff checks passed. A pre-existing Starlette/httpx deprecation warning remains. No AWS calls were made. Coverage includes fresh schema v32, existing v31→v32 with only plan-role columns added, idempotence, malformed-schema failure, default-off plan verification, optional broker trust, and truthful `POLICY_UNATTESTED` list/detail output.

For the follow-up workflow wiring, the focused Nova/workflow tests passed (14 tests), the Actions configuration boundary classified 26 public metadata names and 3 secret names, the PR documentation convention check passed, and `git diff --check` passed. The workflow maps `NOVA_PLAN_ROLE_VERIFICATION_ENABLED` with a false fallback; the hosted variable was not enabled or changed.

After PR #325 merged, PR #326 was retargeted to `main` and current mainline was merged into the feature branch. The full isolated cycle passed at `3be87a1`: clean, Python 3.12 bootstrap, Compose smoke, API contract, simple/complex/degraded/Day-2 and canonical demos, policy and readiness failure demos, customer-plan E2E, fixture seed, trace check, `make verify` (781 tests), and final clean. Ruff, Actions configuration, OpenAPI snapshot, and Compose checks passed. The pre-existing Starlette/httpx deprecation warning remains. Final checks confirmed no project containers, volume, network, `.venv`, or `.local` remained. This is local fixture evidence; no AWS calls or customer resources were used.

The final review then found that the new public customer template object reused a Terraform address still present in a `moved` block. The active object was renamed to `current_customer_discovery_role`, preserving the prior address only as the migration source. The isolated full cycle was rerun on code commit `6bc9668`; all demos passed, `make verify` again passed 781 tests, and `make terraform-validate` passed every configured root including `connection-template-host`. Final cleanup and absence checks confirmed that only the uniquely named test stack and local files were removed. No AWS calls or template publication occurred.

## Resources created

No AWS resources or customer workloads. Both isolated full cycles created project-specific Compose containers, networks and PostgreSQL volumes, plus `.venv` and `.local` in `/private/tmp/davdeploy-pr326-resume`; each final cleanup removed those exact artifacts and absence was verified.

## Teardown

No cloud teardown was needed. Final project-scoped `make clean-local` removed the local test stack and artifacts; absence was verified.

```text
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make clean-local
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make smoke
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make api-contract
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make demo-simple demo-complex demo-degraded demo-day2 demo demo-failure demo-readiness-failure
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make customer-plan-e2e seed-demo-data
sleep 10 && COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make trace-check verify
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make terraform-validate
COMPOSE_PROJECT_NAME=davdeploy-pr326-resume make clean-local
```

## Limits

This evidence proves local migration, policy configuration and API response contracts only. It does not verify live customer role trust, installed AWS policies, CloudFormation onboarding, or any Nova plan execution.

## Final boundary

The v32 migration only records a separate plan-role ARN and setup state. `VERIFIED` proves role trust and account identity only; effective AWS permissions remain unattested. Plan-only role setup remains plan-only, with no customer resource mutation and no AWS deployment validation from this test.
