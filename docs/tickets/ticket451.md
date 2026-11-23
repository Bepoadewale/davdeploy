# ticket451 — bind EventBridge SQS targets to planned rules

PR: https://github.com/Bepoadewale/davdeploy/pull/451
Branch: `feat/eventbridge-sqs-plan-binding-451`

## Problem / goal

The generated-plan policy does not currently connect an EventBridge SQS target
to its planned event bus and rule or to the SQS queue policy that authorizes
delivery. Add a fail-closed check for the directly observed same-account
resource-policy path. Do not treat the existing direct AWS delivery test as
Nova execution evidence.

## Current repo state

- Backend `main` is `8f6f94e92d750a3a496fde9da1d0b59c4baea802` (PR #450).
- Merged PR #450 binds exact planned SNS-to-SQS topic, queue, policy URL, and
  conditional send grant. Its source does not change AWS or hosted state.
- [`test257.md`](../test/test257.md) records one direct EventBridge-to-SQS
  delivery and teardown, but not generated-plan policy or Nova dispatch.
- This package is source-only; no AWS workload or hosted control-plane change
  is required.

## Research / references used

- [`test257.md`](../test/test257.md) — direct EventBridge-to-SQS service
  behavior and cleanup evidence.
- AWS [resource-based EventBridge policies](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html)
  — SQS target permission uses the `events.amazonaws.com` service principal,
  `sqs:SendMessage`, exact queue ARN, and rule source ARN.
- AWS [cross-service confused deputy prevention](https://docs.aws.amazon.com/eventbridge/latest/userguide/cross-service-confused-deputy-prevention.html)
  — recommends full `aws:SourceArn` and `aws:SourceAccount` restrictions.
- HashiCorp AWS provider [`aws_cloudwatch_event_rule`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule)
  and [`aws_cloudwatch_event_target`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target)
  — rule bus/name and target bus/rule/ARN inputs.

## Work planned for the PR

1. Derive trusted EventBridge bus/rule ARNs from planned names, account, and
   region, requiring a same-plan custom bus or the default bus.
2. Bind each known SQS target ARN and bus/rule pair to one queue policy attached
   to that exact planned queue URL.
3. Require one exact `events.amazonaws.com` `sqs:SendMessage` grant with the
   exact queue ARN and full rule source ARN. Accept the exact source-account
   condition as an additional restriction.
4. Deny unknown or unplanned identities, duplicate rule/target pairs, broad or
   orphaned EventBridge send grants, and target IAM-role shapes outside this
   policy's supported path.
5. Keep SNS and EventBridge grants independently bound while allowing both
   exact grants to share one queue policy.
6. Add regression tests, bump the generated-plan policy version, and reconcile
   the handoff and evidence matrix without broadening service-test claims.

## Acceptance criteria

- [x] A valid exact planned EventBridge bus/rule/target and attached SQS queue
      policy remains eligible for human review.
- [x] The grant has the exact EventBridge principal, action, queue ARN, and rule
      source ARN; an optional source-account condition must match the trusted
      account.
- [x] Unplanned buses/rules/queues, unknown destinations, target roles,
      mismatched queue URLs, duplicate pairs, broad grants, and orphan grants
      are denied.
- [x] Exact SNS and EventBridge grants can coexist in one queue policy.
- [x] Findings do not echo policy values or source identifiers.
- [x] The generated-plan policy test file, Ruff, documentation conventions,
      and all seven required PR checks pass before merge.
- [x] No AWS workload, hosted control-plane, Terraform state, or lock resource
      is changed. Documentation makes no Nova dispatch or customer-apply claim.

## Acceptance status

The EventBridge binding and regression tests are complete. The full
generated-plan policy test file passes 320 tests; Ruff and documentation
conventions pass. All seven required PR checks passed on the tested revision.
No AWS or hosted control-plane state changed.

## Tests / validation performed

- `.venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py` —
  320 passed.
- `.venv-pr399/bin/python -m ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `.venv-pr399/bin/python scripts/check_doc_conventions.py` — passed.
- PR CI run `45206796692` passed all seven checks on commit `028949c`.
- No AWS mutation or hosted control-plane operation was performed.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/tickets/ticket451.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

This is a source-only policy change. Do not touch control-plane runtime,
state/locks, production resources, Nova apply gates, or customer credentials.
Do not claim the #257 direct EventBridge test was Nova-dispatched or that a
Nova customer workload was applied or certified. Preserve protected untracked
`--only-show-errors` and `.venv-pr399/`; do not delete local or cloud resources.

## Follow-up work

EventBridge target-role permission policy, non-SQS target families, Step
Functions authorization, SNS topic configuration, SES delivery, producer
authorization outside the supported paths, cost coverage, and Nova-originated
`aws-jobs-events` execution remain separate work.
