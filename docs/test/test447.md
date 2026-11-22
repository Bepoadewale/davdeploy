# test447 — isolated Lambda SQS retry lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: PR #447 bootstrap evidence; test results pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The monitored apply `nova-sqs-lambda-447-create-nov22a1` is running for the
six-resource test stack under the unique
`davdeploy-nova-sqs-lambda-447-nov22a1` prefix. Terminal results are pending.

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
- Monitored saved-plan apply started at `2026-11-22T22:17:07Z` (supervisor PID
  76303), root `/private/tmp/davdeploy-nova-sqs-lambda-447-nov22a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-lambda-447-create-nov22a1.log`.
- Event source, failure, redrive, and teardown results are pending.

## Observed result

Pending completion of monitored apply. No test message has been sent.

## Teardown

Pending. Only the planned test stack will be destroyed after the lifecycle
probe.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, application health, idempotency, or customer workload
certification. The hosted control plane, its Terraform state/locks, production
queues, and Nova execution gates are not part of the test.
