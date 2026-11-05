# ticket328 — fixed Nova plan-only Terraform runner

PR: [#328](https://github.com/Bepoadewale/davdeploy/pull/328) (draft)
Branch: `feat/nova-plan-only-runner-328`
Base: PR #326, `feat/customer-nova-plan-role-326`

## Problem / goal

Replace the isolated Nova CodeBuild project's fail-closed stub with a fixed, checked-in plan runner. The runner accepts only the durable Nova run ID, verifies its immutable proposal/context/account/region and exact staged input, and executes the existing strict Terraform provider-schema, graph, policy, and saved-plan pipeline. It must persist an encrypted, versioned result envelope and exact saved-plan object version, then let an authenticated completion path verify the run, build, revision, tenant, account, and digests before persistence. The runner remains disabled by default. This PR adds no apply/destroy path and makes no pricing claim; approval stays blocked while regional pricing evidence is unavailable.

## Current repo state

- PR #324 provides a disabled-by-default `davdeploy-nova-plan-only` CodeBuild project with `NO_SOURCE`, `NO_ARTIFACTS`, and an inline buildspec that exits 78. Its API StartBuild grant is exact-project scoped and admits only the durable run-ID environment override. IAM can deny only override fields with supported condition keys; the fixed dispatcher source must not send other fields.
- PR #325 provides durable, idempotent `GeneratedPlanRun` records, per-attempt immutable S3 input/result keys, leases, a stable CodeBuild idempotency token, and exact-project build reconciliation. A successful build is currently `BUILD_SUCCEEDED_UNVERIFIED`; there is no trusted result persistence path.
- PR #326 adds a distinct `plan_role_arn` and customer-side plan-only role using the connection's ExternalId. Its template denies customer service actions except the identity check. This PR must preserve ExternalId on role assumption and must not broaden the deployment executor.
- `GeneratedTerraformPlanRunner` performs exact Terraform/provider pin checks, provider schema validation, ownership tagging, policy evaluation, and saved-plan inspection, but currently runs with `-backend=false` and `-lock=false`.
- Nova plan approval remains blocked while complete regional pricing evidence is unavailable.

## Research / references used

- `apps/api/src/davdeploy/generated_terraform_plan.py`: fixed CLI version, provider lockfile, schema, graph/policy, and saved-plan inspection pipeline.
- `apps/api/src/davdeploy/generated_plan_policy.py`, `generated_provider_validation.py`, `generated_plan_ownership.py`, and `generated_deployment_contract.py`: existing strict policy and schema pipeline.
- `apps/api/src/davdeploy/nova_plan_dispatch.py`, `service.py`, and `models.py`: run ID, immutable input, durable request, build binding, and current unverified completion state.
- `infrastructure/terraform/serverless-control-plane/main.tf`: isolated CodeBuild project, API grants, and service-role S3/KMS scope.
- `infrastructure/cloudformation/customer-discovery-role.yaml`: customer plan-role trust and permissions from PR #326.
- HashiCorp S3 backend documentation: `https://developer.hashicorp.com/terraform/language/backend/s3` (versioned state object and native `use_lockfile`; exact support must match the pinned Terraform CLI).
- AWS third-party role access documentation: `https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html` (the customer connection ExternalId must be preserved on cross-account AssumeRole).
- AWS CodeBuild `StartBuild`, `BatchGetBuilds`, and S3 object-version APIs for bounded start, verification, and artifact identity.

## Work planned for the PR

- Replace only the project’s fail-closed buildspec with a fixed checked-in entrypoint whose sole customer input is `DAVDEPLOY_NOVA_PLAN_RUN_ID`; do not accept customer buildspec/source/role/image/command overrides.
- Pin and verify the Terraform CLI and AWS provider, including the checked-in lockfile and immutable code artifact. The dispatcher must not download or execute customer-provided code.
- Load the durable run and exact immutable input by run ID; verify the run is `STARTING_BUILD`, the build project/run ID match, the submitted revision is current and integrity-checked, and the canonical proposal/context/account/region/input digests agree.
- Assume only the bound `plan_role_arn` with the exact connection ExternalId. Keep credentials out of backend config and all plan/result files. Backend bucket/key/region/lock settings must be server-injected.
- Decide and test an explicit remote-state/locking boundary. Prefer the versioned S3 backend with `use_lockfile` if supported by the pinned Terraform CLI, with an exact per-tenant key and least-privilege state/lock permissions. If the #326 plan-role deny policy, CodeBuild role, provider, or state trust cannot support a safe exact boundary, stop and document the blocker instead of weakening policy or using `-lock=false`.
- Reuse the existing strict schema, graph, ownership, policy, and actual saved-plan pipeline. Do not add apply/destroy, pricing claims, or policy relaxations.
- Store the saved plan and a canonical result envelope as encrypted, versioned S3 objects. Bind exact object version IDs and digests to the durable run; keep sensitive plan contents redacted from logs and API responses.
- Add a trusted completion path that obtains an authenticated event, fetches the exact CodeBuild build, verifies project/build/run/revision/organization/tenant/account and all proposal/input/result/saved-plan digests and versions, then persists the verified artifact through the existing tenant-scoped plan persistence path.
- Add strict negative tests for tampered input/result/plan, wrong tenant/run/build/revision/account, incorrect versions/digests, unsafe policy, redaction, timeout/duplicate completion, and absence of apply/destroy or resource-mutation calls.

## Acceptance criteria

- [ ] The fixed runner accepts only the durable run ID and a trusted persisted attempt; no customer source/buildspec/role/image/command override is accepted.
- [ ] Exact Terraform CLI, AWS provider, lockfile, code artifact, and provider schema are verified before planning.
- [ ] The cross-account customer plan role is assumed only with the exact ExternalId bound to the run's connection; credentials never appear in backend configuration, plan files, result envelopes, logs, or API output.
- [ ] The backend and lock boundary is explicit and least-privilege: server-injected exact per-tenant key, versioned state bucket, and supported native S3 lock object. No `-lock=false` fallback or caller-controlled backend settings.
- [ ] The runner verifies immutable proposal, context, account, region, current revision, and staged input before invoking the existing strict schema/graph/policy/actual-plan pipeline.
- [ ] A saved plan and result envelope are encrypted and versioned. Exact object VersionIds and digests are recorded against the run.
- [ ] Authenticated completion verifies exact CodeBuild project/build, durable run, revision, tenant, account, input, result, and saved-plan identity before artifact persistence; duplicate or mismatched completion cannot persist.
- [ ] Tampering, wrong tenant/run/build/revision/account/version, unsafe policy, or missing verification fails closed and redacts secrets and plan contents.
- [ ] No apply, destroy, or customer resource mutation call is introduced. Pricing remains `UNAVAILABLE` and approval remains blocked until regional pricing evidence exists.
- [ ] Runner remains disabled by default; no broad AWS permissions or live AWS calls are added.
- [ ] Focused/full validation and PR CI pass; clean-room status is recorded truthfully.

## Acceptance status

Draft PR and ticket created before implementation. No substantive code has been changed yet. Toolchain, S3 backend/lock, ExternalId, completion authentication, and exact permission boundaries are under review. The runner must remain disabled; if those trust boundaries cannot be made explicit, this PR will stop at a documented blocker.

## Tests / validation performed

- None yet. No customer workload or AWS account was used.
- The required clean-room cycle is not run yet. Cleanup targets and existing user artifacts will be preserved unless separately authorized.

## Evidence files

- `docs/test/test328.md` will record local tests and Terraform validation; no customer workload is planned.

## Boundaries and follow-up

No AWS calls, Terraform apply/destroy, customer resource mutations, broad IAM grants, PR merges, or artifact deletion. The feature stays disabled by default. Regional pricing, approval, and the separately authorized deployment lifecycle remain outside this PR.
