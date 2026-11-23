# test452 — EventBridge SQS target failure, DLQ, and recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: `2162265b9935da5f350eff19292860a66ef1b2c1` (fixture and probe applied).

PR: [#452](https://github.com/Bepoadewale/davdeploy/pull/452), merged as
`6a193161aead202c4fda25b31cf70c512315961f`. Final CI run
[45217552598](https://github.com/Bepoadewale/davdeploy/actions/runs/45217552598)
passed all seven checks on head `9bfc02d70a89931a4037cb4c12a306bc7154d91f`.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The fixture created eight resources: one custom EventBridge bus, one matching
rule, one SQS target, one SQS consumer-redrive DLQ, one separate EventBridge
delivery DLQ, and two queue policies. All resources used the exact
`davdeploy-nova-eventbridge-dlq-452-nov23a1` prefix. Terraform state and plans
stayed outside the repository and the state is now empty.

## Commands executed

- Draft PR #452 and its ticket/test evidence were opened before AWS writes.
- Caller identity was verified as account `654654474502` in `us-east-1`; exact
  names had no conflict. The provider lock selects AWS provider `5.100.0`.
- The initial monitored create `nova-eventbridge-dlq-452-create-nov23a1`
  failed because the fixture lacked explicit Terraform graph dependencies. It
  had created the bus, rule, and two DLQ queues; the incomplete state was
  retained for a safe retry. The fixture was corrected to order the consumer
  DLQ before its source queue, queue policies after their queues, and the
  EventBridge target after both policies.
- Reviewed retry plan contained exactly four additional creates. Monitored run
  `nova-eventbridge-dlq-452-create-retry-nov23a1` started at
  `2026-11-23T16:06:42Z` (supervisor PID 39555, Terraform PID 39556, root
  `/private/tmp/davdeploy-eventbridge-dlq-452-nov23a1`). It completed at
  `16:07:41Z` with four added, zero changed, and zero destroyed; together the
  stack contained the planned eight resources.
- The first failure-probe attempt exposed a local SQS client-method bug after
  publishing a synthetic event. The corrected probe uses the low-level SQS
  client, redacts all message bodies, and successfully confirmed a blocked
  target plus a matching event in the EventBridge DLQ. A residual synthetic
  marker message from the failed probe was drained without printing its body.
- The reviewed recovery plan changed only `aws_sqs_queue_policy.target`:
  one update, zero creates, and zero deletes. Monitored run
  `nova-eventbridge-dlq-452-repair-nov23a1` started at
  `2026-11-23T16:14:50Z` (supervisor PID 42019, Terraform PID 42020) and
  completed at `16:15:20Z`. The recovery probe then received a matching event
  in the primary queue. Its message was deleted; both queues had zero visible
  and in-flight messages before teardown.
- Required PR checks passed on final head `2162265` in run
  [45215572683](https://github.com/Bepoadewale/davdeploy/actions/runs/45215572683).
- The reviewed destroy plan contained exactly eight deletes, zero creates, and
  zero updates. Monitored run `nova-eventbridge-dlq-452-destroy-nov23a1`
  started at `2026-11-23T16:20:43Z` (supervisor PID 43644, Terraform PID
  43649, root `/private/tmp/davdeploy-eventbridge-dlq-452-nov23a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-eventbridge-dlq-452-destroy-nov23a1.log`).
  It completed at `16:21:23Z` with zero additions, zero changes, and eight
  destroys. After the settling period, exact AWS prefix reads found no test
  EventBridge bus or SQS queues. Terraform state is empty and the run monitor
  has zero active operations.

## Expected redacted probe output

Failure stage: booleans for publish, primary-target block, DLQ receipt, marker
match, and body omission. Recovery stage: booleans for publish, target receipt,
marker match, and body omission. The probe prints no event or queue message
body.

## Acceptance criteria

- [x] A synthetic event reaches the EventBridge DLQ when the target queue's
      source-ARN condition is deliberately restrictive.
- [x] After updating the queue policy to the exact planned rule ARN, another
      synthetic event reaches the primary queue.
- [x] All created resources are removed through monitored Terraform destroy
      and independent AWS absence reads.
- [x] The test remains direct AWS service evidence and claims no Nova dispatch.

## Observed result

With a deliberately incorrect primary-queue source-ARN condition, the
synthetic event did not reach the target queue and a matching event reached the
separate EventBridge DLQ. Updating the policy to the exact planned rule ARN
allowed a second synthetic event to reach the primary queue. The corrected
probe printed only redacted boolean results; no message body was printed.

## Teardown

The reviewed exact eight-resource destroy succeeded through the PID monitor.
AWS independently returned no test bus or queues for the exact prefix; local
state is empty and the run monitor has no active operation. Production and
control-plane resources were out of scope and untouched.

## Final boundary

This is planned direct same-account service evidence. It does not claim Nova
dispatch, hosted execution, or customer workload certification. No production
or control-plane resources may be changed.
