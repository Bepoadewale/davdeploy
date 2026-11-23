# ticket473

## Problem / goal

Add explicit safety requirements to the bounded DynamoDB module and generated-plan policy. The current module enables encryption and point-in-time recovery, but the policy only checks those values when unknown and does not require deletion protection or a known on-demand billing/table shape.

## Current repo state

- `infrastructure/terraform/modules/dynamodb-table/main.tf` creates one `PAY_PER_REQUEST` table with a caller-provided name and partition key, server-side encryption, and point-in-time recovery.
- `generated_plan_policy.py` has limited unknown-value checks for encryption, deletion protection, and point-in-time recovery, plus a conditional recovery review.
- The evidence matrix records DynamoDB encryption/PITR evidence but no application read/write or restore lifecycle for this exact module root.
- No AWS resources or hosted control-plane resources will be changed by this source-only package.

## Research / references

- AWS DynamoDB developer guide: point-in-time recovery, deletion protection, and on-demand capacity.
- AWS provider `aws_dynamodb_table` resource documentation.
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/dynamodb-table/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned

1. Explicitly enable table deletion protection in the bounded module.
2. Require known, non-empty table name and partition key; require on-demand billing, server-side encryption, deletion protection, and point-in-time recovery in generated plans.
3. Preserve fail-closed behavior for unknown or unsupported values and add regression tests for accepted and rejected plans.
4. Update the root evidence matrix with the exact policy scope and remaining lifecycle/pricing limits.

## Acceptance criteria

- [ ] The module explicitly configures deletion protection and retains its existing encryption, PITR, and on-demand defaults.
- [ ] Policy accepts the exact safe module shape and denies missing, unsafe, or unknown required settings.
- [ ] Regression tests cover valid, unsafe, unknown, and sensitive-value redaction cases.
- [ ] The evidence matrix describes this source-only policy and leaves application behavior, restore, and complete cost evidence open.
- [ ] No AWS or hosted control-plane resources are changed.
- [ ] Focused and full policy tests, formatting, documentation conventions, Terraform validation, and `git diff --check` pass.
- [ ] Final-head CI and review/merge state are tracked; merge only after required checks pass.

## Boundaries

Source and documentation only. Do not apply the module to AWS. Do not access or change the hosted control plane. Do not claim complete DynamoDB support, customer workload lifecycle, or full pricing from plan checks.

Preserve `--only-show-errors`, `.venv-pr399/`, `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and all generated provider lock files.

## Follow-up

Record isolated customer-side table operations, update/recovery, teardown, independent absence, and exact regional pricing evidence in a separate authorized package.
