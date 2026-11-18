# ticket436 — enforce bucket-owner-enforced controls for planned S3 buckets

PR: https://github.com/Bepoadewale/davdeploy/pull/436
Branch: `feat/s3-owner-enforced-policy-436`

## Problem / goal

The generated-plan policy blocks public access, requires secure transport, and
requires explicit default encryption, but it does not require an explicit S3
Object Ownership setting. Require exactly one same-plan ownership-controls
resource for each planned bucket with exactly one rule set to
`BucketOwnerEnforced`. Add that resource to the file-storage module contract and
artifacts Terraform module so the secure mode is expressible by the product.

## Current repo state

Backend `main` is `ca5c7e67692273df5b6c6c336ee59f3e8a80eb16` (PR #435). PR #434
enforces S3 TLS-deny policies; PR #435 requires explicit default encryption.
Both are source-only and do not certify customer workloads. PR #399 remains
open and draft at `b5dff321ac883c191cd5d96dc9d83ad6456807fa`; apply and
credential gates remain disabled pending a designated customer-owned target
and hosted lifecycle evidence.

The verified AWS account is platform account `654654474502`. No SageMaker
endpoint, model, or endpoint configuration is present; four inactive test
Batch definitions and SageMaker lineage evidence remain. The Terraform monitor
is empty. No Terraform process is active. Do not mutate AWS or the hosted
control plane.

## Research / references used

- Amazon S3 User Guide, [Object Ownership and disabling ACLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html).
- Amazon S3 User Guide, [Setting Object Ownership when creating a bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-ownership-new-bucket.html).
- HashiCorp AWS provider, [`aws_s3_bucket_ownership_controls`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_ownership_controls).
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `apps/api/src/davdeploy/module_contracts.py`
- `infrastructure/terraform/modules/artifacts/main.tf`
- `tests/test_generated_plan_policy.py`

AWS documents that `BucketOwnerEnforced` disables ACLs and makes the bucket
owner own every object; it is also the default for new buckets. This package
requires the setting explicitly in the plan so the ownership decision is
visible and reviewable. It does not certify an upload or cross-account data
flow.

## Work planned for the PR

- Match every planned bucket to exactly one ownership-controls resource by known
  bucket name or trusted Terraform reference.
- Require exactly one rule whose known `object_ownership` value is
  `BucketOwnerEnforced`; deny unknown, missing, duplicate, unsupported,
  mismatched, or ambiguous controls.
- Add the resource to the `aws-file-storage` contract and artifacts module.
- Add focused plan-policy/module tests and update the capability matrix for
  merged PR #435 and this draft package.

## Acceptance criteria

- [x] Every planned S3 bucket has exactly one same-plan ownership-controls
  resource.
- [x] The resource has one rule with `object_ownership = "BucketOwnerEnforced"`.
- [x] Unknown, missing, duplicate, incomplete, mismatched, and ambiguous
  controls are denied without echoing plan values.
- [x] `aws-file-storage` permits the ownership resource and `modules/artifacts`
  configures it.
- [x] Focused tests, full verification, documentation conventions, diff checks,
  and recursive Terraform formatting pass.
- [ ] All seven required PR checks pass on the final PR head.

## Acceptance status

Implementation and local validation are complete. Merge is gated on all seven
required checks passing on the final PR head.

## Tests / validation performed

- Focused generated-plan policy and planner tests: 268 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,367 passed; one existing Starlette/httpx deprecation warning.
- Documentation convention checks passed for PR #436.
- `git diff --check` passed.
- `terraform fmt -check -recursive` passed.
- Final PR check status is recorded on the open pull request.

## Evidence files produced

- `docs/tickets/ticket436.md`

## Boundaries

Source-only plan policy and Terraform module changes. Do not deploy the control
plane, alter S3 resources, run Terraform against AWS, issue credentials, or
apply customer infrastructure. Do not enable PR #399 apply or credential
gates. No customer workload is part of this package.

## Follow-up work

Cross-account uploads with ACL-dependent ownership, application-specific ACL
use, upload authorization, object-level access, retention, and lifecycle proof
remain separate checks. Passing this plan policy does not certify an S3
workload or a customer lifecycle.
