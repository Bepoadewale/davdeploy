# ticket434 — require secure transport for planned S3 buckets

PR: https://github.com/Bepoadewale/davdeploy/pull/434
Branch: `feat/s3-secure-transport-policy-434`

## Problem / goal

The generated-plan policy blocks public S3 access but does not require a bucket
policy that rejects non-TLS requests. Require every planned S3 bucket to have
one same-plan bucket policy denying all S3 actions for insecure transport on
both the bucket and its objects. Exclude AWS service principals from that
network-context denial so AWS service-to-service requests continue to work.
Also inspect explicitly planned S3 bucket policies for the same protection.

## Current repo state

Backend `main` is `9bef966a474d059b2d7e9d123da858707628b07b`; PR #433 added
source-only CloudFront origin TLS rules. PR #399 is open/draft at
`b5dff321ac883c191cd5d96dc9d83ad6456807fa`; all seven checks passed in run
`44216325844`, and apply/credential gates remain disabled. The hosted control
plane remains PR #420 commit `9951caa9244128b1551fea3af66b1bdbf884c800`. No Nova
customer workload has been applied or certified.

## Research / references used

- AWS Security Hub CSPM, [S3 buckets should require requests over HTTPS](https://docs.aws.amazon.com/securityhub/latest/userguide/s3-controls.html).
- Amazon S3 User Guide, [Bucket policy examples using condition keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html).
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

AWS recommends an explicit Deny for `s3:*` when `aws:SecureTransport` is
false, covering both the bucket ARN and its object ARNs. AWS also documents
that network-context keys can be redacted for service-to-service requests and
shows `aws:PrincipalIsAWSService` set to false to avoid unintentionally
blocking AWS service principals.

## Work planned for the PR

- Match each planned S3 bucket to exactly one bucket policy by known bucket
  identity or trusted Terraform resource reference.
- Require an explicit Deny for `s3:*` over the bucket and all its objects,
  conditioned on non-secure transport and non-AWS-service principal.
- Inspect standalone S3 bucket policies and fail closed on missing, malformed,
  ambiguous, incomplete, or unknown security settings.
- Add focused negative and positive plan-policy tests and update the S3 row in
  the source/deployed capability matrix.

## Acceptance criteria

- [ ] Every planned S3 bucket has exactly one policy bound to that bucket.
- [ ] A valid TLS-deny statement covers bucket and object ARNs and excludes
  AWS service principals from the transport condition.
- [ ] Missing policy, incomplete action/resource coverage, wrong conditions,
  malformed policy JSON, unknown values, and duplicate policies are denied.
- [ ] Findings do not expose plan values or sensitive content.
- [ ] Focused tests, full verification, documentation conventions, and diff
  checks pass.
- [ ] All seven required PR checks pass on the final PR head.

## Acceptance status

Ticket-first bootstrap only. Implementation and validation have not started.

## Tests / validation performed

Pending ticket-first documentation and diff checks.

## Evidence files produced

- `docs/tickets/ticket434.md`

## Boundaries

Source-only generated-plan policy work. Do not deploy the control plane, alter
S3 resources, run Terraform against AWS, issue credentials, or apply customer
infrastructure. No customer workload is part of this package.

## Follow-up work

Encryption, retention, ownership, and private-upload authorization remain
separate S3 acceptance items. Passing this policy check does not certify an
S3 workload or a customer lifecycle.
