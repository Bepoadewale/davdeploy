# ticket274 — Reconcile renderer-specific execution evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/274

Branch: `feat/serverless-run-records`

## Problem / goal

The CodeBuild completion reconciler currently validates only run ID and success status before accepting a result. It also maps every non-App-Runner operation to a generic `SUCCEEDED_AWAITING_OBSERVATION` state. That would lose the meaning of Lambda artifact, plan, health, destroy, and cleanup results when the hosted renderer is connected to durable service runs.

Add strict, renderer-aware result validation and terminal state mapping for the checked-in Lambda/API lifecycle. Keep customer run creation disabled. This PR makes persisted evidence trustworthy for the next service-integration step; it does not launch a customer deployment path.

## Current repo state

PR #273 is merged. The Lambda/API renderer and pinned artifact builder are packaged behind the hosted-certification gate. `ProductService.create_cloud_execution_run_for_revision` and its approval/confirmation flow remain App Runner-only. `reconcile_cloud_execution_build` currently accepts any successful JSON artifact matching only `run_id` and `status`, then maps non-App-Runner modes generically.

## Research / references used

- `apps/api/src/davdeploy/service.py`: `run_next_cloud_execution` and `reconcile_cloud_execution_build`
- `apps/api/src/davdeploy/models.py`: durable `CloudExecutionRun` record
- `scripts/customer-workload-serverless-api.sh`: operation result phases and details
- `scripts/customer-serverless-artifact-build.py`: artifact-build evidence schema
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- PRs #267–#273 and tickets #267–#273

## Work planned for the PR

- Validate CodeBuild results against the run's exact ID, approved digest, connection, and typed operation before recording success.
- Map each serverless renderer result to an explicit durable state and preserve its operation-specific evidence.
- Fail closed on missing, mismatched, or malformed phase/detail values; do not infer health from apply success.
- Add focused tests for all result phases, mismatches, and failure states.
- Leave API run creation App Runner-only and keep all serverless execution gates closed for customers.

## Acceptance criteria

- [x] Results are bound to the exact run, plan digest, connection, and requested operation.
- [x] Artifact-build, plan, apply, health, destroy, and cleanup have distinct truthful states.
- [x] Health is recorded only from an explicit successful health result matching the prior apply output; destroy only from confirmed absence.
- [x] Malformed or cross-run evidence cannot mark a run successful.
- [x] Focused tests and full local clean-room cycle pass.
- [x] CI passes.
- [x] No customer execution gate or API run-creation path is enabled.

## Acceptance status

Renderer-aware evidence validation and state mapping are implemented. Focused tests, full suite, isolated local clean-room validation, and all seven required GitHub Actions checks pass.

## Tests / validation performed

`make verify` passed: 378 tests, OpenAPI snapshot, configuration boundary, lint, and Docker Compose config; one existing Starlette/httpx deprecation warning. Focused cloud-execution tests passed: 30 tests. `GITHUB_PR_NUMBER=274 .venv/bin/python scripts/check_doc_conventions.py` and `git diff --check` passed.

The full clean-room cycle used a fresh detached worktree at final implementation commit `99af7a9` in `/tmp/davdeploy-cleanroom-pr274-final-20261103`. `make bootstrap-local` passed, followed by `make smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify`; every target passed. Compose services were stopped with `docker compose stop`; the worktree and named Postgres volume remain.

GitHub Actions run `41688249133` passed all seven checks: `cloud-contracts`, `docs-conventions`, `local-e2e`, `policy`, `python`, `secrets`, and `supply-chain` on implementation commit `99af7a9`. This ticket evidence update will cause CI to run again for the final PR revision.

## Evidence files produced

No AWS workload is planned for this PR. Hosted CodeBuild lifecycle certification remains a follow-up. Clean-room files remain under `/tmp/davdeploy-cleanroom-pr274-final-20261103`; services are stopped, not removed.

## Boundaries

Do not broaden IAM, change Terraform, enable serverless customer execution, create or destroy AWS customer resources, or treat an apply result as health evidence.

## Follow-up work

Implement a separate administrator-authorized serverless run creation/approval flow, project-scoped Terraform state, hosted CodeBuild plan/apply/health/destroy, and end-to-end disposable AWS certification. Enable customer execution only after that evidence and independent review.
