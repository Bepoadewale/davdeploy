# ticket325 - durable hosted Nova plan requests

PR: [#325](https://github.com/Bepoadewale/davdeploy/pull/325)
Branch: `feat/nova-plan-request-api`

## Problem / goal

Add a tenant-scoped, idempotent request boundary for a real Nova-generated Terraform plan. Generate the typed proposal from a current submitted revision, dispatch only through the separate plan-only CodeBuild project from PR #324, and keep final approval blocked until complete cost evidence exists. This PR must not add customer apply or destroy.

## Current repo state

- PR #322 is merged. Generated-plan manifests mark pricing `UNAVAILABLE`; approval fails closed until trusted regional evidence is integrated.
- PR #325's branch is stacked on PR #324's `feat/nova-plan-only-codebuild` branch through a normal merge. The runner flag is rejected unless Nova plan reviews are also enabled, so its exact input inspection and build lookup permissions are present whenever the runner is configured.
- `GeneratedTerraformPlanRunner` validates a typed proposal and produces an actual saved plan, but runs locally with `-backend=false` and `-lock=false`.
- At PR start, `GeneratedPlanArtifact` and `GeneratedPlanApproval` were immutable tenant-scoped records, but Nova requests had no durable worker queue.
- This PR now stores `QUEUED` requests and uses a tokenized, expiring worker lease before preparing input and starting a build.
- Every accepted idempotency key is durably bound to its request and run. Migration 29 backfills existing run keys and stores new keys and cross-key deduplication aliases in an organization-scoped binding table.
- A failed run can be retried explicitly up to three times with a fresh idempotency key. Every attempt gets a new durable runner ID and immutable input/result keys; replaying a retry key is idempotent, and runs with uncertain outcomes remain blocked for reconciliation.
- The expected proposal and canonical input digests are committed before S3 staging. A lost PutObject/version response is resolved with HeadObject against the exact attempt key; only matching run ID/digest metadata with a non-null version is accepted. A confirmed absence permits one more `IfNoneMatch="*"` write.
- Input-stage uncertainty has a specific reconciliation route. A matching stored version can resume the queued worker without regenerating; confirmed absence becomes a retryable failure; unavailable or mismatched inspection remains blocked until inspection succeeds or an operator explicitly abandons that pre-build attempt. Abandonment leaves the old key untouched and later retry uses a fresh key.
- The API role can `GetObject` only for `plans/nova-generated/requests/<run-id>/input.json`, which authorizes HeadObject metadata checks. It receives no `ListBucket`; therefore an absent key returned as 403 is treated as uncertain and resolved through explicit abandonment plus a fresh immutable retry key.
- Migration 30 backfills runner IDs and seeds a database-backed round-robin cursor. The worker honors `DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP` from 1 to 10 and remains fair across cold starts.
- Migration 31 records the durable preparation phase and a unique per-attempt CodeBuild idempotency token. It backfills `GENERATING_PROPOSAL` when no input digest exists, `STAGING_INPUT` when digests exist without an immutable input version, and `STARTING_BUILD` when an input version exists but no build ID is bound. The token is the immutable runner UUID and is passed to `StartBuild`; AWS treats a repeated token as idempotent for five minutes.
- Before each external call, the worker commits its phase. Expiry during generation, input staging, or `StartBuild` becomes a distinct reconciliation state. In particular, a lost `StartBuild` response cannot return the run to the queue.
- An uncertain proposal-generation call stays blocked until the requester explicitly abandons it; only then can they retry with a fresh idempotency key. This avoids automatic replay while preserving a recovery path when cross-key deduplication would otherwise return the same blocked run.
- Bedrock transport exceptions from the actual provider call and HTTP 408 `ModelTimeoutException` are marked outcome-uncertain and flow through generation failure records to the same explicit abandon action. Pre-call validation/policy failures and known provider 4xx rejections other than 408 remain confirmed failures and can use the existing fresh-key retry path.
- CodeBuild `StartBuild` transport errors, timeout error codes, HTTP 408/5xx, and missing or malformed HTTP status metadata are outcome-uncertain and remain in `BUILD_START_RECONCILIATION_REQUIRED`. Only a unique exact run-ID match in the dedicated project can bind a lost response; a known rejected 4xx without timeout semantics stays retryable.
- `reconcile-build` searches only the configured Nova plan project, batch-fetches listed builds, and matches the exact `DAVDEPLOY_NOVA_PLAN_RUN_ID` override. Only one exact match is bound. Zero matches, multiple matches, API errors, or an incomplete bounded search leave the run blocked; the route never starts a build.
- PR #324 contributes the distinct, disabled-by-default `DAVDEPLOY_NOVA_PLAN_PROJECT`; do not use `customer_executor`. Its separate API policy grants `StartBuild` only on that project with the durable run-ID override and denies the other override fields that have CodeBuild IAM condition keys, including `codebuild:autoRetryLimit`. CodeBuild has no IAM condition keys for some `StartBuild` options, including timeout and debug-session options, so IAM cannot reject every optional API field. The fixed dispatcher sends only the project name, idempotency token, and one run-ID environment override; a static source contract test checks that exact call shape. The review policy adds only exact-project lookup and request-object permissions, with no `StartBuild` grant.
- Protected untracked file `--only-show-errors` is not part of this PR and must remain untouched.

## Research / references used

- `apps/api/src/davdeploy/generated_terraform_plan.py`: fixed Terraform validate/plan/show runner.
- `apps/api/src/davdeploy/generated_plan_artifacts.py`: encrypted saved-plan storage and immutable manifest.
- `apps/api/src/davdeploy/models.py`: infrastructure revision, plan render, and generated artifact records.
- `apps/api/src/davdeploy/service.py`: submitted/approved revision checks, worker leases, SQS wake-ups, and CodeBuild reconciliation.
- `apps/api/src/davdeploy/lambda_worker.py`: hosted queue worker.
- PR #324: dedicated plan-only CodeBuild boundary and fixed run-ID input contract.
- AWS CodeBuild `StartBuild` and IAM condition-key documentation: https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html and https://docs.aws.amazon.com/codebuild/latest/userguide/action-context-keys.html.
- AWS CodeBuild recovery lookup APIs: https://docs.aws.amazon.com/codebuild/latest/APIReference/API_ListBuildsForProject.html and https://docs.aws.amazon.com/codebuild/latest/APIReference/API_BatchGetBuilds.html.
- AWS CodeBuild `StartBuild` request fields and supported IAM condition keys: https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html and https://docs.aws.amazon.com/service-authorization/latest/reference/list_codebuild.html.
- AWS Bedrock Converse error status codes, including `ModelTimeoutException` HTTP 408: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html.
- AWS S3 `HeadObject` permission behavior: https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html.

## Work planned for the PR

- Permit Nova contract generation from the latest integrity-checked `SUBMITTED` revision while preserving the existing approved-revision compatibility path.
- Add a durable plan-run model with organization-scoped idempotency, request digest, revision/render binding, bounded attempts, lease state, and unique CodeBuild build identity.
- Add a scoped API to enqueue and inspect plan requests. Reject stale or mismatched revisions, renders, targets, and idempotency-key reuse.
- Dispatch only through the feature-gated plan-only CodeBuild project using a server-generated per-attempt run ID; keep the route disabled if the project is not configured.
- Reconcile the exact CodeBuild project/build completion against the durable run. Do not interpret a successful CodeBuild status alone as a verified Terraform plan.
- Persist a stable per-attempt `StartBuild` idempotency token and provide a fail-closed, exact-project lookup path when the start response is lost.
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
- [x] Lost CodeBuild start responses are protected by a durable per-attempt token and can be reconciled only by one exact runner-ID match in the dedicated CodeBuild project. Zero, multiple, incomplete, or unavailable results remain blocked without retry.
- [x] Transient status-lookup failures for an already-bound build remain manually reconcilable, and a stale completion cannot overwrite a newer retry attempt.
- [x] An uncertain generation lease can be explicitly abandoned and retried with a fresh key; no generation attempt is automatically replayed.
- [x] Bedrock response loss/transport timeout is not treated as a confirmed generation failure; definite pre-call or known 4xx rejection other than HTTP 408 remains retryable.
- [x] Bedrock HTTP 408 and ambiguous CodeBuild `StartBuild` failures cannot be retried until explicit reconciliation or abandonment; known rejected requests remain retryable.
- [x] The Nova plan-only runner cannot be enabled without Nova plan reviews; the static contract test verifies the composed API environment, exact-project lookup grants, and separate constrained `StartBuild` policy.
- [x] CodeBuild IAM blocks supported override condition keys, including auto retry; a static source test proves the fixed dispatcher passes no timeout, debug, or other override arguments.
- [x] Plan output remains unapprovable while complete regional pricing evidence is absent.
- [x] Focused and full local verification pass, with no AWS mutation.

## Acceptance status

The original focused validation (114 tests), full verification (750 tests), Terraform formatting, `terraform validate`, and isolated clean-room cycle at `c8141ae` passed. After review follow-up, the focused Nova-run/worker suite passed 28 tests, Ruff passed, and `make verify` passed with 753 tests plus Actions configuration, OpenAPI, and Compose checks. A fresh isolated clean-room cycle for the review fix is in progress. Bedrock HTTP 408 and transport timeouts, plus ambiguous CodeBuild `StartBuild` errors, require explicit reconciliation or abandonment; known pre-call failures and confirmed provider/CodeBuild rejections without timeout semantics remain retryable. Current-head CI and review must pass before merge.

## Tests / validation performed

- `.venv/bin/python -m pytest tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_db_config.py tests/test_invitation_email.py tests/test_nova_plan_artifact_infra.py tests/test_nova_plan_only_infra.py tests/test_queue_and_model_gateway.py tests/test_terraform_generation.py -q` — 114 passed, covering phase migration, explicit generation-abandon confirmation, exact build recovery, CodeBuild StartBuild 408/5xx/malformed-status classification, timeout-coded 4xx classification, uncertain Bedrock transport/408 outcomes, and composed IAM/dispatcher contracts.
- `make verify PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14` — passed with 750 tests, Ruff, Actions configuration, OpenAPI snapshot, and `docker compose config --quiet`.
- `make openapi-update PY=/Users/adewale/Projects/davdeploy-pr325/.venv/bin/python PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14` updated both reconciliation routes; `make verify` confirmed the snapshot matches.
- `terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf infrastructure/terraform/serverless-control-plane/variables.tf`, `terraform validate`, `uv run --locked --extra dev python scripts/check_doc_conventions.py`, and `git diff --check` passed. Terraform initialization used `-backend=false -lockfile=readonly`.
- The earlier initial verification reported 692 passed and 4 failures due to stale schema-version expectations; those assertions are now updated and the final full suite passes with 750 tests.
- No AWS calls or customer resources were used. The isolated clean-room cycle passed on 2026-11-09 at `c8141ae`; exact commands and cleanup evidence are recorded in `docs/test/test325.md`.

## Evidence files produced

`docs/test/test325.md`

## Boundaries and limitations

No Terraform apply, destroy, customer resource mutation, or AWS deployment. A successful plan job is not proof of apply, health, update, recovery, or cleanup. The separate customer plan-only role and tenant-isolated remote state remain follow-up gates. PR #326 must use schema migration 32 after this PR's migration 31.

The original worktree's `/Users/adewale/Projects/davdeploy-pr325/.venv`, `.local/davdeploy.db`, and Docker volume `davdeploy_davdeploy-postgres` remain preserved. Clean-room validation used a separate new worktree and a uniquely named Compose project, then cleaned only those test-created resources.

## Follow-up work

Integrate authenticated read-only customer plan-role assumption, trusted tenant-scoped remote state and locking, regional pricing evidence, exact saved-plan approval, and the separately authorized apply/observe/recover/destroy lifecycle.
