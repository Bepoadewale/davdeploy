# test447 — isolated Lambda SQS retry lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: `a0db5cccd51e1b0bc751ac85b15b35943b6fbdd7` (evidence update pending).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The six-resource test stack was created with local Terraform state under the
unique `davdeploy-nova-sqs-lambda-447-nov22a1` prefix. It includes two SQS
queues, an execution role/inline policy, the failing Lambda, and its enabled
event source mapping.

## Commands executed

- GitHub PR #447 opened as a draft before resource creation.
- AWS identity and unique resource-name absence were checked before planning.
- Terraform monitor had 19 terminal records and zero active runs.
- Local Terraform root initialized AWS provider 5.100.0 and passed
  `terraform validate`.
- Saved plan reviewed: six creates, zero changes, zero destroys. It contains
  two SQS queues, one IAM role, one inline policy, one Lambda function, and one
  enabled event source mapping.
- Terraform graph confirms the source/DLQ and mapping/function/role-policy
  dependencies.
- Monitored saved-plan apply `nova-sqs-lambda-447-create-nov22a1` started at
  `2026-11-22T22:17:07Z` (supervisor PID 76303, Terraform PID 76304), root
  `/private/tmp/davdeploy-nova-sqs-lambda-447-nov22a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-lambda-447-create-nov22a1.log`.
  It succeeded with six added, zero changed, zero destroyed.
- `aws lambda get-event-source-mapping` returned State `Enabled`; function
  status is Active/Successful with timeout 3 seconds. Queue visibility is 30
  seconds; exact inline role actions and source ARN were verified.
- `aws sqs send-message` returned test message ID
  `6e6fe3bf-beae-41fc-9134-aadd6edd74b1`; the body was not printed.
- Lambda metrics during the test window reported five invocations and five
  errors. The source queue had no visible or in-flight messages after
  processing; the DLQ held the same synthetic message ID
  `6e6fe3bf-beae-41fc-9134-aadd6edd74b1` with
  `ApproximateReceiveCount=6`.
- A saved destroy plan contains exactly six deletes (the two named queues,
  test role and inline policy, Lambda function, and event source mapping),
  zero creates, and zero updates. The monitored destroy-plan apply is running.

## Observed result

The event source mapping was Enabled. CloudWatch reported five invocations and
five errors for the test Lambda. The source queue had zero visible and
in-flight messages after processing. The paired DLQ received the exact same
message ID with `ApproximateReceiveCount=6`, exceeding the configured
`maxReceiveCount=5`.

## Teardown

The reviewed six-resource destroy plan is running through the Terraform PID
monitor. Independent AWS absence checks are pending.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, application health, idempotency, or customer workload
certification. The hosted control plane, its Terraform state/locks, production
queues, and Nova execution gates are not part of the test.
