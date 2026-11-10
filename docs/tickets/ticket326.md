# ticket326 — Add a customer-side Nova plan-only role

PR: #326 (draft)
Branch: `feat/customer-nova-plan-role-326` (current evidence was prepared in a fresh checkout after PR #325 merged)

## Problem / goal

Add an explicit customer AWS role for Nova's hosted Terraform plan path. The role must be distinct from deployment execution access, use the existing per-connection ExternalId trust, and have no ability to mutate customer resources.

## Current repo state

- `customer-discovery-role.yaml` creates a read-only discovery role by default. Its optional `administrator-pilot` path creates an `AdministratorAccess` execution role.
- `CloudConnection` stores `discovery_role_arn` and `execution_role_arn`, but has no plan-role field.
- Connection verification assumes the discovery role and, when present, the execution role; it confirms account identity but does not evaluate effective role permissions.
- `GeneratedTerraformPlanRunner` is backend-free and has no apply/destroy method. Its current plan configuration uses only the trusted `aws_caller_identity` data source.
- The isolated Nova CodeBuild project and future plan-broker permissions are being handled separately. This PR must not change that infrastructure or grant AssumeRole to an existing executor.
- PR #325 (`feat/nova-plan-request-api`) is merged to `main` at `47d932e` and ends at schema v31. PR #326 adds only the v31→v32 plan-role migration. Fresh databases create current metadata and record v32 directly.

## Research / references used

- `infrastructure/cloudformation/customer-discovery-role.yaml`
- `apps/api/src/davdeploy/domain.py`, `main.py`, `service.py`, `models.py`, and `integrations.py`
- `apps/api/src/davdeploy/generated_terraform_plan.py` and `generated_deployment_contract.py`
- `infrastructure/terraform/serverless-control-plane/main.tf` broker policy boundaries
- PR #324 isolated Nova CodeBuild boundary; PR #325 durable Nova plan request API

## Work planned for the PR

- Add a separate `plan_role_arn` purpose to the connection model and schema migration v32 after PR #325's v31 migrations; keep it distinct from `execution_role_arn`.
- Add `plan-only` to Quick Create and the reviewed customer CloudFormation template, creating a role with a unique name, exact ExternalId trust, the API principal, and an optional isolated Nova plan broker principal only when the runner is enabled. The template attaches an expected deny policy; DavDeploy does not attest effective customer permissions.
- Gate API plan-role identity verification behind `enable_nova_plan_role_verification` (default false) and narrowly allow `sts:AssumeRole` only for the `davdeployPlan-*` role prefix with a non-empty ExternalId and a dedicated verification session name.
- Require a workspace administrator and a discovery-only connection before generating a plan-only setup URL. Preserve general verification of execution roles on legacy mixed-role connections.
- Distinguish an expected, unverified template policy from a trust/account-verified role whose installed policy is still unattested. Do not infer plan-only permissions for manually attached arbitrary role ARNs.
- Add focused tests and update customer connection/security documentation.
- Map the plan-role verification Terraform input through the protected `terraform-plan` GitHub Environment variable `NOVA_PLAN_ROLE_VERIFICATION_ENABLED`, defaulting to false when unset; do not enable it in the hosted environment in this PR.
- Do not modify the CodeBuild executor or PR #324 files.

## Acceptance criteria

- [x] The `plan-only` role ARN is stored and returned separately from `execution_role_arn`.
- [x] The plan-only template path creates no AdministratorAccess or other service Allow permissions, and includes an explicit service-action deny.
- [x] Discovery and plan roles both require the exact connection ExternalId; the plan role always trusts the configured API and adds the isolated Nova plan broker principal only when the runner is enabled.
- [x] Verification attempts the plan-role trust/account check and never reports a plan role verified from discovery-role success alone.
- [x] Plan-only setup rejects connections with execution-role access; general verification still checks execution roles on legacy mixed-role records.
- [x] Plan-only setup URL generation requires a workspace administrator, including for same-tenant developers.
- [x] Connection details distinguish an expected, unverified deny policy from verified role trust with policy contents still unattested.
- [x] Connection list and detail responses report `POLICY_UNATTESTED` when plan-role trust/account identity is verified; neither response claims effective permissions were verified.
- [x] Plan-only Quick Create works with the runner disabled and omits the `unused` optional principal from CloudFormation trust; when the runner is enabled, Terraform supplies its CodeBuild role ARN.
- [x] Plan-role identity verification is disabled by default in production configuration and can be enabled separately from the still-disabled runner; setup and verification fail closed when it is off.
- [x] Existing apply paths cannot use the plan role as execution access.
- [x] Schema migration v32 follows #325's v31 migration, and an existing v31 database adds only plan-role columns before advancing to v32.
- [x] Existing discovery and administrator-pilot contracts remain compatible.
- [x] Focused tests pass; no AWS resources are created or changed.
- [x] API verification AssumeRole is separately opt-in and limited to `davdeployPlan-*` roles, with ExternalId and session-name conditions; the existing executor policy is not broadened.

## Acceptance status

The plan-only authorization, opt-in identity verification and status-reporting safeguards are implemented. The PR targets `main`; its branch includes the merged plan-request path, and the v32 migration follows v31. Review feedback on Terraform's moved object address was fixed at `6bc9668` and the full local clean-room cycle plus all-root Terraform validation passed again; evidence is recorded in `docs/test/test326.md`. Current-head CI and review are pending. Verification proves role trust and account identity only; effective policy contents remain unattested and are reported as `POLICY_UNATTESTED`.

## Tests / validation performed

- `uv run --locked --extra dev pytest -q tests/test_product.py tests/test_connection_experience.py tests/test_customer_aws_connection_contract.py tests/test_db_config.py tests/test_invitation_email.py tests/test_cloud_execution.py` — 137 passed.
- `uv run --locked --extra dev ruff check apps/api/src tests scripts` — passed.
- `uv run --locked python scripts/export_openapi.py` — OpenAPI v1 snapshot matches.
- `uv run --locked python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- `uv run --locked --extra dev pytest -q tests/test_product.py` — 47 passed; one existing Starlette/httpx deprecation warning.
- `uv run --locked --extra dev pytest -q tests/test_product.py -k 'plan_only or plan_role or quick_create_setup'` — 8 passed, 39 deselected; one existing Starlette/httpx deprecation warning.
- `uv run --locked --extra dev pytest -q tests/test_db_config.py tests/test_invitation_email.py` — 15 passed after merging the final #325 v31 migration chain and adding the #326 v32 migration.
- `uv run --locked --extra dev pytest -q tests/test_product.py tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py tests/test_nova_plan_only_infra.py tests/test_connection_experience.py tests/test_serverless_runtime.py` — 123 passed; one existing Starlette/httpx deprecation warning.
- `terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf infrastructure/terraform/serverless-control-plane/variables.tf` — passed.
- `terraform init -backend=false -lockfile=readonly && terraform validate` in the serverless-control-plane root — passed; no AWS calls.
- `make verify` — passed: 772 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration; one existing Starlette/httpx deprecation warning.
- Fresh isolated full clean-room cycle after merging current `main` — passed: clean, bootstrap, smoke, API contract, simple/complex/degraded/Day-2/canonical demos, policy/readiness failure demos, customer-plan E2E, fixture seed, trace check, `make verify` (781 tests), and final clean. Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration passed.
- Final absence checks confirmed no `davdeploy-pr326-resume` containers, network, volume, `.venv`, or `.local` remained.
- After the reviewed Terraform object-address fix, the full isolated cycle was rerun at `6bc9668`; `make verify` again passed 781 tests, and `make terraform-validate` passed all configured roots.
- `GITHUB_PR_NUMBER=326 uv run --locked python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — rerun after final documentation updates.
- The required full `clean -> bootstrap -> demos -> verify -> clean` cycle passed on a fresh isolated worktree at `3be87a1`. The user authorized cleanup of PR-specific artifacts; cleanup removed only this run's named project resources and generated `.venv`/`.local`. No AWS calls, stacks, or customer resources were created.

## Evidence files produced

- `docs/test/test326.md` records local schema-migration and focused contract test evidence only. It is not a customer workload run and makes no AWS deployment claim.

## Boundaries

No AdministratorAccess on the plan role, no Terraform apply/destroy, no AWS infrastructure changes, no change to PR #324 files, and no new AssumeRole permission on an existing executor in this PR.

## Follow-up work

The fixed Nova runner remains a fail-closed stub. A follow-up must implement runner-side role assumption and validate the generated plan and saved-plan artifact before enabling customer plans. Effective customer role policy attestation also remains future work; this PR verifies trust and account identity only.
