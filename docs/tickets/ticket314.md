# ticket314 Store generated plans and bind immutable review approval

PR: #314 https://github.com/Bepoadewale/davdeploy/pull/314 (merged 2026-11-04)
Branch: feat/nova-saved-plan-approval

Merge commit: `8cf1db2250a6a07481ad4184a81419b8ac52490a`.

## Problem / goal

PR #311 creates a local-only Terraform saved plan and #312 evaluates its actual
plan. The hosted service and a workspace administrator cannot yet persist and
approve those exact bytes, policy findings, target, and source context. This
PR adds an encrypted durable artifact boundary and an immutable approval
record. It must not apply or destroy infrastructure.

## Current repo state

The generated Terraform runner remains plan-only. This PR adds an internal
persistence boundary and safe review/approval API, but it does not yet invoke
the runner from the hosted API or worker. The operations bucket is versioned,
SSE-KMS encrypted with S3 Bucket Keys, and expires current versions after 30
days and noncurrent versions after 7 days. Lambda access is disabled by default
and limited to the Nova prefix and existing plan key when explicitly enabled.

## Research / references used

- S3 SSE-KMS: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html
- S3 object versioning: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
- S3 conditional writes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- KMS key policy and least privilege: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- KMS least-privilege permissions: https://docs.aws.amazon.com/kms/latest/developerguide/least-privilege.html

## Work planned for the PR

Persist the exact saved-plan bytes under a server-generated tenant/project/run
key in the existing encrypted, versioned plans bucket. Require SSE-KMS,
version ID, bounded size, conditional creation, and read-back digest
verification. Record an immutable manifest binding proposal, configuration,
provider lock, saved-plan bytes, policy version/result, target account/region,
workspace/project/revision, and Terraform/provider versions. Allow an
authenticated workspace administrator to approve only the current
reviewable manifest by its exact digest. Do not expose plan bytes or a
download URL, do not approve denied/stale/tampered artifacts, and do not add
apply behavior.

## Acceptance criteria

- [x] Saved-plan artifacts use the existing versioned SSE-KMS plan bucket with a tenant-scoped prefix and server-generated object keys.
- [x] Runtime IAM is limited to that prefix and the plan KMS key; no bucket listing is allowed or required.
- [x] Uploads are bounded to 128 MiB, conditional, version-pinned, and read-back verified against the runner digest before a database record is committed.
- [x] The manifest binds the approved revision digest, Nova trusted-context digest, proposal, configuration, provider lock, policy evidence, target, tenant, and exact object version.
- [x] Approval is immutable, requires the exact `administrator` role, is tenant-scoped, and binds the exact current manifest digest. Operators cannot approve this artifact type.
- [x] DENY, deny-severity or unknown-severity findings, missing policy evidence, stale revision, wrong tenant, expired/missing object, tampered plan, duplicate approval, and changed manifest fail closed.
- [x] API responses and audit records do not include raw Terraform values, secrets, bytes, bucket/key/version references, or object URLs. Database triggers reject updates/deletes to artifact and approval records.
- [x] Apply and destroy remain unavailable from this path.
- [x] Focused tests, `make verify`, migration tests, Terraform validation, and documentation checks pass.
- [x] All seven required GitHub Actions checks passed, independent review found
  no remaining blocker, and the PR was merged.

## Acceptance status

Merged. Implementation and local validation are complete. Hosted runner
integration, deployment of the source changes, and customer execution are
deliberately outside this PR.

## Tests / validation performed

Validation performed:

- Focused: `uv run pytest -q tests/test_generated_plan_artifacts.py tests/test_generated_plan_review.py tests/test_db_config.py tests/test_terraform_generation.py tests/test_nova_plan_artifact_infra.py tests/test_serverless_runtime.py` — 74 passed.
- Full: `make verify` — 618 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration passed.
- Fresh clean-room: `make local-proof` — bootstrap, smoke, API contract, customer-plan E2E, seed, trace check, and full verification passed; 618 tests passed. Simple, complex, Day-2, degraded, policy-failure, and readiness-failure demos passed.
- Infrastructure: `terraform validate`, 36 focused static tests, Ruff, and Actions configuration check passed.
- Read-only AWS check in account `654654474502`, `us-east-1`: existing plan bucket versioning is enabled, default encryption is SSE-KMS with S3 Bucket Keys, lifecycle is 30 days current / 7 days noncurrent. No object was uploaded and no AWS resource was created or modified.
- Independent review found and prompted fixes for role overreach, contradictory deny findings, proposal-to-revision context binding, canonical run IDs, and malformed policy evidence. Final review found no remaining blocker.
- All seven CI checks passed in run [41879258328](https://github.com/Bepoadewale/davdeploy/actions/runs/41879258328). PR #314 merged as `8cf1db2250a6a07481ad4184a81419b8ac52490a`.

## Evidence files produced

This PR is a plan-storage and approval-record workflow only. It created no AWS
workload resources and uploaded no real plan. A read-only AWS query on
2026-11-04 found `davdeploy-api` Active with last modification at 07:41 UTC;
the Nova plan-review enable flag and plan-artifact bucket variables were
absent. The PR merged at 18:00 UTC, so its source changes are not deployed.
The hosted worker has no caller for the persistence method. Apply and destroy
remain disabled on this Nova path.

## Boundaries

An approval authorizes only the exact saved plan for subsequent execution
eligibility; it does not itself apply infrastructure. Existing customer-plan
approval semantics must not be silently changed. The model cannot approve.

## Follow-up work

Connect approved saved-plan execution to the trusted hosted worker, add a
second authorization and target-account check immediately before apply, and
implement durable run reconciliation, health observation, recovery, and
exact-resource teardown evidence.
