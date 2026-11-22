# test446 — isolated SQS retry and dead-letter lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: `32eaf0b` (PR #446 module ordering fix; evidence update follows)

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The test source queue and tagged DLQ were created with local Terraform state.
The first apply created only the DLQ and failed on source creation; the
source-only retry succeeded after adding an explicit source-to-DLQ dependency
to the module. Existing production-tagged queues are excluded.

## Commands executed

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` — verified
  account `654654474502` immediately before apply.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 init -backend=false` —
  initialized AWS provider 5.100.0.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 validate` — passed.
- Initial `terraform plan` — reviewed: two creates, zero changes, zero
  destroys.
- First monitored apply `nova-sqs-446-create-nov22a1` failed with exit 1 after
  creating only the DLQ. SQS rejected source creation because the DLQ target
  did not exist when the source was submitted.
- Added `depends_on = [aws_sqs_queue.dlq]` to the SQS module's source queue.
  `terraform validate` passed; `terraform graph` confirmed the source-to-DLQ
  dependency. The retry plan includes only the source queue create.
- Retry plan `create-source.tfplan` — one source queue create, zero changes,
  zero destroys.
- Monitored retry `nova-sqs-446-source-nov22a1` succeeded: one resource added,
  zero changed, zero destroyed. Log:
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-446-source-nov22a1.log`.
- `aws sqs send-message` returned message ID
  `442f76aa-5ddb-4341-ab8c-2793c205897e`; message body was not logged.
- Six source receive attempts returned the same message ID with approximate
  receive counts 1–5, then no source message after the count exceeded five.
- A DLQ receive returned that same message ID with receive count 6. No message
  was deleted or redriven manually.
- Reviewed saved destroy plan: exactly the source and DLQ queues are deleted;
  zero resources are created or updated.
- Destroy and post-destroy absence checks remain pending.

## Observed result

The source-to-DLQ receive and automatic redrive passed. Teardown and
independent absence checks are still pending.

## Teardown

Pending. Only the named test stack will be destroyed, followed by independent
absence checks for both test queues.

## Final boundary

This direct same-account SQS test does not establish Nova dispatch,
cross-account isolation, Lambda consumer execution, application health,
idempotency, or general customer workload certification. The hosted control
plane, its Terraform state/locks, production queues, and Nova execution gates
were not changed.
