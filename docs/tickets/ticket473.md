# ticket473

PR: [#473 — feat: enforce bounded DynamoDB plan safety](https://github.com/Bepoadewale/davdeploy/pull/473) (draft)
Branch: `feat/dynamodb-plan-safety-473`

## Problem / goal

Add explicit safety requirements to the bounded DynamoDB module and generated-plan policy. The current module enables encryption and point-in-time recovery, but the policy only checks those values when unknown and does not require deletion protection or a known on-demand billing/table shape.

## Current repo state

- `infrastructure/terraform/modules/dynamodb-table/main.tf` creates one `PAY_PER_REQUEST` table with a caller-provided name and partition key, server-side encryption, and point-in-time recovery.
- `generated_plan_policy.py` has limited unknown-value checks for encryption, deletion protection, and point-in-time recovery, plus a conditional recovery review.
- The evidence matrix records DynamoDB encryption/PITR evidence but no application read/write or restore lifecycle for this exact module root.
- No AWS resources or hosted control-plane resources will be changed by this source-only package.

## Research / references used

- [DynamoDB point-in-time recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html)
- [DynamoDB deletion protection](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.Basics.html)
- [DynamoDB on-demand capacity mode](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [AWS provider `aws_dynamodb_table` resource documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/dynamodb-table/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Explicitly enable table deletion protection in the bounded module.
2. Require known, non-empty table name and partition key; require on-demand billing, server-side encryption, deletion protection, and point-in-time recovery in generated plans.
3. Preserve fail-closed behavior for unknown or unsupported values and add regression tests for accepted and rejected plans.
4. Update the root evidence matrix with the exact policy scope and remaining lifecycle/pricing limits.

## Acceptance criteria

- [x] The module explicitly configures deletion protection and retains its existing encryption, PITR, and on-demand defaults.
- [x] Policy accepts the exact safe module shape and denies missing, unsafe, or unknown required settings.
- [x] Regression tests cover valid, unsafe, unknown, and sensitive-value redaction cases.
- [x] The evidence matrix describes this source-only policy and leaves application behavior, restore, and complete cost evidence open.
- [x] No AWS or hosted control-plane resources are changed.
- [x] Focused/full policy tests, formatting, documentation conventions, Terraform validation, and `git diff --check` pass.
- [ ] Final-head CI and review/merge state are tracked; merge only after required checks pass.

## Acceptance status

Implementation is complete. All local validation is complete; final-head CI and review/merge remain pending. The change is source-only and does not establish workload or hosted Nova evidence.

## Tests / validation performed

- `tests/test_generated_plan_policy.py -q` — 406 passed.
- Ruff — passed.
- Terraform format check — passed.
- `GITHUB_PR_NUMBER=473 .venv-pr399/bin/python scripts/check_doc_conventions.py` — passed after correcting the required ticket headings.
- `terraform -chdir=infrastructure/terraform/modules/dynamodb-table init -backend=false -input=false` — passed. The generated provider lock file is preserved locally and not committed.
- `terraform -chdir=infrastructure/terraform/modules/dynamodb-table validate` — passed.
- `git diff --check` — passed.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/dynamodb-table/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket473.md`

## Boundaries

Source and documentation only. Do not apply the module to AWS. Do not access or change the hosted control plane. Do not claim complete DynamoDB support, customer workload lifecycle, or full pricing from plan checks.

Deletion protection prevents normal table deletion while enabled. Any future intentional teardown must first use a separately reviewed plan to disable protection; this PR does not authorize such a change.

Preserve `--only-show-errors`, `.venv-pr399/`, `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and all generated provider lock files.

## Follow-up work

Record isolated customer-side table operations, update/recovery, teardown, independent absence, and exact regional pricing evidence in a separate authorized package.
