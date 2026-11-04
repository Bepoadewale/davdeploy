# ticket313 Store generated plans and bind immutable review approval

PR: #313 https://github.com/Bepoadewale/davdeploy/pull/313 (closed unmerged)
Branch: feat/nova-saved-plan-approval

Status: Closed without merge. The saved-plan storage and approval
work was superseded and implemented through PR #314; use
[`ticket314.md`](ticket314.md) for merged code and validation evidence.

## Problem / goal

PR #311 creates a local encrypted-by-permissions Terraform saved-plan artifact
and #312 evaluates its actual plan. Neither the hosted service nor an
authorized human reviewer can yet retrieve that exact plan later or approve
the exact bytes, policy findings, target, and source context. This PR adds a
durable encrypted artifact boundary and an immutable approval record. It must
not apply or destroy infrastructure.

## Current repo state

The generic runner is plan-only and has no HTTP or hosted-worker integration.
Existing workspace plan approvals cover customer-authored plan JSON, not a
Terraform saved plan. Existing execution-artifact permissions must be checked
before reuse. The generic Nova execution path remains disabled.

## Research / references used

- AWS S3 server-side encryption with AWS KMS: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html
- AWS S3 object versioning: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
- AWS S3 conditional writes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- AWS KMS key policies: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html

## Work planned for the PR

Persist the exact saved-plan bytes under a server-generated tenant/project/run
key with KMS encryption, version pinning, size limits, digest verification,
and least-privilege access. Record an immutable manifest binding the proposal,
configuration, provider lock, saved-plan bytes, policy version/result, account,
region, workspace/project/revision, Terraform/provider versions, and object
version. Allow an authenticated workspace administrator to approve only the
current reviewable manifest by its exact digest. Do not expose plan bytes or a
download URL, do not approve denied/stale/tampered artifacts, and do not add
apply behavior.

## Acceptance criteria

- [ ] Plan artifacts use an explicit encrypted, versioned, tenant-scoped storage boundary and server-generated object keys.
- [ ] Uploads are size-bounded, non-overwriting or version-pinned, and verified against the runner's saved-plan digest before success is recorded.
- [ ] The canonical manifest binds all plan, proposal, configuration, provider-lock, policy, target, and tenant identity fields.
- [ ] Approval is immutable, administrator-authorized, tenant-scoped, and requires the exact current manifest digest.
- [ ] DENY, missing policy evidence, stale revision, wrong tenant, tampered plan, duplicate approval, and changed manifest fail closed.
- [ ] API responses, audit records, and logs do not include raw Terraform plan values, secret material, or artifact bytes.
- [ ] Apply and destroy remain unavailable from this path.
- [ ] Focused tests, `make verify`, migration tests, documentation checks, and required CI pass.
- [ ] Review is complete.

## Acceptance status

Closed unmerged; this PR did not deliver implementation. Its objective was
superseded by PR #314.

## Tests / validation performed

No implementation was merged through PR #313. The final implementation and
verification evidence are recorded under PR #314.

## Evidence files produced

PR #313 produced no merged artifact or AWS workload. See
[`ticket314.md`](ticket314.md) for the replacement implementation evidence.

## Boundaries

An approval authorizes only the exact saved plan for human review/execution
eligibility. It does not itself apply infrastructure. Existing customer-plan
approval semantics must not be silently changed. The model cannot approve.

## Follow-up work

Connect approved saved-plan execution to the trusted hosted worker, add a
second authorization and target-account check immediately before apply, and
implement durable run reconciliation, health observation, recovery, and
exact-resource teardown evidence.
