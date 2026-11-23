# ticket450 — bind SNS-to-SQS grants to planned resources

PR: https://github.com/Bepoadewale/davdeploy/pull/450
Branch: `feat/sns-sqs-plan-binding-450`

## Problem / goal

The generated-plan policy checks SQS queue policies for broad principals and
resource scope, but it does not prove that an SNS send grant belongs to an
exact planned topic-to-queue subscription. A policy could therefore be valid in
isolation while the subscription or attached queue-policy resource points
elsewhere. Reject those mismatches before human review.

## Current repo state

- Backend `main` is `c5f7a2cf265665451c2ee88e85e34e4bbb048e6c` (PR #449).
- PR #449 records one isolated, direct SNS-to-SQS delivery and teardown in
  [`test449.md`](../test/test449.md). No hosted control-plane state changed.
- Generated-plan policy version is
  `nova-generated-plan-2026-11-23.1` on this branch.
- The general customer-side lifecycle gate is satisfied by accepted PR #437
  ECS evidence; this policy work remains source-only and does not establish
  Nova dispatch or customer workload certification.

## Research / references used

- [`test449.md`](../test/test449.md) — exact same-account SNS/SQS service
  behavior, queue policy, and cleanup evidence.
- AWS [SNS delivery to SQS](https://docs.aws.amazon.com/sns/latest/dg/sns-sqs-as-subscriber.html)
  — subscription and queue-policy relationship.
- AWS [SQS access policy examples](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-examples-of-sqs-policies.html)
  — restricting send permission to SNS and a source topic.
- HashiCorp AWS provider [`aws_sns_topic_subscription`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription)
  and [`aws_sqs_queue_policy`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue_policy)
  — planned subscription endpoint and queue URL inputs.

## Work planned for the PR

1. Derive trusted topic ARNs and queue ARNs/URLs from planned names, account,
   and region.
2. Permit only a same-plan SQS subscription with exact planned topic, queue,
   and matching `aws_sqs_queue_policy.queue_url`.
3. Require exactly one queue grant with `Allow`, SNS service principal,
   `sqs:SendMessage`, exact queue ARN, exact `aws:SourceArn`, and exact
   `aws:SourceAccount`.
4. Deny unsupported protocols, unplanned endpoints, duplicate pairs, broad or
   extra SNS send grants, and grants without a matching subscription.
5. Add regression tests, bump the generated-plan policy version, and update
   the product handoff and capability matrix with scoped claims.

## Acceptance criteria

- [ ] A valid exact planned SNS-to-SQS subscription and attached queue policy
      remains eligible for human review.
- [ ] Missing or mismatched topics, queues, queue URLs, protocols, principals,
      actions, queue ARNs, source ARNs, or source accounts are denied.
- [ ] Duplicate topic/queue subscriptions and unbound/extra SNS send grants
      are denied.
- [ ] Findings do not echo policy values or source identifiers.
- [ ] Existing generated-plan policy tests pass and Ruff reports no issues.
- [ ] Ticket and product evidence pass documentation conventions; all seven
      required PR checks pass before merge.
- [ ] No AWS workload, hosted control-plane, or Terraform state/lock resource
      is changed. Claims distinguish direct service evidence from Nova dispatch.

## Acceptance status

Implementation and regression tests are in progress on a feature branch. The
full generated-plan policy test file currently passes 302 tests, and Ruff
passes for the changed Python files. Documentation and PR checks remain.

## Tests / validation performed

- `.venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py` —
  302 passed.
- `.venv-pr399/bin/python -m ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `git diff --check` — passed before the latest documentation edits; rerun
  after the final diff.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/tickets/ticket450.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

This is a source-only policy change. Do not modify hosted control-plane
runtime/state/locks, production resources, Nova apply gates, or credentials.
Do not claim Nova dispatched the #449 test or that a Nova customer workload was
applied or certified. Preserve the protected untracked `--only-show-errors`
file and `.venv-pr399/`; do not delete local or cloud resources.

## Follow-up work

Continue the Nova goal's dependency-ready security, cost, planner, authorization
and dispatch evidence packages. SNS topic configuration, non-SNS producer
authorization, fan-out behavior, SES delivery, cost coverage, and Nova-hosted
execution remain separate acceptance work.
