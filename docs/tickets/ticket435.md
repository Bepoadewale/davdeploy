# ticket435 — require default encryption for planned S3 buckets

PR: https://github.com/Bepoadewale/davdeploy/pull/435
Branch: `feat/s3-default-encryption-policy-435`

## Problem / goal

The generated-plan policy checks S3 public access and insecure transport, and
rejects an unknown encryption algorithm, but it does not require a same-plan
default-encryption configuration for each planned bucket or reject unsupported
algorithms. Require exactly one encryption configuration per bucket, bound by
known bucket identity or a trusted Terraform reference. Require exactly one
rule with a known supported default algorithm: `AES256`, `aws:kms`, or
`aws:kms:dsse`.

Amazon S3 currently encrypts new objects by default with SSE-S3 even when a
bucket-specific rule is absent. Requiring a declared plan configuration keeps
the selected default explicit and reviewable rather than relying on an implicit
service default.

## Current repo state

Backend `main` is `66d19ab14a33d9a2e16f70bfab1001485158a924`; PR #434 adds
source-only S3 transport enforcement. PR #399 remains open and draft at
`b5dff321ac883c191cd5d96dc9d83ad6456807fa`; apply and credential gates remain
disabled pending hosted plan/apply/lifecycle proof against a designated
customer-owned AWS target. No Nova customer workload has been applied or
certified.

The verified AWS account is platform account `654654474502`. No SageMaker
endpoint, model, or endpoint configuration is present; four inactive test
Batch definitions and SageMaker lineage evidence remain. The Terraform monitor
is empty. No Terraform process is active. Do not mutate AWS or the hosted
control plane.

## Research / references used

- Amazon S3 User Guide, [Protecting data with encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html).
- Amazon S3 User Guide, [Configuring default bucket encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-bucket-encryption.html).
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

AWS documents SSE-S3 (`AES256`), SSE-KMS (`aws:kms`), and DSSE-KMS
(`aws:kms:dsse`) as supported default encryption modes for general purpose S3
buckets. This policy checks the planned default encryption mode; it does not
prove existing object encryption, KMS key authorization, or upload behavior.

## Work planned for the PR

- Match each planned S3 bucket to exactly one default-encryption resource by
  known identity or trusted Terraform reference.
- Require exactly one rule and a known supported default algorithm.
- Deny missing, duplicate, malformed, unknown, unsupported, or ambiguous
  configurations without exposing plan values.
- Add focused tests and update the S3 capability matrix to reflect merged PR
  #434 and this package's draft status.

## Acceptance criteria

- [x] Every planned bucket has exactly one same-plan encryption configuration.
- [x] The configuration has one rule with `AES256`, `aws:kms`, or `aws:kms:dsse`.
- [x] Missing, duplicate, malformed, unknown, unsupported, mismatched, and
  ambiguous configurations are denied.
- [x] Findings do not expose plan values or sensitive content.
- [x] Focused tests, full verification, documentation conventions, diff checks,
  and recursive Terraform formatting pass.
- [ ] All seven required PR checks pass on the final PR head.

## Acceptance status

Implementation and local validation are complete. Merge is gated on all seven
required checks passing on the final PR head.

## Tests / validation performed

- Focused generated-plan policy tests: 233 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,357 passed; one existing Starlette/httpx deprecation warning.
- Documentation convention checks passed for PR #435.
- `git diff --check` passed.
- `terraform fmt -check -recursive` passed.
- Final PR check status is recorded on the open pull request.

## Evidence files produced

- `docs/tickets/ticket435.md`

## Boundaries

Source-only generated-plan policy work. Do not deploy the control plane, alter
S3 resources, run Terraform against AWS, issue credentials, or apply customer
infrastructure. Do not enable PR #399 apply or credential gates. No customer
workload is part of this package.

## Follow-up work

This rule does not verify KMS key policies, object-level upload enforcement,
encryption of existing objects, version retention, ownership controls, or
private upload authorization. Passing the plan check does not certify an S3
workload or a customer lifecycle.
