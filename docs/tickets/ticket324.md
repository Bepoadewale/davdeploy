# ticket324 - isolate the Nova plan-only CodeBuild boundary

PR: [#324](https://github.com/Bepoadewale/davdeploy/pull/324)
Branch: `feat/nova-plan-only-codebuild`

## Problem / goal

Create a dedicated, disabled-by-default CodeBuild project and service role for future trusted Nova plan-only work. Keep its authority separate from `customer_executor`, limit its object access to request input/result artifacts, scope its logs and KMS context, and route completion events only for this exact project. The API project-name environment variable is `DAVDEPLOY_NOVA_PLAN_PROJECT`; it is empty while the project flag is disabled.

The project must fail closed until the trusted fixed runner is wired. The future API caller may pass only the server-owned run ID override `DAVDEPLOY_NOVA_PLAN_RUN_ID`; source, buildspec, service role, environment/compute, artifact, and other authority-changing StartBuild overrides must be denied.

## Current repo state

- `main` is at `6c599e6` after PR #322. Its generated-plan review path is stored under `plans/nova-generated/` and remains cost-gated.
- `aws_codebuild_project.customer_executor` has a separate customer execution role with privileged mode, customer state and lock access, connection-secret access, and customer-role assumption. None of those permissions belong in this project's service role.
- The API role currently starts and observes only the customer executor project. Nova saved-plan review storage uses the configured plan bucket and KMS key.
- The prepared branch and draft PR were created before implementation. No AWS resource call or Terraform apply is in scope.
- The protected untracked `--only-show-errors` file is present in the checkout and must remain untouched.

## Research / references used

- [AWS CodeBuild condition keys](https://docs.aws.amazon.com/codebuild/latest/userguide/action-context-keys.html): `codebuild:source.buildspec` detects buildspec override presence with the `Null` operator; CodeBuild supports per-variable environment override conditions.
- [AWS CodeBuild service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_codebuild.html): identifies the supported `StartBuild` project and override condition keys.
- [AWS CodeBuild StartBuild API](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html): documents source, service-role, environment, artifact and buildspec overrides.
- [S3 Bucket Keys and SSE-KMS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/specifying-kms-encryption.html): a Bucket Key uses the bucket ARN as KMS context; without one, S3 uses the object ARN.
- [Configuring a Bucket Key at object level](https://docs.aws.amazon.com/AmazonS3/latest/userguide/configuring-bucket-key-object.html): an individual upload can disable the bucket-level default.
- `infrastructure/terraform/serverless-control-plane/main.tf`: current API IAM policy, customer executor, runtime environment, worker queue and CodeBuild completion event route.
- `infrastructure/terraform/serverless-control-plane/variables.tf`, Terraform workflows, and existing Nova artifact infrastructure tests.

## Work planned for the PR

- Add an opt-in flag, default false; create the separate project, role, and retained log group only when enabled.
- Keep the project on `NO_SOURCE`, `NO_ARTIFACTS`, and non-privileged Linux compute with a checked-in buildspec that exits unsuccessfully until the trusted fixed runner is wired.
- Give the service role only scoped log writes, `GetObject` on `plans/nova-generated/requests/*/input.json`, `PutObject` on the matching `result.json` objects, and KMS decrypt/data-key access conditioned on regional S3 and those object ARN contexts.
- Give the API role conditional `StartBuild` and `BatchGetBuilds` access on this exact project only, plus request-input/result-output access for the exact object paths. Set `DAVDEPLOY_NOVA_PLAN_PROJECT` to the project name only when enabled.
- Deny command-changing `StartBuild` overrides with official CodeBuild condition keys. Permit the required `DAVDEPLOY_NOVA_PLAN_RUN_ID` environment variable name and no other override name. Require the name/value entries; the API remains responsible for supplying the trusted persisted run ID.
- Route CodeBuild completion events for this exact project to the existing worker queue.
- Add focused static contract tests and PR-numbered validation evidence. Do not call AWS or apply Terraform.

## Acceptance criteria

- [x] The opt-in flag defaults to false; project, role, permissions, and event route are absent while disabled; `DAVDEPLOY_NOVA_PLAN_PROJECT` is empty while disabled.
- [x] The isolated project is non-privileged, uses no source/artifact override, and fails closed until a fixed runner is wired.
- [x] Its role has only scoped log access, input `GetObject`, result `PutObject`, and object-context-scoped KMS access; no customer state/lock, customer connection secret, or customer-role assumption permissions.
- [x] API `StartBuild` and `BatchGetBuilds` grants are conditional and target only this project's ARN; newly added API input/result object actions use only their dedicated keys and the configured plan KMS key/context.
- [x] StartBuild source/buildspec/service-role/environment/compute/artifact/other authority-changing overrides are denied; the only accepted environment override name is the required run ID. The application must source its value from the trusted persisted run.
- [x] Completion events match only this CodeBuild project's exact name and terminal build statuses.
- [x] Focused tests, Terraform formatting/validation, repository checks, and documentation checks pass. All seven required GitHub checks pass in [run 41917758576](https://github.com/Bepoadewale/davdeploy/actions/runs/41917758576); the final evidence update also passed all seven in [run 41918524417](https://github.com/Bepoadewale/davdeploy/actions/runs/41918524417).
- [x] No AWS calls/apply, no merge, no pricing changes, no PR #323 changes, and no modification of the protected untracked file.

## Acceptance status

Infrastructure implementation and local validation are complete. All seven required GitHub checks passed on the implementation/evidence commits in [run 41917758576](https://github.com/Bepoadewale/davdeploy/actions/runs/41917758576) and [run 41918524417](https://github.com/Bepoadewale/davdeploy/actions/runs/41918524417). The PR remains a draft and unmerged.

## Tests / validation performed

See `docs/test/test324.md` for focused tests, full repository verification, Terraform validation, documentation checks, and the required GitHub check run.

## Evidence files produced

- `docs/test/test324.md` — local automated and Terraform validation evidence; no customer workload or AWS execution is planned.

## Boundaries

This PR only provisions a disabled-by-default, fail-closed infrastructure boundary. It does not wire the fixed runner, generate or execute a Terraform plan, enable plan review, or authorize apply/destroy. The KMS condition is prefix-specific only when request objects are uploaded with SSE-KMS and Bucket Keys explicitly disabled; the future trusted API/runner implementation must honor that contract. If S3 Bucket Keys are used, S3 supplies the bucket ARN as encryption context and the object-prefix KMS condition rejects the operation.

## Follow-up work

Wire a fixed, reviewed runner input/result contract that verifies the persisted run ID and immutable artifacts before producing a saved plan. Its API must set SSE-KMS with the configured key, disable S3 Bucket Keys for request objects, and pass only the trusted run ID environment override. Keep the project flag disabled until that implementation is reviewed and available.
