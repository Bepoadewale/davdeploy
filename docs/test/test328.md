# test328 - fixed Nova plan-only Terraform runner

Date: 2026-11-09
Execution type: Local unit, API, infrastructure-contract, and Terraform validation; no customer workload
Repository: `Bepoadewale/davdeploy`
Customer repository: N/A; no customer repository or workload was used
Branch: `feat/nova-plan-only-runner-328`, stacked on PR #326
PR: #328 (draft; clean-room evidence added after implementation)
Commit: `6ef504f3f0cf79361af23ae3820602c80c06dce5` (implementation under test)
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Verify the disabled-by-default fixed CodeBuild plan runner, customer plan-role binding, immutable input handoff, authenticated completion, encrypted/versioned result and plan objects, buildArn-scoped S3 policy, and the backend-free approval block. This verifies local behavior and IAM policy text only. It does not apply Terraform, contact a customer account, or simulate AWS IAM.

## Commands executed

```text
uv run --extra dev python -m pytest -q tests/test_generated_plan_review.py tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_only_infra.py tests/test_nova_plan_artifact_infra.py tests/test_generated_terraform_plan.py --tb=short
uv run --extra dev python -m ruff check apps/api/src/davdeploy/generated_plan_artifacts.py apps/api/src/davdeploy/generated_terraform_plan.py apps/api/src/davdeploy/nova_plan_dispatch.py apps/api/src/davdeploy/nova_plan_codebuild.py apps/api/src/davdeploy/service.py tests/test_generated_plan_review.py tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_only_infra.py tests/test_nova_plan_artifact_infra.py tests/test_generated_terraform_plan.py
uv run --extra dev python -m compileall -q apps/api/src/davdeploy
terraform fmt -check -diff main.tf variables.tf
terraform init -backend=false -lockfile=readonly
terraform validate
make verify
GITHUB_PR_NUMBER=328 uv run --extra dev python scripts/check_doc_conventions.py
git diff --check
```

Terraform commands ran from `infrastructure/terraform/serverless-control-plane`. No Terraform plan, apply, or destroy was run.

## Observed result

The focused feature suite passed 115 tests. Ruff and compileall passed. Terraform initialization, `terraform fmt -check`, and `terraform validate` passed. `make verify` passed 796 tests, Ruff, the GitHub Actions configuration boundary, the OpenAPI snapshot, and Compose configuration. One pre-existing Starlette/httpx deprecation warning was emitted. Documentation convention and diff checks passed after the final ticket update.

The recovery tests cover a worker exit after the exact build ID is durably recorded but before input copy, and a lost response after the build-scoped input write; reconciliation binds the exact object version and does not start another build or duplicate the copy. Policy contract tests show the CodeBuild role cannot access the API-only request prefix and that exact BuildArn A input/result/plan paths do not match BuildArn B. KMS policy tests confirm the plans bucket uses S3 Bucket Keys and the policies use its exact bucket ARN as encryption context while retaining buildArn-scoped S3 resources. A mocked STS trust test rejects connection A's ExternalId when it is presented to connection B's plan role. This is not an AWS IAM simulation or live trust verification.

The runner tests cover exact build input/version binding, wrong run/build/tenant, tampered input, denied policy, secret redaction, versioned KMS-encrypted output, malformed CodeBuild response shapes, and the absence of Terraform apply/destroy calls. No customer workload or AWS account was used.

## Resources created

No AWS resources, customer workloads, or persistent test services. Terraform initialization installed the locked AWS provider locally for validation only. Unit tests used temporary directories, mocked S3/STS/CodeBuild clients, and local SQLite fixtures.

## Teardown

No cloud teardown is needed. No cleanup command was run.

## Clean-room evidence

The isolated clean-room cycle passed on 2026-11-09 in detached worktree `/private/tmp/davdeploy-pr328-cleanroom` at commit `6ef504f3f0cf79361af23ae3820602c80c06dce5`, using the unique Compose project `davdeploy-pr328-cleanroom`:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr328-cleanroom make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr328-cleanroom make clean-local
```

Fresh dependency installation and Docker image builds passed. Smoke reported API, worker, executor, Prometheus, Grafana, Tempo, and OPA ready. The API contract and customer-plan end-to-end passed, including governed destroy in the local fixture. Trace checks passed. Full verification passed 796 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration; one existing Starlette/httpx deprecation warning was reported. Final cleanup removed only the uniquely named clean-room containers, network, and PostgreSQL volume plus the new worktree's `.venv` and `.local`. A follow-up check confirmed no matching containers or volume and no remaining `.venv` or `.local`. The clean-room worktree is retained. No AWS resources or unrelated project data were accessed or removed.

## Final boundary

The runner remains disabled by default. Its Terraform configuration uses `-backend=false`; results explicitly declare `INITIAL_PLAN_NO_REMOTE_STATE` and cannot be approved. Regional pricing remains unavailable, and the durable remote-state design is a separate blocker. No AWS call, customer resource mutation, Terraform apply/destroy, or merge is evidenced here. The CodeBuild role's STS permission uses a `davdeployPlan-*` name pattern; exact account/connection ARN binding in the runner, buildArn-only input visibility, and per-connection ExternalId trust keep the plan path identity-only. PR #326's customer plan role explicitly denies all customer service actions.
