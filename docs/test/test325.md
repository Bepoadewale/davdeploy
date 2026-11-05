# test325 - durable hosted Nova plan requests

Date: 2026-11-05
Execution type: Local unit, API-code, and database-migration validation; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: Final migration-31 and reconciliation follow-up on `feat/nova-plan-request-api`; no customer workload was used
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Commands executed

```text
uv run --locked --extra dev pytest -q tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_db_config.py tests/test_invitation_email.py tests/test_nova_plan_artifact_infra.py tests/test_queue_and_model_gateway.py tests/test_terraform_generation.py
terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf
make openapi-update PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
make verify PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
uv run --locked python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

The earlier verification reported 692 passed and 4 failures because migration assertions still expected schema version 26; the assertions were updated. The final focused suite passed 99 tests, including lost Build response recovery by one exact match, using an already durable build ID, blocked zero/multiple/unavailable lookups, malformed Build environment responses, per-attempt token persistence, explicit generation-abandon confirmation and recovery, schema-phase migration, uncertain Bedrock transport outcomes, and confirmed 4xx/pre-call failures. The final `make verify` passed with 734 tests, Ruff, Actions configuration, OpenAPI snapshot validation, and Compose configuration. Terraform formatting, documentation conventions, and `git diff --check` passed. No AWS calls or customer resources were used.

## Resources created

No AWS resources. Unit tests use isolated in-memory SQLite databases and mocked S3/CodeBuild clients.

## Teardown

Not applicable; no cloud workload or persistent local service stack is in scope.

## Final boundary

The route is disabled unless `DAVDEPLOY_NOVA_PLAN_RUNNER_READY=true` and the exact project, artifact bucket, KMS key, and bucket owner are configured. The isolated CodeBuild project from PR #324 currently fails closed. Migration 29 backfills existing request-key bindings; migration 30 backfills runner IDs and seeds the durable worker cursor; migration 31 stores the preparation phase and unique per-attempt CodeBuild token. Migration 31 backfills `GENERATING_PROPOSAL` for active runs without an input digest, `STAGING_INPUT` for runs with digests but no immutable input version, and `STARTING_BUILD` for runs with an immutable input version but no build ID. AWS `StartBuild` receives that stable token, which CodeBuild treats as idempotent for five minutes. A lost response is reconciled only by scanning the exact project and matching the exact durable `DAVDEPLOY_NOVA_PLAN_RUN_ID` override through `ListBuildsForProject` and `BatchGetBuilds`. One exact match binds the build. Zero matches remain blocked for a later lookup; multiple matches, malformed response fields, unavailable APIs, and searches beyond the 10-page bound remain blocked. The API role receives those lookup actions only when Nova plan reviews are enabled, scoped to `davdeploy-nova-plan-only`; it cannot start a build through that statement.

Explicit retries require a fresh idempotency key, are limited to confirmed `FAILED` runs, and get a new runner ID, CodeBuild token, and distinct immutable input/result keys. Generation and input digests are committed before their side effects. The `reconcile-input` route can resume a verified staged input, mark confirmed absence retryable, or explicitly abandon a pre-build attempt so a fresh-key retry can proceed. If proposal generation lease expiry leaves the outcome uncertain, `reconcile-generation` requires an explicit abandon confirmation; the retry endpoint then creates a fresh attempt. The Lambda gets `s3:GetObject` only on request `input.json` keys and receives no `s3:ListBucket`; a missing key reported as 403 remains uncertain and requires explicit abandonment. Worker queue scheduling uses a durable cursor to rotate all queue kinds while respecting the configured job cap. Even if a build reports `SUCCEEDED`, this code records `BUILD_SUCCEEDED_UNVERIFIED` until a trusted result and saved-plan artifact verifier exists. This PR does not apply, destroy, or create customer AWS resources.

Bedrock transport timeouts and connection-level failures after `converse()` begins are treated as uncertain because the provider may have accepted the request before its response was lost. Those runs require explicit generation abandonment before retry. Failures before the provider call and responses with a known 4xx status remain confirmed failures. The fixture fallback is not called after an uncertain provider outcome.

The repository clean-room cycle remains pending because `make clean-local` would remove the existing `.venv`, `.local/davdeploy.db`, and Docker volume `davdeploy_davdeploy-postgres`. They were preserved pending approval.

## Known limitations

The customer-side plan-only role, its CodeBuild trust and broker permissions, the fixed runner result contract, verified saved-plan persistence, tenant-scoped remote state and lock, and regional pricing integration remain follow-up work. The current request record deliberately cannot be approved or used for deployment.
