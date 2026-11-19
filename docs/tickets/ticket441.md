# ticket441 — require encryption for planned SQS queues

PR: https://github.com/Bepoadewale/davdeploy/pull/441
Branch: `feat/nova-sqs-managed-encryption-441`

## Problem / goal

The capability matrix identifies SQS queue encryption as an uncovered
plan-policy requirement. Generated plans can currently create an SQS queue
without showing SQS-managed server-side encryption. Add a fail-closed plan
check for known `sqs_managed_sse_enabled=true`, with regression coverage for
disabled, unknown, and enabled values.

## Current repo state

- Backend main is `e5408186daaa647c10dbce0b442164ed198f185b`.
- Existing policy checks inspect SQS resource policies for public or unbounded
  access, but do not inspect encryption on `aws_sqs_queue` resources.
- The current `modules/sqs-queue` sets SQS-managed encryption and configures a
  dead-letter queue; this change protects other generated SQS queues too.
- No AWS resource or hosted control-plane mutation is needed.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py` — current generated-plan
  policy and unknown-value checks.
- `tests/test_generated_plan_policy.py` — existing plan-policy fixture and SQS
  queue-policy regression tests.
- `infrastructure/terraform/modules/sqs-queue/main.tf` — current module's
  SQS-managed encryption setting.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — SQS queue acceptance and
  current policy gap.

## Work planned for the PR

1. Require every planned `aws_sqs_queue` to expose
   `sqs_managed_sse_enabled=true`.
2. Treat an unknown encryption flag as a policy-critical unknown and deny the
   plan.
3. Bump the generated-plan policy version so approvals use the new rule.
4. Update the SQS matrix row to distinguish this narrow encryption rule from
   remaining queue, consumer, retry, and dead-letter coverage.

## Acceptance criteria

- [x] SQS-managed encryption is required on every planned SQS queue.
- [x] Missing, disabled, or unknown encryption fails closed with redacted
      findings.
- [x] Existing queue-policy checks remain intact.
- [x] The policy version changes with the semantic rule.
- [x] Focused tests, formatting, documentation conventions, diff checks, and
      required PR CI pass on the implementation and evidence heads.
- [x] No hosted runtime, control-plane, AWS, or Terraform state mutation.

## Acceptance status

The policy and regression cases are implemented. The focused policy suite
passes (271 tests), Ruff and documentation conventions pass, and the diff is
clean. All seven checks passed in run `44606644772` on code head `3700e88`, and
again in run `44607504888` on evidence head `52fcd83`. Required checks for the
latest test-record update are tracked on the PR and will be verified before
merge. No hosted runtime or AWS resource was changed.

## Tests / validation performed

- `PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest
  tests/test_generated_plan_policy.py -q` — 271 passed.
- Ruff on the changed policy and test files — passed.
- `GITHUB_PR_NUMBER=441 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- PR CI run `44606644772` passed all seven checks on code head `3700e88`.
- PR CI run `44607504888` passed all seven checks on evidence head `52fcd83`.
- Required checks for the latest test-record update are tracked in PR #441.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket441.md`
- `docs/test/test441.md`

## Boundaries

Do not deploy this policy to the hosted control plane or enable any execution
gate. The rule only verifies SQS-managed queue encryption; it does not prove
queue policy safety beyond existing checks, customer permission sufficiency,
message delivery, retry/DLQ behavior, or consumer correctness.

## Follow-up work

Add plan-bound SQS retry/DLQ and visibility-timeout checks, model consumer
authorization and cost, and gather application lifecycle evidence for the
`aws-jobs-events` architecture entry.
