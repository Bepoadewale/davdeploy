# ticket452 — validate EventBridge target retry and DLQ recovery

PR: https://github.com/Bepoadewale/davdeploy/pull/452
Branch: `feat/eventbridge-dlq-recovery-452`

## Problem / goal

The generated-plan policy now binds EventBridge SQS targets to an exact rule
and queue grant, but it does not require bounded retry settings or bind the
target's dead-letter destination to a separately authorized queue. Add those
checks and a controlled same-account test that observes failure routing,
permission repair, successful delivery, and teardown.

## Current repo state

- Backend `main` is `24000865fbf6e3d2c8325661a6e1494dd896de9b` (PR #451).
- PR #451 binds a planned EventBridge bus/rule, SQS target, queue-policy URL,
  and exact rule source ARN. It does not yet enforce retry or DLQ configuration.
- [`test257.md`](../test/test257.md) records one direct EventBridge-to-SQS
  delivery and teardown, without a failure-to-DLQ or recovery cycle.
- The hosted control plane and its Terraform state/locks are out of scope.

## Research / references used

- [`test257.md`](../test/test257.md) — direct EventBridge-to-SQS behavior.
- AWS [retry policies and dead-letter queues](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-custom-bus-retry.html)
  — retry range is 0–185 attempts and 60–86,400 seconds; a DLQ retains events
  after exhausted retries.
- AWS [EventBridge DLQ requirements and permissions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-dlq.html)
  — DLQs must be standard SQS queues in the rule's region, with an exact rule
  ARN resource grant when configured through the API.
- HashiCorp AWS provider [`aws_cloudwatch_event_target`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target)
  — target retry policy and dead-letter configuration fields.

## Work planned for the PR

1. Require known retry attempt and event-age values within AWS bounds for
   supported EventBridge-to-SQS targets.
2. Require a distinct, same-plan standard SQS DLQ and bind its attached queue
   policy to `events.amazonaws.com`, `sqs:SendMessage`, exact queue ARN, and
   exact rule source ARN.
3. Keep normal SQS consumer redrive and EventBridge delivery DLQ identities
   separate in the plan contract.
4. Add regression tests for missing/out-of-range retries, missing/unplanned/
   FIFO/same-queue DLQs, bad DLQ grants, and SNS/EventBridge grant coexistence.
5. Add a pinned fixture and body-redacting probe. Use a deliberately
   restrictive wrong rule source on the primary target policy to force a
   delivery failure, while the EventBridge DLQ policy remains exact; repair
   the target grant, verify recovery delivery, then destroy the test stack.
6. Keep the test direct same-account service evidence. Do not change hosted
   control-plane state or claim Nova dispatch.

## Acceptance criteria

- [x] Retry policy values are known and within AWS ranges; missing and
      out-of-range values are denied.
- [x] A distinct planned standard DLQ is required, and its queue URL and
      EventBridge grant bind to the exact rule and queue.
- [x] An unplanned, FIFO, same-as-target, or incorrectly authorized DLQ is
      denied.
- [x] One synthetic event fails delivery to the primary queue and reaches the
      EventBridge DLQ with a matching marker.
- [x] After repairing the exact source rule grant, a second synthetic event
      reaches the primary queue with a matching marker.
- [x] The probe prints no message bodies. The exact test stack is destroyed
      through the Terraform run monitor and independently confirmed absent.
- [x] The generated-plan policy test file, Ruff, docs conventions, and all
      seven required PR checks pass.
- [x] Control-plane runtime/state/locks and production/customer resources are
      untouched; evidence is not described as Nova dispatch or customer apply.

## Acceptance status

All source, regression, direct-service, and cleanup criteria are met for this
test shape. PR #452 remains a draft; its final head `2162265` passed all seven
required checks in run
[45215572683](https://github.com/Bepoadewale/davdeploy/actions/runs/45215572683).
This is direct same-account EventBridge-to-SQS evidence only, not Nova
dispatch, hosted execution, or broad customer certification.

## Tests / validation performed

- `.venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py` —
  330 passed, including the retry and DLQ regression cases.
- Ruff, Python syntax, Terraform formatting/validation, documentation
  conventions, and `git diff --check` passed for the fixture and policy.
- The corrected isolated AWS test observed target failure to the exact
  EventBridge DLQ, repaired the queue grant, observed recovery delivery, and
  removed the exact eight-resource stack. `test452.md` records monitored run
  IDs, plans, results, independent absence, and boundaries.
- No hosted control-plane operation was performed.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/tickets/ticket452.md`
- `docs/test/test452.md`
- `docs/test/fixtures/nova-eventbridge-dlq-452/main.tf`
- `docs/test/fixtures/nova-eventbridge-dlq-452/probe.py`
- `docs/test/fixtures/nova-eventbridge-dlq-452/.terraform.lock.hcl`

## Boundaries

Use only the exact `davdeploy-nova-eventbridge-dlq-452-nov23a1` test prefix in
account `654654474502`, region `us-east-1`. Keep state, plans, variables, and
generated files outside the repository. Route every apply/destroy through the
PID-based Terraform monitor; review saved create/update/destroy plans and never
overlap mutations. Do not touch control-plane runtime/state/locks, production
resources, customer credentials, Nova gates, or lineage evidence. Keep AWS
errors and message bodies out of output. Preserve protected untracked
`--only-show-errors` and `.venv-pr399/`.

## Follow-up work

This test covers one direct EventBridge-to-SQS target and DLQ shape. It does
not prove Nova-generated plan/apply, EventBridge target roles, other target
families, replay/redrive behavior, or full `aws-jobs-events` coverage.
