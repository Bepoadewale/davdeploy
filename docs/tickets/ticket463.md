# ticket463

PR: [#463 — feat: enforce safe KMS key plan settings](https://github.com/Bepoadewale/davdeploy/pull/463) (draft)

Branch: `feat/kms-key-plan-safety-463`

## Problem / goal

The customer-managed KMS module currently relies on defaults for key type and
usage, uses a seven-day deletion window, and does not explicitly constrain the
key to one Region. Generated-plan policy checks only that key usage and the
deletion window are known. Make the supported baseline explicit in the module
and deny plans that weaken or leave these settings unknown.

## Current repo state

- `infrastructure/terraform/modules/kms-key/main.tf` defines the customer key
  and alias. The key has rotation enabled, but previously used a seven-day
  deletion window and implicit defaults for key type, usage, and Region scope.
- Generated-plan policy had no known-value enforcement for KMS key type,
  rotation, or Region scope.
- No root-specific customer-managed KMS lifecycle evidence exists. Existing
  Kinesis evidence uses AWS-managed encryption and is not equivalent.
- The KMS key must be scheduled for deletion and remains in a pending-deletion
  state for 7–30 days. AWS lists customer-managed keys as billable, so this PR
  does not create a key solely to obtain lifecycle evidence.

## Research / references used

- [Terraform AWS provider `aws_kms_key` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key.html)
- [AWS KMS key deletion and waiting period](https://docs.aws.amazon.com/kms/latest/developerguide/deleting-keys.html)
- [AWS KMS pricing](https://aws.amazon.com/kms/pricing/)
- [AWS KMS automatic rotation requirements](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/kms-key/main.tf`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark key type, key usage, rotation, deletion wait, and multi-Region scope as
   critical known values in generated plans.
2. Require `SYMMETRIC_DEFAULT`, `ENCRYPT_DECRYPT`, automatic rotation enabled,
   a 30-day deletion wait, and `multi_region = false`.
3. Set these values explicitly in the KMS Terraform module.
4. Add passing, unsafe-value, and unknown-value regression tests.
5. Update the Nova evidence matrix while leaving key-policy, consumer-binding,
   cost, and customer-managed-key lifecycle evidence open.

## Acceptance criteria

- [x] The checked-in module explicitly declares the supported KMS key
  configuration.
- [x] Generated-plan evaluation permits the supported configuration and
  denies unsupported, weakened, or unknown safety settings.
- [x] Regression tests cover all five settings and their unknown values.
- [x] The capability matrix records source checks and keeps full KMS support
  and lifecycle evidence unproven.
- [x] No AWS key is created, changed, or scheduled for deletion by this PR;
  hosted control-plane state is not accessed or changed.
- [ ] Focused and full policy tests, formatting, Terraform validation,
  documentation conventions, and `git diff --check` pass.
- [ ] Final-head CI passes and the PR is reviewed and merged through GitHub.

## Acceptance status

Implementation is in progress on PR #463. This work adds a plan-policy and
module baseline only; it does not establish customer-managed KMS lifecycle
support.

## Tests / validation performed

Pending.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/kms-key/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket463.md`

## Boundaries

- Do not mutate AWS KMS resources or hosted control-plane resources for this
  code-only package.
- Do not claim KMS key-policy validation, consumer access, rotation operation,
  deletion recovery, full cost coverage, or complete customer-managed KMS
  lifecycle support.
- Preserve `--only-show-errors`, `.venv-pr399/`, and
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`.

## Follow-up work

Add a separately approved, cost-bounded customer-managed KMS test that verifies
the exact module root, key policy, consumer encryption/decryption, rotation, and
recovery while accounting for the AWS deletion waiting period and charges.
