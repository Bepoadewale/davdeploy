# test452 — EventBridge SQS target failure, DLQ, and recovery

Date: 2026-11-23

Execution type: Planned controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: Pending initial test commit.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

No AWS resources have been created yet. The fixture plans one custom
EventBridge bus, one matching rule, one SQS target, one SQS consumer-redrive
DLQ, one separate EventBridge delivery DLQ, and two queue policies. All
resources use the exact `davdeploy-nova-eventbridge-dlq-452-nov23a1` prefix.
Terraform state and plans stay outside the repository.

## Commands executed

Terraform init, validation, and formatting were run locally against a temporary
copy of the fixture. No AWS commands have been run. The intended sequence is
to open the draft PR first, verify identity and exact-name absence, review the
eight-resource create plan, create the isolated stack, observe a DLQ failure,
repair the rule grant, observe successful delivery, and remove the exact stack
with independently verified absence.

## Expected redacted probe output

Failure stage: booleans for publish, primary-target block, DLQ receipt, marker
match, and body omission. Recovery stage: booleans for publish, target receipt,
marker match, and body omission. The probe prints no event or queue message
body.

## Acceptance criteria

- [ ] A synthetic event reaches the EventBridge DLQ when the target queue's
      source-ARN condition is deliberately restrictive.
- [ ] After updating the queue policy to the exact planned rule ARN, another
      synthetic event reaches the primary queue.
- [ ] All created resources are removed through monitored Terraform destroy
      and independent AWS absence reads.
- [ ] The test remains direct AWS service evidence and claims no Nova dispatch.

## Observed result

Pending the controlled disposable run. No AWS resource has been created for
this test yet.

## Teardown

Pending the controlled disposable run. The reviewed destroy must use only the
exact test prefix; production and control-plane resources are out of scope.

## Final boundary

This is planned direct same-account service evidence. It does not claim Nova
dispatch, hosted execution, or customer workload certification. No production
or control-plane resources may be changed.
