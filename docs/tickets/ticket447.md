# ticket447 — isolated Lambda SQS consumer retry lifecycle evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/447
Branch: `test/nova-sqs-lambda-lifecycle-447`

## Problem / goal

Exercise an actual Lambda SQS event source mapping against a disposable source
queue and DLQ. The consumer deliberately fails on a synthetic event so the
test can observe Lambda-driven receive attempts and automatic SQS redrive. This
extends PR #446's direct ReceiveMessage test and gives real service evidence
for PR #445's same-plan consumer timeout and execution-role policy contract.

## Current repo state

- Backend `main` is `857e5efdf56713ecdd37ed24060fde15767930be` (PR #446).
- PR #445's SQS checks are merged in source but not deployed to the hosted
  control plane.
- PR #446 fixed source-after-DLQ Terraform ordering and documented direct
  source receive/redrive; it did not exercise a Lambda consumer.
- AWS account `654654474502`, region `us-east-1`; test resources will use only
  `davdeploy-nova-sqs-lambda-447-nov22a1`.
- The hosted control plane, its state/locks, and Nova execution gates are not
  part of this test.

## Research / references used

- [`test446.md`](../test/test446.md) — direct SQS repeated receive, automatic
  DLQ transition, and cleanup.
- [`ticket445.md`](ticket445.md) — plan-bound queue retry and Lambda consumer
  checks.
- AWS [Configuring a queue to trigger a Lambda function](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html) — event source mapping and queue visibility requirements.
- AWS [Lambda SQS configuration](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html) — execution-role permissions and visibility timeout guidance.
- AWS [SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html) — receive threshold and DLQ behavior.

## Work planned for the PR

1. Open a draft PR before any AWS mutation.
2. Create one managed-encrypted source/DLQ pair, a test-only Lambda role with
   exact source-queue receive/delete/attribute permissions, a short-timeout
   Lambda function, and an enabled SQS event source mapping.
3. Set visibility to at least six times the function timeout plus batching
   window. Use a one-to-one `byQueue` DLQ allow policy and `maxReceiveCount=5`.
4. Send a synthetic event to a deliberately failing consumer. Verify mapping
   state, Lambda invocation/error metrics, retry count, and automatic DLQ
   delivery. Do not log or print message contents or credentials.
5. Review a saved destroy plan, destroy only test resources through the PID
   monitor, and independently confirm the named test resources are absent.
6. Add `docs/test/test447.md` with exact run IDs, logs, observations, teardown,
   and limitations.

## Acceptance criteria

- [x] Draft PR and ticket exist before the first AWS mutation.
- [ ] Caller identity is account `654654474502`; all resource names and tags
      identify only this test.
- [ ] Event source mapping reaches Enabled and invokes the planned Lambda.
- [ ] Lambda error behavior is observed and a single synthetic message reaches
      the exact paired DLQ after exceeding `maxReceiveCount=5`.
- [ ] Plan values confirm visibility is at least six times function timeout
      plus batching window, and the role grants only the required exact-queue
      SQS actions.
- [ ] Monitored teardown succeeds; exact test resources are independently
      confirmed absent. No production queue or control-plane resource changes.
- [ ] Documentation conventions, focused checks, and all seven PR CI checks
      pass.
- [ ] Evidence is described as same-account direct service behavior, not Nova
      dispatch, cross-account isolation, or customer workload certification.

## Acceptance status

Draft PR #447 is open. The preceding PR #446 SQS resources were independently
confirmed absent. Caller identity and absence of the unique test prefix were
rechecked before apply. Monitored run `nova-sqs-lambda-447-create-nov22a1`
started at `2026-11-22T22:17:07Z`; its terminal result is pending. No test
message has been sent.

## Tests / validation performed

- Current main and PR #446 merge state verified through GitHub.
- AWS identity and absence of the unique SQS queue/Lambda names were verified
  before planning.
- Terraform monitor: 19 terminal records, zero active.
- Local Terraform root initialized AWS provider 5.100.0 and passed
  `terraform validate`.
- Reviewed saved plan: six creates (two SQS queues, one IAM role, one inline
  policy, one Lambda, one event source mapping), zero changes, zero destroys.
- Terraform graph confirms the source queue waits for the DLQ and the event
  source mapping waits for both the function and inline role policy.
- The planned role policy names only the three SQS receive/delete/attributes
  actions on the exact known source ARN; the 30-second queue visibility is
  greater than six times the 3-second function timeout plus zero batching.
- Monitored apply `nova-sqs-lambda-447-create-nov22a1` is in progress with
  supervisor PID 76303, root `/private/tmp/davdeploy-nova-sqs-lambda-447-nov22a1`,
  log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-lambda-447-create-nov22a1.log`.
- No message test has started.

## Evidence files produced

- `docs/tickets/ticket447.md`
- `docs/test/test447.md`

## Boundaries

Use only the test prefix `davdeploy-nova-sqs-lambda-447-nov22a1` in account
`654654474502`, region `us-east-1`. Keep state local and isolated. Start every
Terraform mutation through the PID monitor; record run ID, root, PID, and log.
Never overlap mutations on the root. Destroy only this test stack after
observing the lifecycle. Do not touch production queues, the hosted control
plane, its state/locks, Nova gates, or customer credentials. Keep secrets and
message contents out of logs and evidence.

Do not claim Nova generated or dispatched the test, that a customer workload
was applied or certified, or that this demonstrates cross-account isolation.

## Follow-up work

If this run passes, consider a separate successful-consumption and idempotency
test, followed by Nova-originated execution only if it can be done without
changing the hosted control plane.
