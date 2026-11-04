# ticket325 - durable hosted Nova plan requests

PR: [#325](https://github.com/Bepoadewale/davdeploy/pull/325)
Branch: `feat/nova-plan-request-api`

## Problem / goal

Add a tenant-scoped, idempotent request boundary for a real Nova-generated Terraform plan. Generate the typed proposal from a current submitted revision, dispatch only through the separate plan-only CodeBuild project from PR #324, and keep final approval blocked until complete cost evidence exists. This PR must not add customer apply or destroy.

## Current repo state

- PR #322 is merged. Generated-plan manifests mark pricing `UNAVAILABLE`; approval fails closed until trusted regional evidence is integrated.
- `GeneratedTerraformPlanRunner` validates a typed proposal and produces an actual saved plan, but runs locally with `-backend=false` and `-lock=false`.
- At PR start, `GeneratedPlanArtifact` and `GeneratedPlanApproval` were immutable tenant-scoped records, but Nova requests had no durable worker queue.
- This PR now stores `QUEUED` requests and uses a tokenized, expiring worker lease before preparing input and starting a build.
- Every accepted idempotency key is durably bound to its request and run. Migration 29 backfills existing run keys and stores new keys and cross-key deduplication aliases in an organization-scoped binding table.
- A failed run can be retried explicitly up to three times with a fresh idempotency key. Every attempt gets a new durable runner ID and immutable input/result keys; replaying a retry key is idempotent, and runs with uncertain outcomes remain blocked for reconciliation.
- The expected proposal and canonical input digests are committed before S3 staging. A lost PutObject/version response is resolved with HeadObject against the exact attempt key; only matching run ID/digest metadata with a non-null version is accepted. A confirmed absence permits one more `IfNoneMatch="*"` write.
- Input-stage uncertainty has a specific reconciliation route. A matching stored version can resume the queued worker without regenerating; confirmed absence becomes a retryable failure; unavailable or mismatched inspection remains blocked until inspection succeeds or an operator explicitly abandons that pre-build attempt. Abandonment leaves the old key untouched and later retry uses a fresh key.
- The API role can `GetObject` only for `plans/nova-generated/requests/<run-id>/input.json`, which authorizes HeadObject metadata checks. It receives no `ListBucket`; therefore an absent key returned as 403 is treated as uncertain and resolved through explicit abandonment plus a fresh immutable retry key.
- Migration 30 backfills runner IDs and seeds a database-backed round-robin cursor. The worker honors `DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP` from 1 to 10 and remains fair across cold starts.
- PR #324 is adding a distinct, disabled-by-default `DAVDEPLOY_NOVA_PLAN_PROJECT`; do not use `customer_executor`.
- Protected untracked file `--only-show-errors` is not part of this PR and must remain untouched.

## Research / references used

- `apps/api/src/davdeploy/generated_terraform_plan.py`: fixed Terraform validate/plan/show runner.
- `apps/api/src/davdeploy/generated_plan_artifacts.py`: encrypted saved-plan storage and immutable manifest.
- `apps/api/src/davdeploy/models.py`: infrastructure revision, plan render, and generated artifact records.
- `apps/api/src/davdeploy/service.py`: submitted/approved revision checks, worker leases, SQS wake-ups, and CodeBuild reconciliation.
- `apps/api/src/davdeploy/lambda_worker.py`: hosted queue worker.
- PR #324: dedicated plan-only CodeBuild boundary and fixed run-ID input contract.
- AWS CodeBuild `StartBuild` and IAM condition-key documentation: https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html and https://docs.aws.amazon.com/codebuild/latest/userguide/action-context-keys.html.
- AWS S3 `HeadObject` permission behavior: https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html.

## Work planned for the PR

- Permit Nova contract generation from the latest integrity-checked `SUBMITTED` revision while preserving the existing approved-revision compatibility path.
- Add a durable plan-run model with organization-scoped idempotency, request digest, revision/render binding, bounded attempts, lease state, and unique CodeBuild build identity.
- Add a scoped API to enqueue and inspect plan requests. Reject stale or mismatched revisions, renders, targets, and idempotency-key reuse.
- Dispatch only through the feature-gated plan-only CodeBuild project using a server-generated per-attempt run ID; keep the route disabled if the project is not configured.
- Reconcile the exact CodeBuild project/build completion against the durable run. Do not interpret a successful CodeBuild status alone as a verified Terraform plan.
- Preserve the cost-unavailable gate and all tenant, role, target, ownership, policy, and immutable-manifest boundaries.

## Acceptance criteria

- [x] A current submitted revision can produce a Nova typed Terraform proposal without requiring a workspace architecture approval first.
- [x] Duplicate requests with the same organization/key and same request digest return the same run; key reuse with different content is rejected.
- [x] A different key accepted through request deduplication is persisted as an alias; reusing that alias for different content is rejected.
- [x] Confirmed failed runs can be retried explicitly with a fresh key and a new immutable input/result key; request-key replay does not retry, retry-key replay is idempotent, and uncertain runs cannot be retried.
- [x] Stale revisions, wrong project/connection/account, malformed digests, and unauthorized users are rejected.
- [x] The hosted plan request persists `QUEUED` work and wakes only the separate, feature-gated plan-only CodeBuild worker using a server-generated run identifier.
- [x] Worker drain order is fair across all four durable queue kinds through a shared database cursor, while respecting any configured job cap including 1.
- [x] Duplicate/concurrent worker wake-ups and CodeBuild callbacks cannot create duplicate runs or bind another tenant's result.
- [x] Failed, expired, or uncertain work remains visibly failed or requires reconciliation; no fake plan/artifact success is recorded.
- [x] Lost input-stage responses cannot trigger an unsafe overwrite or duplicate write; durable reconciliation resumes a matching object, confirms absence, or requires explicit attempt abandonment before a fresh-key retry.
- [x] Plan output remains unapprovable while complete regional pricing evidence is absent.
- [x] Focused and full local verification pass, with no AWS mutation.

## Acceptance status

All implementation and local validation criteria are met. The PR remains open for review and has not been merged.

## Tests / validation performed

- Initial `make verify` before correcting the migration assertions: 692 passed, 4 failed. All four failures were stale expectations of schema version 26 after PR #325 had advanced it to 27.
- `uv run --locked --extra dev pytest -q tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_lambda_worker.py tests/test_db_config.py tests/test_invitation_email.py` — 45 passed after the S3 input-stage reconciliation and scoped IAM update.
- `uv run --locked --extra dev pytest -q tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py` — 25 passed in the focused dispatcher/run subset after adding S3 input-stage reconciliation.
- `make verify PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14` — passed with 711 tests, Ruff, configuration/OpenAPI checks, and `docker compose config --quiet`.
- `make openapi-update PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14` updated the snapshot; the final `make verify` confirmed it matches.
- No AWS calls or customer resources were used.

## Evidence files produced

`docs/test/test325.md`

## Boundaries and limitations

No Terraform apply, destroy, customer resource mutation, or AWS deployment. A successful plan job is not proof of apply, health, update, recovery, or cleanup. The separate customer plan-only role and tenant-isolated remote state remain follow-up gates. PR #326 must use schema migration 31 after this PR's migration 30.

## Follow-up work

Integrate authenticated read-only customer plan-role assumption, trusted tenant-scoped remote state and locking, regional pricing evidence, exact saved-plan approval, and the separately authorized apply/observe/recover/destroy lifecycle.
