# ticket314 Store generated plans and bind immutable review approval

PR: #314 (draft)
Branch: feat/nova-saved-plan-approval

## Problem / goal

PR #311 creates a local-only Terraform saved plan and #312 evaluates its actual
plan. The hosted service and a workspace administrator cannot yet persist and
approve those exact bytes, policy findings, target, and source context. This
PR adds an encrypted durable artifact boundary and an immutable approval
record. It must not apply or destroy infrastructure.

## Current repo state

The generated Terraform runner remains plan-only and is not exposed through
the hosted API or worker. Existing workspace approvals cover customer-authored
plan JSON, not generated Terraform saved plans. The operations bootstrap has a
versioned SSE-KMS encrypted plans bucket with a separate key and lifecycle
retention. The control-plane runtime does not yet have access to a dedicated
Nova plan prefix.

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

- [ ] Saved-plan artifacts use the existing versioned SSE-KMS plan bucket with a new tenant-scoped prefix and server-generated object keys.
- [ ] Runtime IAM is limited to that exact prefix and the plan KMS key; no bucket listing is required.
- [ ] Uploads are size-bounded, conditional, version-pinned, and read-back verified against the runner's saved-plan digest before success is recorded.
- [ ] The canonical manifest binds all plan, proposal, configuration, provider-lock, policy, target, and tenant identity fields.
- [ ] Approval is immutable, administrator-authorized, tenant-scoped, and requires the exact current manifest digest.
- [ ] DENY, missing policy evidence, stale revision, wrong tenant, expired/missing object, tampered plan, duplicate approval, and changed manifest fail closed.
- [ ] API responses, audit records, and logs do not include raw Terraform plan values, secret material, artifact bytes, or object URLs.
- [ ] Apply and destroy remain unavailable from this path.
- [ ] Focused tests, `make verify`, migration tests, documentation checks, and required CI pass.
- [ ] Review is complete.

## Acceptance status

Draft. Implementation and validation pending.

## Tests / validation performed

Pending.

## Evidence files produced

This PR is a plan-storage and approval-record workflow only. It creates no AWS
workload resources. Record tests and any storage integration evidence here.

## Boundaries

An approval authorizes only the exact saved plan for subsequent execution
eligibility; it does not itself apply infrastructure. Existing customer-plan
approval semantics must not be silently changed. The model cannot approve.

## Follow-up work

Connect approved saved-plan execution to the trusted hosted worker, add a
second authorization and target-account check immediately before apply, and
implement durable run reconciliation, health observation, recovery, and
exact-resource teardown evidence.
