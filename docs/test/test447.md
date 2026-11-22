# test447 — isolated Lambda SQS retry lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: PR #447 bootstrap evidence; test results pending.

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
- Lambda error, retry, DLQ delivery, and teardown results are pending.

## Observed result

Pending Lambda failure, retry, and DLQ observation.

## Teardown

Pending. Only the named test stack will be destroyed after the lifecycle
probe.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, application health, idempotency, or customer workload
certification. The hosted control plane, its Terraform state/locks, production
queues, and Nova execution gates are not part of the test.
