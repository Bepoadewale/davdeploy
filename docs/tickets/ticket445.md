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
2. Require each planned queue to belong to one bounded source/DLQ pair. The
   source uses a plan-known target ARN and `maxReceiveCount` 5–10; the DLQ
   accepts only that source and retains messages longer than the source queue.
   Keep unsupported shared-DLQ, unpaired-queue, and unknown-value shapes
   fail-closed.
3. For each planned SQS-to-Lambda event source mapping, require direct
   configuration references to exactly one planned source queue and function,
   and bind the function to one planned IAM role. Require known function
   timeout and queue visibility of at least six times that timeout plus the
   event source batch window.
4. Require an inline role policy granting `sqs:ReceiveMessage`,
   `sqs:DeleteMessage`, and `sqs:GetQueueAttributes` only on the exact planned
   queue ARN. Reject wildcard/unresolved permissions and unsupported mapping
   or managed-policy shapes.
5. Add regression fixtures for valid and unsafe queue, redrive, timeout,
   event-source and permission combinations, including unknown values.
6. Update the Nova SQS policy matrix and ticket/test evidence. State that
   message processing, idempotency, producer authorization, runtime pricing,
   and real SQS lifecycle evidence remain unproven unless separately evidenced.

## Acceptance criteria

- [x] Queue visibility/retention unknowns and out-of-range values are denied.
- [x] Every planned queue belongs to one plan-bound, one-to-one source/DLQ
      pair. Redrive targets cannot be self-references, unplanned, cross-account,
      cross-region, shared, or cyclic.
- [x] The source's explicit `maxReceiveCount` is an integer from 5 through 10.
      The AWS Lambda guide recommends at least five attempts; ten is DavDeploy's
      explicit product cap.
- [x] The DLQ redrive-allow policy names only the exact source queue, and its
      message retention exceeds the source queue retention.
- [x] An SQS Lambda mapping is denied unless direct configuration references
      bind its source queue, function and execution role to this plan.
- [x] For Lambda consumers, queue visibility is at least six times the planned
      function timeout plus the configured batching window; unknown values
      fail closed.
- [x] The consumer role's inline policy grants the required SQS read and
      acknowledgement actions on the exact planned source ARN. Wildcard,
      conditioned, or unresolved permissions do not satisfy the rule.
- [x] Managed consumer policies and module-output-only bindings are explicitly
      unsupported and fail closed; no full effective-permission claim is made.
- [x] Existing SQS encryption and queue-policy checks remain intact, and the
      semantic policy version is bumped.
- [ ] Focused tests, Ruff, documentation conventions, diff checks, and all
      required PR CI checks pass on the merge-ready head.
- [x] Pricing documentation and findings remain honest: queue request units
      and consumer compute/transfer must be known and supported before costed
      approval; no complete quote is claimed by these policy checks.
- [x] No AWS resource, Terraform state, hosted control-plane runtime, customer
      credential, or Nova execution gate is mutated.

## Acceptance status

The implementation and local validations are complete on the draft PR. SQS
Lambda mapping support is limited to direct plan references and inline
consumer-role policies; CI/review remains outstanding and this source policy
is not deployed.

## Tests / validation performed

- Focused generated-plan, pricing, API schema, Terraform format/validate, Ruff,
  and diff checks are recorded in [`test445.md`](../test/test445.md).
- No AWS resource, Terraform state, hosted control-plane runtime, customer
  credential, or Nova execution gate has been changed.

## Evidence files produced

- `docs/tickets/ticket445.md`
- `docs/test/test445.md` — to be added before this PR is marked ready.
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `infrastructure/terraform/modules/sqs-queue/main.tf`
- `apps/api/src/davdeploy/domain.py` and `contracts/openapi-v1.json`

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
