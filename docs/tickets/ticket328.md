# ticket328 — fixed Nova plan-only Terraform runner

PR: [#328](https://github.com/Bepoadewale/davdeploy/pull/328) (draft)
Branch: `feat/nova-plan-only-runner-328`
Base: `main` (PR #326 merged as `49bd5dbed1fd578704f955c664ed19e8a4e159ef` on 2026-11-10; PR #328 was reopened and retargeted after GitHub closed it when the stacked base branch was deleted)

## Problem / goal

Replace the isolated Nova CodeBuild project's fail-closed stub with a fixed, checked-in plan runner. The runner accepts only the durable Nova run ID, verifies its immutable proposal/context/account/region and exact staged input, and executes the existing strict Terraform provider-schema, graph, policy, and saved-plan pipeline. It must persist an encrypted, versioned result envelope and exact saved-plan object version, then let an authenticated completion path verify the run, build, revision, tenant, account, and digests before persistence. The runner remains disabled by default. This PR adds no apply/destroy path and makes no pricing claim; approval stays blocked while regional pricing evidence is unavailable.

## Current repo state

- PR #324 provides a disabled-by-default `davdeploy-nova-plan-only` CodeBuild project with `NO_SOURCE`, `NO_ARTIFACTS`, and an inline buildspec that exits 78. Its API StartBuild grant is exact-project scoped and admits only the durable run-ID environment override. IAM can deny only override fields with supported condition keys; the fixed dispatcher source must not send other fields.
- PR #325 provides durable, idempotent `GeneratedPlanRun` records, per-attempt immutable S3 input/result keys, leases, a stable CodeBuild idempotency token, and exact-project build reconciliation. A successful build is currently `BUILD_SUCCEEDED_UNVERIFIED`; there is no trusted result persistence path.
- PR #326 adds a distinct `plan_role_arn` and customer-side plan-only role using the connection's ExternalId. Its template explicitly denies all customer service actions; AWS STS `GetCallerIdentity` remains usable even when explicitly denied. This PR must preserve ExternalId on role assumption and must not broaden the deployment executor.
- `GeneratedTerraformPlanRunner` performs exact Terraform/provider pin checks, provider schema validation, ownership tagging, policy evaluation, and saved-plan inspection, but currently runs with `-backend=false` and `-lock=false`.
- Nova plan approval remains blocked while complete regional pricing evidence is unavailable.

## State boundary decision and follow-up blocker

PR #328 is deliberately limited to an initial, backend-free plan. It must not read, write, or lock Terraform state, and its artifact must remain unapprovable and non-deployable even if regional pricing becomes available later. This avoids giving the shared CodeBuild service role access to every tenant's remote state. It is not a completion of the durable deployment-plan lifecycle.

Remote-state approaches reviewed for a later milestone:

1. **Per-customer state bucket and role.** Customer-account state could be isolated to a per-connection bucket/key and a separate role, but the current plan-only Quick Create intentionally installs a deny-all role. This requires a separately reviewed customer template, state encryption/versioning, ownership, recovery, and lifecycle contract.
2. **Per-tenant DavDeploy backend role.** A role for each tenant can grant access to one control-plane bucket key and S3 lock object. The current CodeBuild project has one shared service role and cannot receive a run-scoped IAM session policy through the allowed run-ID-only `StartBuild` override. The roles would need a separate, durable provisioning and teardown lifecycle before this is safe.
3. **DavDeploy-managed state service.** A control-plane service could broker exact tenant state versions and locks, but it would need Terraform-compatible state read/write, conditional version updates, crash recovery, and independent access controls. This is not an existing repository capability.

No option is implemented here. Do not add shared CodeBuild access to `davdeploy/customer/*`, do not use caller-controlled backend settings, and do not claim that backend-free plans represent refreshed or durable deployment state. Until a later state design is reviewed and implemented, approval, apply, and destroy remain blocked for these artifacts.

## Run-scoped object and role boundary

The API first writes immutable request input to its API-only `requests/{runId}/input.json` key. The CodeBuild role has no permission on that prefix. After `StartBuild` returns and the exact build identity is durably recorded, the API copies the verified request bytes into `builds/{BuildArn}/input.json`. The fixed build entrypoint bounded-polls that exact key. Its result and saved plan use the same BuildArn prefix. CodeBuild S3 resources interpolate the AWS-supported `codebuild:buildArn` policy variable, so a build with ARN A cannot read or write build B's input, result, or plan. There is no `ListBucket` grant.

The shared CodeBuild role's `sts:AssumeRole` resource is the name pattern `davdeployPlan-*`; IAM does not bind that permission to the current run's customer ARN. The fixed runner derives the expected ARN from the verified input account and connection ID. The CodeBuild role can read only its own build-scoped input, and the customer plan-role trust requires `StringEquals` on that connection's ExternalId. PR #326's plan role explicitly denies all customer service actions. A mocked trust test proves that a connection-A ExternalId is rejected by connection B's role; this is a static/unit contract check, not an AWS IAM simulation. Keep the runner disabled by default. If a future plan role receives customer service permissions, require a separately reviewed per-tenant broker boundary first.

The shared plans bucket enables S3 Bucket Keys. AWS therefore uses the exact bucket ARN as the KMS encryption context. Nova input, result, and saved-plan uploads explicitly enable the bucket key; KMS statements match the bucket ARN, while S3 object resources retain exact per-build paths.

## Research / references used

- `apps/api/src/davdeploy/generated_terraform_plan.py`: fixed CLI version, provider lockfile, schema, graph/policy, and saved-plan inspection pipeline.
- `apps/api/src/davdeploy/generated_plan_policy.py`, `generated_provider_validation.py`, `generated_plan_ownership.py`, and `generated_deployment_contract.py`: existing strict policy and schema pipeline.
- `apps/api/src/davdeploy/nova_plan_dispatch.py`, `service.py`, and `models.py`: run ID, immutable input, durable request, build binding, and current unverified completion state.
- `infrastructure/terraform/serverless-control-plane/main.tf`: isolated CodeBuild project, API grants, and service-role S3/KMS scope.
- `infrastructure/cloudformation/customer-discovery-role.yaml`: customer plan-role trust and permissions from PR #326.
- HashiCorp S3 backend documentation: `https://developer.hashicorp.com/terraform/language/backend/s3` (versioned state object and native `use_lockfile`; exact support must match the pinned Terraform CLI).
- AWS third-party role access documentation: `https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html` (the customer connection ExternalId must be preserved on cross-account AssumeRole).
- AWS S3 SSE-KMS documentation: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/specifying-kms-encryption.html` (S3 Bucket Keys use the bucket ARN as the KMS encryption context).
- AWS S3 object-level Bucket Key documentation: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/configuring-bucket-key-object.html` (a PUT can inherit or explicitly set the per-object Bucket Key behavior).
- AWS CodeBuild IAM context documentation: `https://docs.aws.amazon.com/codebuild/latest/userguide/permissions-conditionkeys-variables.html` and `https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html` (the supported `codebuild:buildArn` policy variable).
- AWS CodeBuild `StartBuild`, `BatchGetBuilds`, and S3 object-version APIs for bounded start, verification, and artifact identity.

## Work planned for the PR

- Replace only the project’s fail-closed buildspec with a fixed checked-in entrypoint whose sole customer input is `DAVDEPLOY_NOVA_PLAN_RUN_ID`; do not accept customer buildspec/source/role/image/command overrides.
- Pin and verify the Terraform CLI and AWS provider, including the checked-in lockfile and immutable code artifact. The dispatcher must not download or execute customer-provided code.
- Load the durable run and exact immutable build-scoped input by run ID; verify the project/build ARN/run ID, submitted revision, tenant, proposal/context/account/region, and canonical input digest. The API durably records the build before copying staged input into its BuildArn key; lease expiry or a lost copy response is handled by explicit build-input reconciliation without replaying StartBuild.
- Assume only the bound `plan_role_arn` with the exact connection ExternalId. Keep credentials out of backend config and all plan/result files. Backend bucket/key/region/lock settings must be server-injected.
- Keep the current intermediate slice backend-free and explicitly initial-plan-only. Do not add state-bucket or lock permissions to the shared CodeBuild role. Track one of the three state approaches above as a separate milestone; until then all generated artifacts stay unapprovable and non-deployable.
- Reuse the existing strict schema, graph, ownership, policy, and actual saved-plan pipeline. Do not add apply/destroy, pricing claims, or policy relaxations.
- Store the saved plan and canonical result envelope as encrypted, versioned S3 objects under the exact BuildArn prefix. The API binds exact object version IDs and digests to the durable run; all Nova uploads use S3 Bucket Keys to match the plans bucket's KMS context. Sensitive plan contents remain out of logs and API responses.
- Add a trusted completion path that obtains an authenticated event, fetches the exact CodeBuild build, verifies project/build/run/revision/organization/tenant/account and all proposal/input/result/saved-plan digests and versions, then persists the verified artifact through the existing tenant-scoped plan persistence path.
- Add strict negative tests for tampered input/result/plan, wrong tenant/run/build/revision/account, incorrect versions/digests, unsafe policy, redaction, timeout/duplicate completion, and absence of apply/destroy or resource-mutation calls.
- Bind the customer role ARN to the account and connection in immutable input, and retain the per-connection exact ExternalId trust check. Test cross-tenant object isolation and mocked trust mismatch; do not claim a live IAM simulation.

## Acceptance criteria

- [x] The fixed runner accepts only the durable run ID and a trusted persisted attempt; no customer source/buildspec/role/image/command override is accepted.
- [x] Exact Terraform CLI, AWS provider, lockfile, code artifact, and provider schema are verified before planning.
- [x] The cross-account customer plan role is assumed only with the exact ExternalId bound to the run's connection; credentials never appear in backend configuration, plan files, result envelopes, logs, or API output.
- [x] This PR uses no Terraform backend or state lock; the artifact explicitly records `INITIAL_PLAN_NO_REMOTE_STATE` and cannot be approved even if pricing evidence later becomes available. No `-lock=false` workaround is added for a configured backend.
- [x] The runner verifies immutable proposal, context, account, region, current revision, and staged input before invoking the existing strict schema/graph/policy/actual-plan pipeline.
- [x] A saved plan and result envelope are encrypted and versioned. Exact object VersionIds and digests are recorded against the run.
- [x] Authenticated completion verifies exact CodeBuild project/build, durable run, revision, tenant, account, input, result, and saved-plan identity before artifact persistence; duplicate or mismatched completion cannot persist.
- [x] Tampering, wrong tenant/run/build/revision/account/version, unsafe policy, or missing verification fails closed and redacts secrets and plan contents.
- [x] No apply, destroy, or customer resource mutation call is introduced. Pricing remains `UNAVAILABLE`; approval remains blocked both by unavailable regional pricing and the missing remote-state milestone.
- [x] Runner remains disabled by default; no broad AWS permissions or live AWS calls are added.
- [x] Focused/full validation and clean-room validation pass.
- [ ] Current-head PR CI and review pass for the Unicode digest and saved-plan reconciliation fixes.

## Acceptance status

Draft PR and ticket were created before implementation. The backend-free initial-plan slice is implemented, including buildArn-scoped input/result/plan paths, exact role/ExternalId request binding, explicit input-handoff recovery, distinct durable request and per-attempt IDs, exact API build-input reads, transient result-read reconciliation, canonical Unicode proposal digests, recovery from saved-plan verification errors, and returning the artifact ID only for a review-ready run. The integrated clean-room cycle passed 816 tests before these latest review fixes; the current-head `make verify` passed 818 tests. Current-head CI and review remain pending. The durable remote-state boundary remains a product milestone blocker and is not weakened by this PR. The runner remains disabled by default; artifacts from this slice are explicitly unapprovable and non-deployable. The shared AssumeRole policy is a role-name pattern; per-connection trust and build-scoped input bind the identity pair, and the plan role grants no customer service permissions.

## Tests / validation performed

- The integrated clean-room cycle passed on 2026-11-10 before review fixes: all six local demos, customer-plan fixture flow, 816-test `make verify`, and `make terraform-validate` across 15 roots. After the fixes, a fresh Python 3.12 `make local-proof` and current-head 818-test `make verify` passed; scoped cleanup is in `docs/test/test328.md`.
- Focused tests for runner recovery and connection contracts passed (61 tests); no customer workload or AWS account was used.
- Current-head review regressions passed: 47 focused plan/reconciliation tests and `make verify` with 818 tests; Ruff passed. No AWS calls or resource mutations occurred.

## Evidence files produced

- `docs/test/test328.md` records local tests and Terraform validation; no customer workload is planned.

## Boundaries

No AWS calls, Terraform apply/destroy, or customer resource mutations. PR #326 was merged as a prerequisite; PR #328 remains draft and unmerged. The feature stays disabled by default. Regional pricing, remote state, approval, and the separately authorized deployment lifecycle remain blocked or outside this intermediate PR. The mocked cross-tenant trust check does not replace deployed IAM verification.

## Follow-up work

Design and implement a separately reviewed per-tenant remote-state boundary before any generated plan can become approvable or deployable. Add a tenant-isolated role broker before the plan role receives customer service permissions. Enable the runner only after the required deployment and regional pricing milestones are complete.
