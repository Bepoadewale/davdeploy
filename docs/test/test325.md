# test325 - durable hosted Nova plan requests

Date: 2026-11-09
Execution type: Local unit, API-code, and database-migration validation; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: source review fixes are on the PR head; no customer workload was used.
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Commands executed

```text
terraform init -backend=false -lockfile=readonly
.venv/bin/python -m pytest tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_db_config.py tests/test_invitation_email.py tests/test_nova_plan_artifact_infra.py tests/test_nova_plan_only_infra.py tests/test_queue_and_model_gateway.py tests/test_terraform_generation.py -q
terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf infrastructure/terraform/serverless-control-plane/variables.tf
terraform validate
make openapi-update PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
make verify PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The earlier verification reported 692 passed and 4 failures because migration assertions still expected schema version 26; the assertions were updated. The final focused recovery, gateway, and stacked infrastructure suite passed 114 tests, including lost Build response recovery by one exact match, using an already durable build ID, blocked zero/multiple/unavailable lookups, malformed Build environment responses, per-attempt token persistence, explicit generation-abandon confirmation and recovery, schema-phase migration, uncertain Bedrock transport outcomes and HTTP 408, CodeBuild StartBuild timeout/408/5xx/malformed-status handling, confirmed rejections, and composed Terraform policy checks. The final `make verify` passed with 750 tests, Ruff, Actions configuration, OpenAPI snapshot validation, and Compose configuration. Terraform formatting, `terraform validate`, documentation conventions, and `git diff --check` passed. PR #325 is stacked on PR #324's `feat/nova-plan-only-codebuild` branch and targets that base. PR #324's auto-retry IAM update passed all seven checks in run 41946900232. The runner flag requires reviews to be enabled, so its restricted StartBuild grant is composed with request staging and reconciliation permissions. No AWS calls or customer resources were used.

## Resources created

No AWS resources. Unit tests use isolated in-memory SQLite databases and mocked S3/CodeBuild clients.

## Teardown

Not applicable; no cloud workload or persistent local service stack is in scope.

## Final boundary

The route is disabled unless `DAVDEPLOY_NOVA_PLAN_RUNNER_READY=true` and the exact project, artifact bucket, KMS key, and bucket owner are configured. The isolated CodeBuild project from PR #324 currently fails closed. Migration 29 backfills existing request-key bindings; migration 30 backfills runner IDs and seeds the durable worker cursor; migration 31 stores the preparation phase and unique per-attempt CodeBuild token. Migration 31 backfills `GENERATING_PROPOSAL` for active runs without an input digest, `STAGING_INPUT` for runs with digests but no immutable input version, and `STARTING_BUILD` for runs with an immutable input version but no build ID. AWS `StartBuild` receives that stable token, which CodeBuild treats as idempotent for five minutes. A lost response is reconciled only by scanning the exact project and matching the exact durable `DAVDEPLOY_NOVA_PLAN_RUN_ID` override through `ListBuildsForProject` and `BatchGetBuilds`. One exact match binds the build. Zero matches remain blocked for a later lookup; multiple matches, malformed response fields, unavailable APIs, and searches beyond the 10-page bound remain blocked. The API role receives those lookup actions only when Nova plan reviews are enabled, scoped to `davdeploy-nova-plan-only`; it cannot start a build through that statement.

Explicit retries require a fresh idempotency key, are limited to confirmed `FAILED` runs, and get a new runner ID, CodeBuild token, and distinct immutable input/result keys. Generation and input digests are committed before their side effects. The `reconcile-input` route can resume a verified staged input, mark confirmed absence retryable, or explicitly abandon a pre-build attempt so a fresh-key retry can proceed. If proposal generation lease expiry leaves the outcome uncertain, `reconcile-generation` requires an explicit abandon confirmation; the retry endpoint then creates a fresh attempt. The Lambda gets `s3:GetObject` only on request `input.json` keys and receives no `s3:ListBucket`; a missing key reported as 403 remains uncertain and requires explicit abandonment. Worker queue scheduling uses a durable cursor to rotate all queue kinds while respecting the configured job cap. Even if a build reports `SUCCEEDED`, this code records `BUILD_SUCCEEDED_UNVERIFIED` until a trusted result and saved-plan artifact verifier exists. This PR does not apply, destroy, or create customer AWS resources.

Bedrock transport timeouts and connection-level failures after `converse()` begins are treated as uncertain because the provider may have accepted the request before its response was lost. HTTP 408 `ModelTimeoutException` is also uncertain; it requires explicit generation abandonment before retry. Failures before the provider call and known 4xx rejections other than 408 remain confirmed failures. The fixture fallback is not called after an uncertain provider outcome. CodeBuild `StartBuild` HTTP 408, 5xx, timeout-coded, malformed-status, and transport failures remain blocked for exact build reconciliation; confirmed 4xx rejections without timeout semantics remain retryable.

PR #325 includes PR #324's isolated plan-only CodeBuild configuration through a normal branch merge. Its separate API policy grants `StartBuild` only on the exact project and only with the durable run-ID override. Explicit denies cover the other override fields for which CodeBuild provides IAM condition keys, including `codebuild:autoRetryLimit`. AWS exposes no IAM condition keys for some `StartBuild` fields, including timeout and debug-session options, so the IAM policy cannot forbid every API field. The fixed dispatcher sends only `projectName`, the idempotency token, and the single run-ID environment override; an abstract-syntax-tree contract test verifies that call shape. The Terraform variable validation requires reviews whenever the runner is enabled.

## Fresh isolated clean-room evidence

The required local cycle passed on 2026-11-09 at commit
`c8141ae` in detached worktree `/private/tmp/davdeploy-pr325-cleanroom` using
the unique Compose project `davdeploy-pr325-cleanroom`:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr325-cleanroom make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr325-cleanroom make clean-local
```

Fresh dependency installation and Docker image builds passed. Smoke, API contract,
customer-plan end-to-end, fixture seed, and trace check passed. Full verification passed
751 tests, Ruff, Actions configuration, the OpenAPI snapshot, and Compose configuration,
with one existing Starlette/httpx deprecation warning. Cleanup removed only this cycle's
uniquely named containers, network, PostgreSQL volume, and newly created worktree
`.venv`/`.local`; post-clean checks found none remaining. The worktree is retained.
The original `davdeploy-pr325` worktree and its previously existing local artifacts were
not changed. No AWS resources or customer workloads were used.

## Review follow-up validation

The review follow-up permits the authenticated `reconcile-build` action to retry
status lookup for a build ID already bound to the run after a transient CodeBuild
API failure. The event handler can then acknowledge that completion event without
leaving the run permanently unrecoverable. Terminal completion uses a conditional
database update bound to the exact project, build ID, and eligible run state, so
a late completion cannot overwrite a separately queued retry.

- `.venv/bin/pytest -q tests/test_nova_plan_runs.py tests/test_lambda_worker.py` — 29 passed, including transient status reconciliation, stale build completion fencing, and stale status-error fencing.
- `.venv/bin/ruff check apps/api/src/davdeploy/service.py tests/test_nova_plan_runs.py` — passed.
- `make verify` — 754 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration passed. One existing Starlette/httpx deprecation warning remains.

## First review-fix clean-room evidence

The required fresh local cycle passed on 2026-11-09 at commit
`7c05d80a71bf271640bd2d3d5b1da5ad1c01687e` in detached worktree
`/private/tmp/davdeploy-pr325-review-cleanroom`, using the unique Compose
project `davdeploy-pr325-review`:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr325-review make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr325-review docker compose stop
COMPOSE_PROJECT_NAME=davdeploy-pr325-review docker compose rm -f
```

Fresh Python 3.12 bootstrap and image builds passed. Smoke, API contract,
customer-plan E2E, fixture seed, trace check and full verification passed. The
fresh environment reported 690 tests passed, Ruff, Actions configuration,
OpenAPI snapshot and Compose configuration passed, with one existing
Starlette/httpx deprecation warning. Only the uniquely named disposable
containers were stopped and removed; absence was verified. The test-created
Compose volume `davdeploy-pr325-review_davdeploy-postgres`, network
`davdeploy-pr325-review_default`, and worktree `.venv`/`.local` remain because
they are non-container resources and were not deleted. Existing local worktrees,
volumes and data were not touched. No AWS calls or customer workloads occurred.

## Final reconciliation-fix clean-room evidence

After fencing both terminal completion and late status lookup errors, the
required fresh local cycle passed again on 2026-11-09 at commit
`80827d4565a1624a9d0ff090d226efd54167e569` in detached worktree
`/private/tmp/davdeploy-pr325-final-cleanroom`, using the unique Compose project
`davdeploy-pr325-final`:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr325-final make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr325-final docker compose stop
COMPOSE_PROJECT_NAME=davdeploy-pr325-final docker compose rm -f
```

Fresh Python 3.12 bootstrap and image builds passed. Smoke, API contract,
customer-plan E2E, fixture seed, trace check and full verification passed with
690 tests, Ruff, Actions configuration, OpenAPI snapshot and Compose checks.
The existing Starlette/httpx deprecation warning remains. Only the uniquely
named disposable containers were stopped and removed; absence was verified.
The test-created Compose volume `davdeploy-pr325-final_davdeploy-postgres`,
network `davdeploy-pr325-final_default`, and worktree `.venv`/`.local` remain
because they are non-container resources and were not deleted. No existing local
worktrees, volumes or data were touched. No AWS calls or customer workloads
occurred.

## Known limitations

The customer-side plan-only role, its CodeBuild trust and broker permissions, the fixed runner result contract, verified saved-plan persistence, tenant-scoped remote state and lock, and regional pricing integration remain follow-up work. The current request record deliberately cannot be approved or used for deployment.
