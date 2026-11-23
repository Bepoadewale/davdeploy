# ticket475

PR: [#475 — feat: enforce bounded Kinesis plan safety](https://github.com/Bepoadewale/davdeploy/pull/475) (draft)
Branch: `feat/kinesis-plan-safety-475`

## Problem / goal

The Kinesis Terraform module uses one provisioned shard, 24-hour retention, and KMS encryption with the AWS-managed Kinesis key. Generated-plan policy currently does not verify these settings, so a generated plan could silently select a larger or unencrypted stream shape.

## Current repo state

- `infrastructure/terraform/modules/kinesis-stream/main.tf` accepts a caller shard count, sets retention to 24 hours, and enables KMS encryption through `alias/aws/kinesis`.
- The evidence matrix records one accepted Kinesis record in `test258`, but no consumer processing, replay, failure recovery, or Nova-dispatched run.
- No Kinesis AWS resource or hosted control-plane resource will be changed by this source-only package.

## Research / references used

- [Terraform AWS provider `aws_kinesis_stream` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kinesis_stream)
- [Kinesis retention period](https://docs.aws.amazon.com/streams/latest/dev/kinesis-extended-retention.html)
- [Kinesis server-side encryption](https://docs.aws.amazon.com/streams/latest/dev/what-is-sse.html)
- [Kinesis concepts and shard capacity](https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/kinesis-stream/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Bound the module to exactly one provisioned shard and explicitly identify provisioned capacity mode.
2. Require a known non-empty stream name, one shard, 24-hour retention, KMS encryption, and the AWS-managed Kinesis key in generated plans.
3. Add regression tests for the accepted shape, unsafe settings, and unknown critical values.
4. Update the root evidence matrix with source-only policy scope and remaining consumer, lifecycle, and cost gaps.

## Acceptance criteria

- [ ] The module explicitly configures one provisioned shard, 24-hour retention, and KMS encryption with the AWS-managed Kinesis key.
- [ ] Policy accepts the intended bounded shape and denies missing, unsafe, or unknown required settings.
- [ ] Regression tests cover valid, unsafe, unknown, and finding-value redaction cases.
- [ ] The evidence matrix does not claim consumer behavior, full pricing, lifecycle, or Nova dispatch from the policy checks.
- [ ] No AWS or hosted control-plane resources are changed.
- [ ] Focused policy tests, Ruff, Terraform formatting/validation, documentation conventions, and `git diff --check` pass.
- [ ] Final-head CI and review state are tracked; merge only after required checks pass.

## Acceptance status

Implementation is pending.

## Tests / validation performed

- Pending.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/kinesis-stream/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket475.md`

## Boundaries

Source and documentation only. Do not create or change Kinesis resources. Do not access or change the hosted control plane. Do not claim stream consumers, replay, failure recovery, complete pricing, or Nova execution from plan checks.

## Follow-up work

Record customer-side producer and consumer behavior, retry/replay, update/recovery, teardown, independent absence, and exact regional pricing in a separately authorized package.
