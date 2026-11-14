# test408 — revision-bound S3 usage assumptions

Date: 2026-11-14
Execution type: Local implementation, unit/integration tests, OpenAPI validation, and GitHub CI. No AWS execution.
Customer repository: `Bepoadewale/davdeploy`
Commit: implementation commit pending
AWS account: Not used
AWS region: Not used

## Resources created

No AWS resources or customer workload resources were created.

## Commands executed

- `uv run --locked --extra dev pytest -q tests/test_pricing_usage_assumptions.py tests/test_infrastructure_plan_lifecycle.py tests/test_generated_plan_pricing.py tests/test_generated_plan_artifacts.py tests/test_generated_plan_review.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_runs.py` — 222 passed, including final malformed/tampered usage cases.
- `make verify` — passed: action configuration check, Ruff lint, 1,193 tests, OpenAPI snapshot check, and `docker compose config --quiet` (one existing Starlette/httpx deprecation warning).
- `make openapi-update` — updated `contracts/openapi-v1.json`; the following `make verify` confirmed the snapshot matches the application.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- GitHub required CI and fresh-runner clean-room lifecycle — pending implementation commit.

## Observed result

The request contract accepts only bounded integer quantity ranges for monthly S3 Standard storage, writes, reads, and internet egress. User edits create immutable plan revisions; the trusted planner reconstructs assumptions from the digest-checked revision and carries them into pricing context, saved evidence, and review. Price evidence remains incomplete for S3 until all material cost dimensions have deterministic rates.

No AWS Price List query, plan apply, workload mutation, or customer lifecycle was performed.

## Teardown

No cloud resources were created, so no AWS teardown was needed. The isolated local worktree and Python environment are retained.

## Final boundary

PR #408 is draft, not deployed, and does not price S3 or make a customer plan approvable. EBS gp3 is the only resource with a price mapping. Database, asynchronous work, other material S3 dimensions, and unsupported usage remain approval blockers.
