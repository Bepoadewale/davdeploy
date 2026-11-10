# test328 - fixed Nova plan-only Terraform runner

Date: 2026-11-10
Execution type: Local unit, API, infrastructure-contract, and Terraform validation; no customer workload
Repository: `Bepoadewale/davdeploy`
Customer repository: N/A; no customer repository or workload was used
PR source branch: `feat/nova-plan-only-runner-328`
Local validation worktree branch: `feat/nova-plan-only-runner-328-review`
PR: #328 (draft; based on `main` after prerequisite PR #326 merged)
Commit: `41a9b6a1bac32f701e0e9c8229d868e285ffd00d` (Nova retry identity and exact IAM policy follow-ups; documentation evidence is committed separately)
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Verify the disabled-by-default fixed CodeBuild plan runner, customer plan-role binding, immutable input handoff, authenticated completion, encrypted/versioned result and plan objects, buildArn-scoped S3 policy, recovery after transient result-read failures, review-ready artifact discovery, and the backend-free approval block. This verifies local behavior and IAM policy text only. It does not apply Terraform, contact a customer account, or simulate AWS IAM.

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

The focused feature suite passed 115 tests before the review fixes. After the fixes, the focused run/recovery and infrastructure tests passed 32 tests; Ruff passed. Terraform formatting and validation passed. The OpenAPI snapshot was updated for the reconciliation description. `make verify` passed 797 tests, Ruff, the GitHub Actions configuration boundary, the OpenAPI snapshot, and Compose configuration; all Terraform roots validated. One pre-existing Starlette/httpx deprecation warning was emitted. Documentation convention and diff checks are to be rerun at the final commit.

The recovery tests cover a worker exit after the exact build ID is durably recorded but before input copy, a lost response after the build-scoped input write, and a transient result-read failure followed by reconciliation; reconciliation binds exact object versions and does not start another build or duplicate the copy. Policy contract tests show the CodeBuild role cannot access the API-only request prefix and that exact BuildArn A input/result/plan paths do not match BuildArn B. The API's build-input read grant is limited to the exact build ARN. KMS policy tests confirm the plans bucket uses S3 Bucket Keys and the policies use its exact bucket ARN as encryption context while retaining buildArn-scoped S3 resources. A mocked STS trust test rejects connection A's ExternalId when it is presented to connection B's plan role. This is not an AWS IAM simulation or live trust verification.

The runner tests cover exact build input/version binding, wrong run/build/tenant, tampered input, denied policy, secret redaction, versioned KMS-encrypted output, malformed CodeBuild response shapes, and the absence of Terraform apply/destroy calls. No customer workload or AWS account was used.

## Resources created

No AWS resources, customer workloads, or persistent test services. Terraform initialization installed the locked AWS provider locally for validation only. Unit tests used temporary directories, mocked S3/STS/CodeBuild clients, and local SQLite fixtures.

## Teardown

No cloud teardown is needed. The isolated PR clean-room environment was cleaned with its unique Compose project; no persistent project services were left running.

## Clean-room evidence

The isolated clean-room cycle passed on 2026-11-09 in detached worktree `/private/tmp/davdeploy-pr328-cleanroom` at commit `6ef504f3f0cf79361af23ae3820602c80c06dce5`, using the unique Compose project `davdeploy-pr328-cleanroom`:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr328-cleanroom make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr328-cleanroom make clean-local
```

Fresh dependency installation and Docker image builds passed. Smoke reported API, worker, executor, Prometheus, Grafana, Tempo, and OPA ready. The API contract and customer-plan end-to-end passed, including governed destroy in the local fixture. Trace checks passed. Full verification passed 796 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration; one existing Starlette/httpx deprecation warning was reported. Final cleanup removed only the uniquely named clean-room containers, network, and PostgreSQL volume plus the new worktree's `.venv` and `.local`. A follow-up check confirmed no matching containers or volume and no remaining `.venv` or `.local`. The clean-room worktree is retained. No AWS resources or unrelated project data were accessed or removed.

## Earlier clean-room evidence — 2026-11-10

The earlier review worktree run passed 797 tests. It is superseded by the integrated proof below, which includes main's merged customer plan-role changes and 814 tests.

## Integrated clean-room evidence — 2026-11-10

After merging current `main` (including PR #326), the isolated worktree `/private/tmp/davdeploy-pr328-review` completed the fresh local validation sequence on the PR implementation and generated OpenAPI snapshot:

```text
make clean-local
make bootstrap-local
make smoke
make demo-simple
make demo-complex
make demo-day2
make demo-degraded
make demo-failure
make demo-readiness-failure
make trace-check
make verify
make terraform-validate
make clean-local
```

The simple, complex, Day-2, degraded, policy-failure, and readiness-failure demos passed. Smoke reported API, worker, executor, Prometheus, Grafana, Tempo, and OPA ready. The API contract, local customer-plan end-to-end, seed, and trace checks passed. `make verify` passed 814 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration. All 15 configured Terraform roots passed formatting and validation. One pre-existing Starlette/httpx deprecation warning was emitted. The final cleanup removed only the uniquely named Compose project containers, network, PostgreSQL volume, and this PR worktree's generated `.venv` and `.local`. No AWS calls, customer workloads, or unrelated resources were used.

## Retry identity and IAM review follow-up — 2026-11-10

The independent review found that retries use two distinct IDs: the durable plan request ID and a fresh CodeBuild attempt ID. It also asked for clearer proof that staged-input inspection can use an unversioned read. The worker now validates these IDs separately, and the API still binds the staged input's `control_plane_run_id` to the durable database row while the artifact is keyed to the attempt ID. The API IAM policy lists `s3:GetObject` and `s3:GetObjectVersion` together on the exact build-input key; no prefix listing permission was added.

Focused tests passed (61 tests), covering a distinct attempt/request pair, rejection of an invalid durable request ID before customer role assumption, mismatched result-attempt rejection, and exact IAM action/resource scope. Ruff passed. The complete isolated cycle was rerun:

```text
make clean-local
make bootstrap-local
make smoke
make demo-simple
make demo-complex
make demo-day2
make demo-degraded
make demo-failure
make demo-readiness-failure
make trace-check
make verify
make terraform-validate
make clean-local
```

All six local demos passed. Smoke, API contract, fixture end-to-end, seed, and trace checks passed. `make verify` passed 816 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration; all 15 configured Terraform roots passed formatting and validation. The only warning was the existing Starlette/httpx deprecation. Final cleanup removed only the unique PR Compose project and its generated `.venv` and `.local`. No AWS calls, customer workloads, or unrelated resources were used.

## Final boundary

The runner remains disabled by default. Its Terraform configuration uses `-backend=false`; results explicitly declare `INITIAL_PLAN_NO_REMOTE_STATE` and cannot be approved. Regional pricing remains unavailable, and the durable remote-state design is a separate blocker. No AWS call, customer resource mutation, Terraform apply/destroy, or merge of PR #328 is evidenced here. The CodeBuild role's STS permission uses a `davdeployPlan-*` name pattern; exact account/connection ARN binding in the runner, buildArn-only input visibility, and per-connection ExternalId trust keep the plan path identity-only. PR #326's customer plan role explicitly denies all customer service actions.

## Current-head review follow-up — 2026-11-10

The latest review identified two edge cases. The Terraform planner now hashes proposal JSON with the same canonical UTF-8 encoding used by the control plane, including non-ASCII text. If saved-plan object verification raises its typed storage error during successful-build reconciliation, the durable run now enters `RECONCILIATION_REQUIRED` instead of remaining `BUILD_STARTED`.

Focused tests passed: `tests/test_generated_terraform_plan.py` and `tests/test_nova_plan_runs.py` (47 tests); Ruff passed. Full `make verify` passed 818 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration. A clean Python 3.12 `make local-proof` also passed smoke, API contract, customer-plan fixture E2E, seed, trace checks, and all 818 tests. Cleanup removed only this PR's named Compose containers, network, PostgreSQL volume, `.venv`, and `.local`. The existing Starlette/httpx deprecation warning remains. CI run `42778557344` passed all seven jobs for commit `e8311a3`.

That review also found a missing-input recovery case: without `s3:ListBucket`, HeadObject can return 403 for an absent key. Recovery now proceeds to its exact-key conditional write instead of treating that response as proof of presence; if an object already exists and cannot be verified, the attempt still fails closed. The recovery regression test simulates an inaccessible HEAD and confirms the exact build input is staged without restarting CodeBuild. Focused tests passed (2), full `make verify` passed 818 tests, and a fresh Python 3.12 `make local-proof` passed smoke, API contract, fixture end-to-end, seed, trace checks, and all 818 tests. Scoped cleanup removed only this PR's named local artifacts. No AWS calls or resource mutations occurred. Current-head CI and review for this follow-up are pending.

## Canonical digest persistence follow-up — 2026-11-10

The independent review found one remaining legacy persistence path that hashed proposal JSON with Python's default ASCII escaping. `persist_generated_plan_artifact()` now uses `canonical_json_digest`, matching the planner and hosted result validation. The persistence success regression now uses an accented French rationale, so it proves the complete artifact-persistence path accepts the same proposal digest.

The Unicode planner and artifact-persistence regressions plus the conditional input-recovery case passed. Full `make verify` passed 818 tests; a fresh Python 3.12 `make local-proof` passed smoke, API contract, customer-plan fixture E2E, seed, trace checks, and all 818 tests. `make clean-local` removed only this PR's uniquely named containers, network, PostgreSQL volume, `.venv`, and `.local`. No AWS calls or mutations occurred. CI and review for this newest commit are pending.

## Secrets Manager retry follow-up — 2026-11-10

Current-head review identified that `BotoCoreError` and `ClientError` from the production Secrets Manager lookup could bypass the result-reconciliation handler. These AWS failures are now classified as retryable result-verification failures, so the request enters `RECONCILIATION_REQUIRED` and can be checked again after Secrets Manager recovers. Regression coverage exercises both a transport failure and a service error.

The focused secret-read reconciliation tests passed (2). Full `make verify` passed 820 tests; a fresh Python 3.12 `make local-proof` passed smoke, API contract, customer-plan fixture E2E, seed, trace checks, and all 820 tests. Final cleanup removed only this PR's named containers, network, PostgreSQL volume, `.venv`, and `.local`. No AWS calls or resource mutations occurred. CI and review for the latest changes are pending.
