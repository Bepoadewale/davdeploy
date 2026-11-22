# ticket445 — bind SQS retry and Lambda consumer safety to the generated plan

PR: https://github.com/Bepoadewale/davdeploy/pull/445
Branch: `feat/nova-sqs-retry-consumer-445`

## Problem / goal

PR #441 requires SQS-managed encryption, but a Nova plan can still omit queue
visibility or dead-letter settings, point a source queue at an unplanned or
unrelated DLQ, configure too few Lambda retries, or wire a Lambda consumer
without the exact queue-read permissions. For Lambda event sources, the queue
visibility timeout must account for the function timeout and batch window.
These gaps can cause lost/repeated processing or a queue that is not executable
by its declared consumer.

Add a fail-closed generated-plan contract for queue delivery settings and
same-plan Lambda SQS consumers. Continue to block plan approval whenever
consumer compute or queue request/transfer costs are unknown or unsupported;
do not present partial pricing as a complete estimate.

## Current repo state

- Backend `main` is `7f9148a12cb5ec91ed7c5e19c49a1ce8c7980c98` (PR #444).
- PR #441 requires known SQS-managed encryption and preserves existing queue
  policy checks; retry/DLQ/visibility and consumer authorization are open.
- `modules/sqs-queue` configures encryption, a source-to-DLQ redrive policy,
  and `maxReceiveCount=3`; it does not prove generated plans preserve this
  contract or link a consumer's permissions to the queue.
- The hosted control plane and Nova execution gates remain untouched and
  disabled. This PR is source policy, local regression tests, and documentation.
- Direct ECS Express lifecycle evidence in PR #437 satisfies the general
  customer-side plan/apply/health/update/recovery/teardown gate. It does not
  prove SQS delivery or Nova dispatch.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py` and
  `tests/test_generated_plan_policy.py` — current generated-plan checks.
- `apps/api/src/davdeploy/generated_plan_pricing.py` — existing bounded SQS
  request and Lambda pricing inputs; unsupported material costs block approval.
- `infrastructure/terraform/modules/sqs-queue/main.tf` — current queue/DLQ
  module configuration.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — the SQS and jobs/events
  acceptance gaps.
- AWS [Lambda SQS event-source configuration](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html) — visibility timeout, retries, and execution-role requirements.
- AWS [SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html) — redrive behavior, source/DLQ relationship, and retention guidance.
- AWS [Lambda execution-role permissions for SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-lambda-function-trigger.html) — required receive, delete, and attribute permissions.
- HashiCorp AWS provider [`aws_sqs_queue`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue) — planned queue fields and JSON redrive configuration.

## Work planned for the PR

1. Require known, valid queue visibility and retention settings for planned
   SQS queues; preserve PR #441's encryption and queue-policy behavior.
2. For each planned SQS-to-Lambda event source mapping, require a plan-bound
   source queue, consumer function and execution role. Validate the source
   queue's redrive target, explicit retry count, and Lambda visibility-timeout
   relationship, including any configured batching window.
3. Require the linked consumer role to grant the SQS receive, delete and
   attribute actions on the exact source queue ARN. Reject unresolved or
   wildcard resource/action evidence. Keep unsupported attachment/policy
   shapes fail-closed and identify their limits.
4. Add regression fixtures for valid and unsafe queue, redrive, timeout,
   event-source and permission combinations, including unknown values.
5. Update the Nova SQS policy matrix and ticket/test evidence. State that
   message processing, idempotency, producer authorization, runtime pricing,
   and real SQS lifecycle evidence remain unproven unless separately evidenced.

## Acceptance criteria

- [ ] Queue visibility/retention unknowns and out-of-range values are denied.
- [ ] An SQS Lambda mapping is denied unless its source queue, function, and
      execution role are bound to resources in the same plan.
- [ ] A Lambda-consumed queue has an explicit valid redrive policy pointing to
      one same-account, same-region planned queue; the target cannot be the
      source or form a redrive cycle; receive count is within the documented
      product retry bound; DLQ retention exceeds source retention.
- [ ] For Lambda consumers, queue visibility is at least six times the planned
      function timeout plus the configured batching window; unknown values
      fail closed.
- [ ] The consumer role grants the required SQS read/acknowledgement actions
      on the exact planned source ARN. Wildcard or unresolved permissions do
      not satisfy the rule.
- [ ] Existing SQS encryption and queue-policy checks remain intact, and the
      semantic policy version is bumped.
- [ ] Focused tests, Ruff, documentation conventions, diff checks, and all
      required PR CI checks pass on the merge-ready head.
- [ ] Pricing documentation and findings remain honest: queue request units
      and consumer compute/transfer must be known and supported before costed
      approval; no complete quote is claimed by these policy checks.
- [ ] No AWS resource, Terraform state, hosted control-plane runtime, customer
      credential, or Nova execution gate is mutated.

## Acceptance status

Implementation has not started. This ticket is the draft-PR bootstrap and will
be updated with concrete test outcomes and any narrowed supported shapes
before the PR is marked ready for review.

## Tests / validation performed

- None yet. This bootstrap contains documentation only; no AWS or Terraform
  operation was run.

## Evidence files produced

- `docs/tickets/ticket445.md`
- `docs/test/test445.md` — to be added before this PR is marked ready.

## Boundaries

Do not deploy the policy to the hosted control plane, enable any Nova execution
gate, or mutate AWS resources. Do not claim SQS processing, idempotency, hosted
dispatch, or customer workload certification based on plan-policy fixtures.
Keep secrets out of source, logs, plans, and test evidence.

## Follow-up work

Gather a separately scoped, isolated SQS consumer lifecycle run with success,
failure-to-DLQ, retry, redrive/idempotency, update, cleanup, and independent
absence evidence. Continue cost and per-entry coverage across all 26
architecture entries and 30 Terraform roots.
