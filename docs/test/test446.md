# test446 — isolated SQS retry and dead-letter lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: `c68dae0` (PR #446 test procedure; module dependency fix is in progress)

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The tagged DLQ `davdeploy-nova-sqs-446-nov22a1-dlq` was created by the first
apply. That run failed before creating the source queue. A source-only retry
apply `nova-sqs-446-source-nov22a1` is running with an explicit dependency on
the DLQ. Existing production-tagged queues are excluded.

## Commands executed

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` — verified
  account `654654474502` immediately before apply.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 init -backend=false` —
  initialized AWS provider 5.100.0.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 validate` — passed.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 plan -out=create.tfplan` —
  reviewed: two creates, zero changes, zero destroys.
- First monitored apply `nova-sqs-446-create-nov22a1` failed with exit 1 after
  creating only the DLQ. SQS rejected source creation because the DLQ target
  did not exist when the source was submitted.
- Added `depends_on = [aws_sqs_queue.dlq]` to the SQS module's source queue.
  `terraform validate` passed; `terraform graph` confirmed the source-to-DLQ
  dependency. The retry plan includes only the source queue create.
- Retry apply, message delivery/redrive, and teardown results will be added
  after their monitored operations reach terminal state.

## Observed result

Pending completion of the source-only monitored apply and SQS message
lifecycle. First failure and correction are documented above.

## Teardown

Pending. Only the named test stack will be destroyed, followed by independent
absence checks for both test queues.

## Final boundary

This direct same-account SQS test does not establish Nova dispatch,
cross-account isolation, Lambda consumer execution, application health,
idempotency, or general customer workload certification. The hosted control
plane, its Terraform state/locks, production queues, and Nova execution gates
were not changed.
